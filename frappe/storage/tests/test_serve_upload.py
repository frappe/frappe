# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import base64
import builtins
import hashlib
import io
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlencode

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.test import TestResponse

import frappe
import frappe.storage
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError
from frappe.core.doctype.file.file_v2 import create_file_from_blob
from frappe.storage.blob import put_blob
from frappe.storage.local_driver import LocalDriver
from frappe.storage.memory_driver import MemoryDriver
from frappe.storage.serve import serve_private_file, serve_public_file, stream_blob
from frappe.storage.tests import (
	file_permissions_enforced,
	hook_value,
	storage_v2,
	unique_bytes,
	use_driver,
)
from frappe.storage.upload import (
	BLOB_SESSION,
	FILE_SESSION,
	FINISHING_SUFFIX,
	claim_session,
	create_blob_upload,
	create_upload,
	delete_session,
	expire_stale_upload_sessions,
	finish_upload,
	finish_upload_to_blob,
	get_request_bytes,
	get_session_paths,
	get_uploads_dir,
	require_session_policy,
	upload_blob_chunk,
	upload_chunk,
)
from frappe.storage.url import make_signature
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import FrappeAPITestCase, make_request
from frappe.tests.test_chrome_pdf_interceptor import _fire_request, _make_page, _make_session
from frappe.utils import set_request
from frappe.utils.logging import ensure_log_table, get_log_db

PDF_HOST = "https://example.frappe.test/"


class NativeUrlDriver(MemoryDriver):
	"""Driver that hands out its own download URLs, like S3 presigned GET."""

	def download_url(
		self, key, filename, expires_in, *, is_private=False, mime_type=None, as_attachment=False
	):
		return f"https://cdn.example/{key}?name={filename}&ttl={expires_in}"


class TempLocalDriver(LocalDriver):
	"""LocalDriver rooted in a temp dir, so get_path never touches the site."""

	def __init__(self, root):
		self.root = root

	def get_files_dir(self, is_private: bool = False) -> str:
		path = os.path.join(self.root, "private" if is_private else "public", "files")
		os.makedirs(path, exist_ok=True)
		return path


class DirectTargetDriver(MemoryDriver):
	"""Driver that takes browser -> bucket uploads."""

	def upload_target(self, key, size, *, is_private=False):
		return {"url": "https://bucket.example/upload"}


class VanishingDirectDriver(DirectTargetDriver):
	"""exists() says yes, read() says no: the object died between the two."""

	def exists(self, key, *, is_private=False):
		return True


class StorageUnavailable(Exception):
	"""Not an OSError, like botocore's EndpointConnectionError."""


class UnreachableDriver(MemoryDriver):
	def read(self, key, *, is_private=False):
		raise StorageUnavailable("storage is unreachable")


class UndeletableDirectDriver(DirectTargetDriver):
	"""Driver whose delete always fails, like an unreachable bucket."""

	def delete(self, key, *, is_private=False):
		raise RuntimeError("bucket unreachable")


def response_body(response) -> bytes:
	# send_file responses use direct_passthrough; get_data() would raise
	return b"".join(response.response)


def blob_of(result):
	"""The File Blob behind a finish result, which is a File row or the blob itself."""
	return frappe.get_doc("File Blob", result.blob) if result.doctype == "File" else result


class TestServeUpload(IntegrationTestCase):
	"""GET /files/ and /private/files/ serve routes and the three-step upload flow.

	Upload session files land in private/files/.uploads and are removed
	in tearDown."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._sessions = []

	def tearDown(self):
		for upload_id in self._sessions:
			meta_path, part_path = get_session_paths(upload_id)
			delete_session(meta_path, meta_path + FINISHING_SUFFIX, part_path)
		frappe.local.form_dict = frappe._dict()
		if hasattr(frappe.local, "request"):
			del frappe.local.request
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDown()

	# ---- helpers ----

	def serve(self, path: str, headers: dict | None = None, **query):
		"""Route ``path`` the way ``frappe.app.application`` does."""
		set_request(method="GET", path=path, headers=headers or {})
		frappe.local.form_dict = frappe._dict(query)
		try:
			if path.startswith("/private/files/"):
				return serve_private_file(path)
			return serve_public_file(path)
		finally:
			frappe.local.form_dict = frappe._dict()
			if hasattr(frappe.local, "request"):
				del frappe.local.request

	def send_chunk(self, upload_id: str, offset: int, data: bytes):
		# upload_chunk takes a raw PUT body
		set_request(method="PUT", path="/", data=data)
		try:
			return upload_chunk(upload_id, offset)
		finally:
			if hasattr(frappe.local, "request"):
				del frappe.local.request

	def open_session(self, filename: str, size: int, *, mode="chunked", is_private=1, **target) -> str:
		result = create_upload(filename, size, is_private=is_private, **target)
		self.assertEqual(result["mode"], mode)
		self._sessions.append(result["upload_id"])
		return result["upload_id"]

	def open_blob_session(self, filename: str, size: int, *, mode="chunked") -> str:
		result = create_blob_upload(filename, size)
		self.assertEqual(result["mode"], mode)
		self._sessions.append(result["upload_id"])
		return result["upload_id"]

	def session_kinds(self):
		"""The public File flow and the trusted blob flow share every session rule."""
		return (
			("file", self.open_session, self.send_chunk, finish_upload),
			("blob", self.open_blob_session, upload_blob_chunk, finish_upload_to_blob),
		)

	def session_files(self, upload_id: str) -> set[str]:
		"""Which of the session's meta, claimed meta, and part files exist."""
		meta_path, part_path = get_session_paths(upload_id)
		paths = {"meta": meta_path, "claimed": meta_path + FINISHING_SUFFIX, "part": part_path}
		return {name for name, path in paths.items() if os.path.exists(path)}

	def backdate(self, *paths: str, hours: float = 25):
		stamp = time.time() - hours * 3600
		for path in paths:
			os.utime(path, (stamp, stamp))

	def temp_local_driver(self) -> TempLocalDriver:
		root = tempfile.TemporaryDirectory()
		self.addCleanup(root.cleanup)
		return TempLocalDriver(root.name)

	def insert_moved_file(self, file_name: str, *, is_private: int) -> tuple[str, bytes]:
		"""A File row as relocation leaves it: a v1 URL linked to a blob. Return the URL and bytes."""
		content = unique_bytes(b"moved v1 bytes ")
		blob = put_blob(io.BytesIO(content), is_private=bool(is_private), filename=file_name)
		folder = "/private/files" if is_private else "/files"
		file_url = f"{folder}/storage-v2-moved-{frappe.generate_hash(length=10)}-{file_name}"
		file = frappe.new_doc("File", file_name=file_name, file_url=file_url, blob=blob.name)
		file.update({"name": frappe.generate_hash(length=10), "is_private": is_private, "is_folder": 0})
		file.db_insert()
		return file_url, content

	def render_in_pdf(self, url: str, user: str = "Administrator"):
		"""Fire one request through the PDF renderer's interceptor. Return the CDP command and params."""
		captured = [None]
		session = _make_session(captured)
		frappe.set_user(user)
		with patch("frappe.utils.chromium.page.get_host_url", return_value=PDF_HOST):
			_make_page(session).intercept_request_for_local_resources()
			_fire_request(captured[0], "req", PDF_HOST + url.lstrip("/"))
		return session.send.call_args.args[:2]

	# ---- serve routes ----

	def test_private_route_needs_a_signature_or_file_permission(self):
		ensure_log_table("Access Log")
		with storage_v2(), frappe.storage.fake():
			content = unique_bytes(b"private route ")
			blob = put_blob(io.BytesIO(content), is_private=True, filename="report.txt")
			url = f"/private/files/{blob.name}/report.txt"
			# a v1 URL whose bytes moved into a blob keeps its File row's permission
			moved_url, moved_content = self.insert_moved_file("contract.pdf", is_private=1)

			# no File row: nobody passes the permission check, not even Administrator.
			# An unknown blob gets the same answer, so there is no existence oracle.
			for path in (url, "/private/files/nosuchblob/report.txt"):
				with self.subTest(path=path), self.assertRaises(Forbidden):
					self.serve(path)

			frappe.set_user("Guest")
			expires = int(time.time()) + 60
			signature = make_signature(blob.name, "report.txt", expires)
			response = self.serve(url, e=str(expires), s=signature)
			self.assertEqual(response.status_code, 200)
			self.assertEqual(response_body(response), content)

			expired = int(time.time()) - 1
			tampered = signature[:-1] + ("0" if signature[-1] != "0" else "1")
			for path, query in (
				(url, {}),
				(moved_url, {}),
				(url, {"e": str(expired), "s": make_signature(blob.name, "report.txt", expired)}),
				(url, {"e": str(expires), "s": tampered}),
				# a signature for one filename must not open another
				(f"/private/files/{blob.name}/other.txt", {"e": str(expires), "s": signature}),
			):
				with self.subTest(path=path, query=query), self.assertRaises(Forbidden):
					self.serve(path, **query)

			frappe.set_user("Administrator")
			create_file_from_blob(blob, "report.txt", is_private=True)
			self.assertEqual(response_body(self.serve(url)), content)
			self.assertEqual(response_body(self.serve(moved_url)), moved_content)
			# Access Log rows live in the site's SQLite log database
			self.assertTrue(
				get_log_db().exists(
					"Access Log", {"reference_document": blob.name, "export_from": "File Blob"}
				)
			)

	def test_public_route_serves_only_public_blobs(self):
		with storage_v2(), frappe.storage.fake() as store:
			content = unique_bytes(b"public bytes ")
			public = put_blob(io.BytesIO(content))
			private = put_blob(io.BytesIO(unique_bytes(b"private bytes ")), is_private=True)
			gone = put_blob(io.BytesIO(unique_bytes(b"vanishing ")))
			store.delete(gone.key, is_private=False)
			moved_url, moved_content = self.insert_moved_file("logo.png", is_private=0)

			frappe.set_user("Guest")
			response = self.serve(f"/files/{public.name}/pub.txt")
			self.assertEqual(response.status_code, 200)
			self.assertEqual(response_body(response), content)
			self.assertEqual(response_body(self.serve(moved_url)), moved_content)

			for path in (
				"/files/",
				"/files/some.txt",
				"/files/nosuchblob/a.txt",
				f"/files/{public.name}/a/b.txt",
				f"/files/{gone.name}/gone.txt",
				# a private blob is never served under /files/, not even its own URL
				f"/files/{private.name}/file",
			):
				with self.subTest(path=path), self.assertRaises(NotFound):
					self.serve(path)

			frappe.set_user("Administrator")
			with self.assertRaises(NotFound):
				self.serve(f"/files/{private.name}/file")

	def test_active_content_is_served_as_an_attachment(self):
		# the URL filename is caller-chosen: an HTML blob requested as x.txt
		# must not render inline on the site origin either
		svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
		html = b"<!DOCTYPE html><html><body>" + unique_bytes() + b"</body></html>"
		with storage_v2(), frappe.storage.fake():
			urls = [
				f"/files/{put_blob(io.BytesIO(svg)).name}/image.svg",
				f"/files/{put_blob(io.BytesIO(html)).name}/innocent.txt",
			]
			frappe.set_user("Guest")
			for url in urls:
				with self.subTest(url=url):
					response = self.serve(url)
					self.assertEqual(response.status_code, 200)
					self.assertTrue(response.headers.get("Content-Disposition", "").startswith("attachment"))

	def test_pdf_renderer_reads_blobs_that_are_not_on_disk_and_checks_access(self):
		with storage_v2(), frappe.storage.fake():
			public = put_blob(io.BytesIO(b"<svg>public</svg>"), filename="logo.svg")
			private = put_blob(io.BytesIO(b"private png"), is_private=True, filename="sign.png")
			create_file_from_blob(private, "sign.png", is_private=True)
			moved_url, moved_content = self.insert_moved_file("photo.jpg", is_private=1)
			urls = {
				f"/files/{public.name}/logo.svg": (b"<svg>public</svg>", "image/svg+xml"),
				f"/private/files/{private.name}/sign.png": (b"private png", "image/png"),
				moved_url: (moved_content, "image/jpeg"),
			}

			for url, (content, content_type) in urls.items():
				with self.subTest(url=url):
					method, params = self.render_in_pdf(url)
					self.assertEqual(method, "Fetch.fulfillRequest")
					self.assertEqual(base64.b64decode(params["body"]), content)
					self.assertIn({"name": "Content-Type", "value": content_type}, params["responseHeaders"])

			self.assertEqual(
				self.render_in_pdf(f"/files/{public.name}/logo.svg", "Guest")[0], "Fetch.fulfillRequest"
			)
			for url in list(urls)[1:]:
				with self.subTest(url=url, user="Guest"):
					method, params = self.render_in_pdf(url, "Guest")
					self.assertEqual(method, "Fetch.failRequest")
					self.assertEqual(params["errorReason"], "AccessDenied")

		# a driver that cannot read fails only that one image
		with storage_v2(), use_driver(UnreachableDriver()):
			blob = put_blob(io.BytesIO(b"<svg>unreachable</svg>"), filename="logo.svg")
			method, params = self.render_in_pdf(f"/files/{blob.name}/logo.svg")
		self.assertEqual(method, "Fetch.failRequest")
		self.assertEqual(params["requestId"], "req")

	def test_native_url_driver_redirects(self):
		with storage_v2(), use_driver(NativeUrlDriver()):
			content = unique_bytes(b"native ")
			public = put_blob(io.BytesIO(unique_bytes(b"native ")))
			private = put_blob(io.BytesIO(content), is_private=True)

			frappe.set_user("Guest")
			response = self.serve(f"/files/{public.name}/n.txt")
			self.assertEqual(response.status_code, 302)
			self.assertEqual(
				response.headers["Location"], f"https://cdn.example/{public.name}/file?name=n.txt&ttl=3600"
			)
			self.assertEqual(response.headers["Cache-Control"], "public, max-age=1800")

			expires = int(time.time()) + 60
			signature = make_signature(private.name, "n.txt", expires)
			response = self.serve(f"/private/files/{private.name}/n.txt", e=str(expires), s=signature)
			self.assertEqual(response.status_code, 302)
			self.assertEqual(
				response.headers["Location"], f"https://cdn.example/{private.name}/file?name=n.txt&ttl=60"
			)
			self.assertNotIn("public", response.headers.get("Cache-Control") or "")

			# an already authorized stream redirects only when the caller opts in
			set_request(method="GET", path="/dav/n.txt")
			response = stream_blob(private, "n.txt")
			self.assertEqual(response.status_code, 200)
			self.assertEqual(response_body(response), content)
			response.close()
			response = stream_blob(private, "n.txt", allow_native_redirect=True)
			self.assertEqual(response.status_code, 302)
			self.assertIn(private.key, response.headers["Location"])

	def test_local_blobs_use_x_accel_or_disk_ranges(self):
		svg = b'<svg xmlns="http://www.w3.org/2000/svg"><!--' + unique_bytes() + b"--></svg>"
		accel = {"X-Use-X-Accel-Redirect": "1"}
		with storage_v2(), use_driver(self.temp_local_driver()) as driver:
			report = put_blob(
				io.BytesIO(unique_bytes(b"accel private ")), is_private=True, filename="report.pdf"
			)
			logo = put_blob(io.BytesIO(svg), filename="logo.svg")
			self.assertEqual(report.driver, "local")
			expires = int(time.time()) + 60
			signature = make_signature(report.name, "report.pdf", expires)

			frappe.set_user("Guest")
			response = self.serve(
				f"/private/files/{report.name}/report.pdf", accel, e=str(expires), s=signature
			)
			private_path = frappe.local.conf.get("private_path", "private")
			self.assertEqual(
				response.headers["X-Accel-Redirect"],
				f"/protected/{private_path}/files/{report.name}/report.pdf",
			)
			self.assertEqual(response.headers["Accept-Ranges"], "bytes")
			self.assertEqual(response.headers["Content-Type"], "application/pdf")
			self.assertIn("private", response.headers["Cache-Control"])
			# a pdf is not active content: it stays inline
			self.assertIsNone(response.headers.get("Content-Disposition"))

			response = self.serve(f"/files/{logo.name}/logo.svg", accel)
			self.assertEqual(response.headers["X-Accel-Redirect"], f"/files/{logo.name}/logo.svg")
			self.assertEqual(response.headers["Content-Type"], "image/svg+xml")
			self.assertEqual(response.headers["Content-Disposition"], "attachment; filename*=UTF-8''logo.svg")

			# without X-Accel, ranges are read from disk
			content = unique_bytes(b"range ") * 8
			blob = put_blob(io.BytesIO(content), filename="data.bin")
			gone = put_blob(io.BytesIO(unique_bytes(b"deleted from disk ")), filename="gone.bin")
			os.remove(driver.get_path(gone.key, False))
			response = self.serve(f"/files/{blob.name}/data.bin", {"Range": "bytes=5-14"})
			self.assertEqual(response.status_code, 206)
			self.assertEqual(response.headers["Content-Range"], f"bytes 5-14/{len(content)}")
			self.assertEqual(response_body(response), content[5:15])
			response.close()

			with self.assertRaises(NotFound):
				self.serve(f"/files/{gone.name}/gone.bin")

	def test_stream_blob_answers_range_requests(self):
		content = b"0123456789abcdefghijklmnopqrstuvwxyz"
		cases = (
			("bytes=5-14", 206, "bytes 5-14/36", content[5:15]),
			("bytes=20-", 206, "bytes 20-35/36", content[20:]),
			("bytes=100-200", 416, "bytes */36", b""),
		)
		with storage_v2(), frappe.storage.fake():
			blob = put_blob(io.BytesIO(content), is_private=True, filename="data.bin")
			for range_header, status, content_range, body in cases:
				with self.subTest(range=range_header):
					set_request(method="GET", path="/dav/data.bin", headers={"Range": range_header})
					response = stream_blob(blob, "data.bin")
					self.assertEqual(response.status_code, status)
					self.assertEqual(response.headers["Content-Range"], content_range)
					self.assertEqual(response.headers["Accept-Ranges"], "bytes")
					self.assertEqual(response_body(response), body)
					response.close()

	def test_stream_blob_trusts_its_caller_and_honours_etags(self):
		with storage_v2(), frappe.storage.fake() as store:
			content = unique_bytes(b"already authorized ")
			blob = put_blob(io.BytesIO(content), is_private=True, filename="private.bin")
			frappe.set_user("Guest")

			set_request(method="GET", path="/dav/private.bin")
			with (
				patch("frappe.storage.serve.has_file_permission") as has_permission,
				patch("frappe.storage.serve.make_access_log") as access_log,
			):
				response = stream_blob(blob, "private.bin")
			self.assertEqual(response.status_code, 200)
			self.assertEqual(response_body(response), content)
			has_permission.assert_not_called()
			access_log.assert_not_called()
			response.close()

			set_request(
				method="GET", path="/dav/private.bin", headers={"If-None-Match": f'"{blob.checksum}"'}
			)
			with patch.object(store, "read") as read, patch.object(store, "read_range") as read_range:
				response = stream_blob(blob, "private.bin")
			self.assertEqual(response.status_code, 304)
			self.assertEqual(response.headers["ETag"], f'"{blob.checksum}"')
			read.assert_not_called()
			read_range.assert_not_called()

	# ---- upload sessions: entry points ----

	def test_upload_entry_points_refuse_bad_input(self):
		with storage_v2(False):
			with self.assertRaises(frappe.ValidationError):
				create_upload("off.txt", 10)
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk("doesnotmatter", 0, b"x")
			with self.assertRaises(frappe.ValidationError):
				finish_upload("doesnotmatter")

		with storage_v2(), frappe.storage.fake():
			with patch("frappe.core.api.file.get_max_file_size", return_value=1024):
				with self.assertRaises(MaxFileSizeReachedError):
					create_upload("big.bin", 2048)
			for upload_id in ("", "../../etc/passwd", "abc.def", "abc/def"):
				with self.subTest(upload_id=upload_id), self.assertRaises(frappe.ValidationError):
					get_session_paths(upload_id)
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk("../../etc/passwd", 0, b"x")

	def test_trusted_sessions_stay_off_http(self):
		for function in (create_blob_upload, upload_blob_chunk, finish_upload_to_blob):
			self.assertNotIn(function, frappe.whitelisted)
		with storage_v2(), frappe.storage.fake():
			for bypass in (
				{"session_policy": BLOB_SESSION},
				{"check_permission": False},
				{"restrict_mimetypes": False},
			):
				with self.subTest(bypass=bypass), self.assertRaises(TypeError):
					create_upload("bypass.html", 4, **bypass)

			blob_session = self.open_blob_session("private.bin", 4)
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk(blob_session, 0, b"data")
			with self.assertRaises(frappe.ValidationError):
				finish_upload(blob_session)
			# rejection does not consume the session: the trusted path can finish it
			upload_blob_chunk(blob_session, 0, b"data")
			self.assertEqual(frappe.db.count("File", {"blob": finish_upload_to_blob(blob_session).name}), 0)

			file_session = self.open_session("public.txt", 4)
			with self.assertRaises(frappe.ValidationError):
				upload_blob_chunk(file_session, 0, b"data")
			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(file_session)

			for policy in (FILE_SESSION, BLOB_SESSION):
				with self.subTest(policy=policy), self.assertRaises(frappe.ValidationError):
					require_session_policy({}, policy)

	def test_chunk_route_streams_a_bounded_raw_put_body(self):
		# a POST would run make_form_dict, which decodes the body as text and caps
		# it at the generic upload size; only PUT on a streaming path skips that
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[upload_chunk], ("PUT",))
		self.assertIn(
			"/api/method/frappe.storage.upload.upload_chunk", frappe.get_hooks("streaming_request_paths")
		)

		# streaming paths lift the generic byte cap, so the read bounds itself
		set_request(method="PUT", path="/", data=b"x" * (64 * 1024))
		self.assertEqual(get_request_bytes(limit=4), b"xxxxx")

		# form bodies are refused by Content-Type alone, before Werkzeug's form
		# parser spools a body of any size
		for mimetype, data in (
			("multipart/form-data", {"file": (io.BytesIO(b"x" * (256 * 1024)), "huge.bin")}),
			("application/x-www-form-urlencoded", {"a": "x" * (256 * 1024)}),
		):
			with self.subTest(mimetype=mimetype):
				set_request(method="PUT", path="/", data=data)
				frappe.local.request.max_content_length = None
				raw_input = frappe.local.request.environ["wsgi.input"]
				with self.assertRaises(frappe.ValidationError):
					get_request_bytes(limit=4)
				self.assertEqual(raw_input.tell(), 0)

	# ---- upload sessions: flows ----

	def test_chunked_upload_creates_one_file(self):
		with storage_v2(), frappe.storage.fake() as store:
			content = unique_bytes(b"chunked upload ") * 20
			half = len(content) // 2
			upload_id = self.open_session("hello.txt", len(content))

			# only an offset that leaves no hole is accepted
			for offset in (5, -1):
				with self.subTest(offset=offset), self.assertRaises(frappe.ValidationError):
					self.send_chunk(upload_id, offset, b"x")
			self.assertEqual(self.send_chunk(upload_id, 0, content[:half])["received"], half)
			# retrying a received chunk is allowed, writing past the end is not
			self.assertEqual(self.send_chunk(upload_id, 0, content[:half])["received"], half)
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk(upload_id, half + 1, b"x")
			self.assertEqual(self.send_chunk(upload_id, half, content[half:])["received"], len(content))

			checksum = hashlib.sha256(content).hexdigest()
			file = finish_upload(upload_id, checksum=checksum, file_name="hello.txt")
			blob = frappe.get_doc("File Blob", file.blob)
			self.assertEqual((blob.checksum, blob.file_size), (checksum, len(content)))
			self.assertTrue(store.exists(blob.key, is_private=True))
			self.assertEqual(self.session_files(upload_id), set())

			with self.assertRaises(frappe.ValidationError):
				finish_upload(upload_id, file_name="hello.txt")
			self.assertEqual(frappe.db.count("File", {"blob": file.blob}), 1)

	def test_trusted_upload_creates_a_blob_without_file_gates_or_hooks(self):
		hook_calls = []

		def adopt(*, doc):
			hook_calls.append(doc)
			return doc

		first, second = b"first half ", unique_bytes(b"second half ")
		with storage_v2(), frappe.storage.fake() as store, hook_value("after_file_upload", [adopt]):
			# a Guest may open a trusted session for an .html name: the caller authorizes it
			frappe.set_user("Guest")
			upload_id = self.open_blob_session("trusted.html", len(first + second))
			self.assertEqual(upload_blob_chunk(upload_id, 0, first)["received"], len(first))
			# the next chunk appends to the part file instead of truncating it
			self.assertEqual(
				upload_blob_chunk(upload_id, len(first), second)["received"], len(first + second)
			)
			with open(get_session_paths(upload_id)[1], "rb") as f:
				self.assertEqual(f.read(), first + second)

			blob = finish_upload_to_blob(upload_id, checksum=hashlib.sha256(first + second).hexdigest())
			self.assertEqual(blob.file_size, len(first + second))
			self.assertTrue(store.exists(blob.key, is_private=True))
			self.assertEqual(frappe.db.count("File", {"blob": blob.name}), 0)
			self.assertEqual(hook_calls, [])
			self.assertEqual(self.session_files(upload_id), set())

			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)

	def test_ordinary_user_uploads_to_own_todo_and_only_they_read_it_privately(self):
		uploader, stranger = "test1@example.com", "test2@example.com"
		with storage_v2(), frappe.storage.fake() as store, file_permissions_enforced():
			files = {}
			with self.set_user(uploader):
				todo = frappe.get_doc(doctype="ToDo", description="storage v2 upload").insert()
				for is_private in (0, 1):
					content = unique_bytes(b"ordinary user upload ")
					upload_id = self.open_session(
						"notes.txt", len(content), is_private=is_private, doctype="ToDo", docname=todo.name
					)
					self.send_chunk(upload_id, 0, content)
					file = finish_upload(upload_id, checksum=hashlib.sha256(content).hexdigest())
					files[is_private] = (file, content)

					self.assertEqual(file.owner, uploader)
					self.assertEqual((file.attached_to_doctype, file.attached_to_name), ("ToDo", todo.name))
					self.assertEqual(file.is_private, is_private)
					blob_key = frappe.db.get_value("File Blob", file.blob, "key")
					self.assertTrue(store.exists(blob_key, is_private=bool(is_private)))

				private_file, private_content = files[1]
				self.assertEqual(response_body(self.serve(private_file.file_url)), private_content)

			with self.set_user(stranger):
				public_file, public_content = files[0]
				self.assertEqual(response_body(self.serve(public_file.file_url)), public_content)
				with self.assertRaises(Forbidden):
					self.serve(private_file.file_url)

	def test_guest_uploads_follow_system_settings(self):
		settings = {
			"allow_guests_to_upload_files": 1,
			"allowed_doctypes_for_guest_uploads": "ToDo\n\nBlog Post\n",
		}
		todo = {"doctype": "ToDo", "docname": "new-todo-1"}
		with storage_v2(), frappe.storage.fake():
			with self.change_settings("System Settings", settings):
				frappe.set_user("Guest")
				with self.assertRaises(frappe.PermissionError):
					create_upload("ok.png", 10, doctype="Contact", docname="new-contact-1")
				# guests keep upload_file's mimetype allowlist, at create and at finish
				with self.assertRaises(frappe.ValidationError):
					create_upload("evil.html", 10, **todo)
				upload_id = self.open_session("ok.png", 10, **todo)
				self.assertEqual(self.send_chunk(upload_id, 0, b"abc")["received"], 3)
				with self.assertRaises(frappe.ValidationError):
					finish_upload(upload_id, file_name="evil.html")

			# every guest is the same session user, so the permission check runs per chunk
			with self.assertRaises(frappe.PermissionError):
				self.send_chunk(upload_id, 3, b"def")

	def test_direct_upload_finishes_from_the_bucket_object(self):
		with storage_v2(), use_driver(DirectTargetDriver()) as driver:
			for kind, open_session, send_chunk, finish in self.session_kinds():
				with self.subTest(kind=kind):
					content = unique_bytes(b"direct upload bytes ")
					upload_id = open_session("direct.bin", len(content), mode="direct")
					with self.assertRaises(frappe.ValidationError):
						send_chunk(upload_id, 0, b"x")
					# finishing before the browser uploaded fails and keeps the session
					with self.assertRaises(frappe.ValidationError):
						finish(upload_id)

					driver.write(f"uploads/{upload_id}", io.BytesIO(content), is_private=True)
					blob = blob_of(finish(upload_id))
					self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
					self.assertTrue(driver.exists(blob.key, is_private=True))
					self.assertEqual(frappe.db.count("File", {"blob": blob.name}), 1 if kind == "file" else 0)
					self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))

				with self.subTest(kind=kind, object="oversize"):
					upload_id = open_session("oversize.bin", 3, mode="direct")
					driver.write(f"uploads/{upload_id}", io.BytesIO(b"four"), is_private=True)
					with self.assertRaises(frappe.ValidationError):
						finish(upload_id)
					self.assertEqual(self.session_files(upload_id), set())
					self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))

	def test_direct_upload_object_that_vanishes_before_the_read_fails(self):
		with storage_v2(), use_driver(VanishingDirectDriver()):
			upload_id = self.open_session("gone.txt", 10, mode="direct")
			# exists() passes the pre-flight check, read() then finds nothing
			with self.assertRaises(frappe.ValidationError):
				finish_upload(upload_id, file_name="gone.txt")
			self.assertEqual(frappe.db.count("File", {"file_name": "gone.txt"}), 0)

	# ---- upload sessions: rules shared by both kinds ----

	def test_session_rules_hold_for_both_kinds(self):
		content = b"session rule bytes"
		failing_finishes = (
			(unique_bytes(b"checksum mismatch "), "sum.txt", "0" * 64),
			(b"<html><script>bad()</script></html>", "disguised.png", None),
		)
		with storage_v2(), frappe.storage.fake():
			for kind, open_session, send_chunk, finish in self.session_kinds():
				with self.subTest(kind=kind, rule="bound to the owner"):
					upload_id = open_session("owned.bin", 10)
					with self.set_user("Guest"):
						with self.assertRaises(frappe.PermissionError):
							send_chunk(upload_id, 0, b"x")
						with self.assertRaises(frappe.PermissionError):
							finish(upload_id)

				with self.subTest(kind=kind, rule="an oversize chunk kills the session"):
					upload_id = open_session("small.bin", 3)
					with self.assertRaises(frappe.ValidationError):
						send_chunk(upload_id, 0, b"four")
					self.assertEqual(self.session_files(upload_id), set())
					with self.assertRaises(frappe.ValidationError):
						send_chunk(upload_id, 0, b"x")

				for failing_content, filename, checksum in failing_finishes:
					with self.subTest(kind=kind, rule="a failed finish drops the session", filename=filename):
						upload_id = open_session(filename, len(failing_content))
						send_chunk(upload_id, 0, failing_content)
						with self.assertRaises(frappe.ValidationError):
							finish(upload_id, checksum=checksum)
						self.assertEqual(self.session_files(upload_id), set())

				with self.subTest(kind=kind, rule="a finish without bytes is retryable"):
					upload_id = open_session("empty.bin", len(content))
					with self.assertRaisesRegex(frappe.ValidationError, "no data"):
						finish(upload_id)
					self.assertEqual(self.session_files(upload_id), {"meta", "part"})
					send_chunk(upload_id, 0, content)
					self.assertEqual(blob_of(finish(upload_id)).file_size, len(content))

				# a finish that consumed the session deleted its part file; a chunk
				# still in flight must not re-create it and report bytes nobody reads
				with self.subTest(kind=kind, rule="a session without its part file refuses work"):
					upload_id = open_session("missing.bin", len(content))
					send_chunk(upload_id, 0, content)
					delete_session(get_session_paths(upload_id)[1])
					# the no-data check runs before the claim, so the session stays unclaimed
					with self.assertRaisesRegex(frappe.ValidationError, "no data"):
						finish(upload_id)
					with self.assertRaisesRegex(frappe.ValidationError, "no data"):
						send_chunk(upload_id, 0, content)
					self.assertEqual(self.session_files(upload_id), {"meta"})

	# ---- upload sessions: finish races ----

	def test_concurrent_session_claim_has_a_single_winner(self):
		with storage_v2(), frappe.storage.fake():
			meta_path, _part_path = get_session_paths(self.open_session("race.txt", 4))
			barrier = Barrier(2)

			def compete():
				barrier.wait()
				try:
					return claim_session(meta_path)
				except frappe.ValidationError:
					return None

			with ThreadPoolExecutor(max_workers=2) as pool:
				futures = [pool.submit(copy_context().run, compete) for _ in range(2)]
				results = [future.result() for future in futures]

			self.assertEqual(len([claimed for claimed in results if claimed]), 1)

	def test_finish_refuses_a_session_consumed_while_it_is_read(self):
		"""The winner of a finish race deletes the session while the loser still
		reads its meta file. The loser sees the session error, not an OSError."""
		content = b"one winner only"
		with storage_v2(), frappe.storage.fake():
			upload_id = self.open_blob_session("race.bin", len(content))
			upload_blob_chunk(upload_id, 0, content)
			meta_path, part_path = get_session_paths(upload_id)
			real_open = builtins.open

			def consume_then_open(file, *args, **kwargs):
				if file == meta_path:
					# stands in for the winner claiming and dropping the session
					delete_session(meta_path, part_path)
				return real_open(file, *args, **kwargs)

			with patch("builtins.open", consume_then_open):
				with self.assertRaisesRegex(frappe.ValidationError, "not found or expired"):
					finish_upload_to_blob(upload_id)

			self.assertEqual(self.session_files(upload_id), set())

	def test_finish_refuses_a_session_whose_part_vanishes_after_the_claim(self):
		"""Claiming does not pin the part file: a concurrent oversize chunk deletes
		it. The finisher sees the session error, not an OSError."""
		content = b"claimed then robbed"
		with storage_v2(), frappe.storage.fake():
			upload_id = self.open_blob_session("robbed.bin", len(content))
			upload_blob_chunk(upload_id, 0, content)
			meta_path, part_path = get_session_paths(upload_id)
			real_rename = os.rename

			def rob_after_claim(src, dst, *args, **kwargs):
				result = real_rename(src, dst, *args, **kwargs)
				if src == meta_path:
					delete_session(part_path)
				return result

			with patch("os.rename", rob_after_claim):
				with self.assertRaisesRegex(frappe.ValidationError, "no data"):
					finish_upload_to_blob(upload_id)

			# the claim was still released
			self.assertEqual(self.session_files(upload_id), set())

	# ---- upload sessions: file adoption hook ----

	def test_both_upload_routes_run_the_file_adoption_hook_once(self):
		from frappe.handler import upload_file

		adopted_name = f"adopted-{frappe.generate_hash(length=10)}.txt"
		calls, observed = [], []

		def adopt(*, doc):
			calls.append(doc)
			observed.append((doc.is_new(), bool(frappe.db.exists("File", {"blob": doc.blob}))))
			doc.file_name = adopted_name
			return doc

		with storage_v2(), frappe.storage.fake(), hook_value("after_file_upload", [adopt]):
			content = unique_bytes(b"file adoption hook ")
			upload_id = self.open_session("before-hook.txt", len(content))
			self.send_chunk(upload_id, 0, content)
			file = finish_upload(upload_id)
			self.assertEqual(observed, [(True, False)])
			# the hook's mutation is saved
			self.assertEqual(file.file_name, adopted_name)
			self.assertEqual(frappe.db.get_value("File", file.name, "file_name"), adopted_name)

			content = unique_bytes(b"legacy upload ")
			set_request(
				method="POST",
				path="/api/method/upload_file",
				data={"file": (io.BytesIO(content), "legacy.txt")},
			)
			legacy_file = upload_file()

		self.assertEqual(len(calls), 2)
		self.assertIs(calls[0], file)
		self.assertIs(calls[1], legacy_file)

	def test_finish_upload_propagates_hook_failure_for_transaction_rollback(self):
		file_name = f"failure-{frappe.generate_hash(length=10)}.txt"
		marker = f"file-hook-{frappe.generate_hash(length=12)}"

		def fail_after_writing(*, doc):
			frappe.get_doc(doctype="ToDo", description=marker).insert()
			raise RuntimeError("file adoption failed")

		content = unique_bytes(b"failing file adoption hook ")
		frappe.db.savepoint("file_upload_hook_failure")
		try:
			with storage_v2(), frappe.storage.fake(), hook_value("after_file_upload", [fail_after_writing]):
				upload_id = self.open_session(file_name, len(content))
				self.send_chunk(upload_id, 0, content)
				with self.assertRaisesRegex(RuntimeError, "file adoption failed"):
					finish_upload(upload_id)
				self.assertFalse(frappe.db.exists("File", {"file_name": file_name}))
		finally:
			frappe.db.rollback(save_point="file_upload_hook_failure")

		self.assertFalse(frappe.db.exists("ToDo", {"description": marker}))

	# ---- upload sessions: stale sweep ----

	def test_expire_removes_stale_and_unreadable_sessions_only(self):
		with storage_v2(), frappe.storage.fake():
			stale_id = self.open_session("stale.txt", 10)
			fresh_id = self.open_session("fresh.txt", 10)
			self.backdate(*get_session_paths(stale_id))

			corrupt_id = frappe.generate_hash(length=20)
			self._sessions.append(corrupt_id)
			meta_path, part_path = get_session_paths(corrupt_id)
			# nosemgrep
			with open(meta_path, "w") as f:
				f.write("{ not json")
			open(part_path, "wb").close()
			self.backdate(meta_path, part_path)

			# a meta file whose timestamp cannot be read
			uploads_dir = get_uploads_dir()
			broken = os.path.join(uploads_dir, f"{frappe.generate_hash(length=20)}.meta")
			os.symlink(os.path.join(uploads_dir, "does-not-exist"), broken)
			self.addCleanup(delete_session, broken)

			self.assertGreaterEqual(expire_stale_upload_sessions(max_age_hours=24), 3)
			self.assertEqual(self.session_files(stale_id), set())
			self.assertEqual(self.session_files(corrupt_id), set())
			self.assertFalse(os.path.lexists(broken))
			self.assertEqual(self.session_files(fresh_id), {"meta", "part"})

	def test_expire_deletes_stale_direct_upload_objects(self):
		with storage_v2(), use_driver(DirectTargetDriver()) as driver:
			upload_id = self.open_session("stale-direct.txt", 10, mode="direct")
			driver.write(f"uploads/{upload_id}", io.BytesIO(b"x" * 10), is_private=True)
			self.backdate(get_session_paths(upload_id)[0])

			self.assertGreaterEqual(expire_stale_upload_sessions(max_age_hours=24), 1)
			self.assertEqual(self.session_files(upload_id), set())
			self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))

		# an unreachable bucket does not keep the local session alive
		with storage_v2(), use_driver(UndeletableDirectDriver()):
			upload_id = self.open_session("unreachable.txt", 10, mode="direct")
			self.backdate(get_session_paths(upload_id)[0])

			self.assertGreaterEqual(expire_stale_upload_sessions(max_age_hours=24), 1)
			self.assertEqual(self.session_files(upload_id), set())


class TestUploadChunkRouting(FrappeAPITestCase):
	"""PUT .../upload_chunk through the real WSGI pipeline (frappe.app.application).

	init_request matches streaming_request_paths against the routed path, and
	/api/v2/method/... reaches upload_chunk through a different Werkzeug Rule
	than the form the hook declares. A path-matching regression does not raise:
	make_form_dict drains the stream first, so the chunk silently gets zero bytes.
	"""

	def setUp(self):
		super().setUp()
		self._sessions = []

	def tearDown(self):
		for upload_id in self._sessions:
			delete_session(*get_session_paths(upload_id))
		super().tearDown()

	def open_session(self, filename: str, size: int, user: str = "Administrator") -> str:
		with storage_v2():
			frappe.set_user(user)
			upload_id = create_upload(filename, size)["upload_id"]
			frappe.set_user("Administrator")
		self._sessions.append(upload_id)
		return upload_id

	def put_chunk(
		self, endpoint: str, upload_id: str, data: bytes, headers: dict | None = None
	) -> TestResponse:
		auth = {} if headers else {"sid": self.sid}
		query = urlencode({"upload_id": upload_id, "offset": 0, **auth})
		# the request thread calls frappe.init() afresh, so the flag must come
		# from get_site_config, not from this thread's storage_v2() override
		configured = frappe._dict({**frappe.get_site_config(), "storage_v2": 1})
		with patch("frappe.config.get_site_config", return_value=configured):
			return make_request(
				target=self.TEST_CLIENT.open,
				args=(f"{endpoint}?{query}",),
				kwargs={
					"method": "PUT",
					"data": data,
					"content_type": "application/octet-stream",
					"headers": headers,
				},
			)

	def test_every_api_mount_receives_the_full_chunk_bounded_by_the_session_size(self):
		v2 = "/api/v2/method/frappe.storage.upload.upload_chunk"
		v1 = "/api/v1/method/frappe.storage.upload.upload_chunk"
		# v2 returns the value under "data", v1 under "message"
		for endpoint, key in ((v2, "data"), (v1, "message")):
			with self.subTest(endpoint=endpoint):
				response = self.put_chunk(endpoint, self.open_session("route.bin", 10), b"abcdefghij")
				self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
				self.assertEqual(response.json[key]["received"], 10)

		# the generic per-request cap is lifted, so the declared size must catch this
		response = self.put_chunk(v2, self.open_session("cap.bin", 4), b"too-long-a-chunk")
		self.assertEqual(response.status_code, 417, response.get_data(as_text=True))

	def test_bearer_authenticated_chunk_receives_the_full_body(self):
		# bearer auth runs before the handler and must leave the streaming body unread
		from frappe.integrations.doctype.oauth_bearer_token.test_oauth_bearer_token import (
			make_oauth_client,
		)

		user = "test1@example.com"
		upload_id = self.open_session("bearer-route.txt", 10, user=user)
		access_token = frappe.generate_hash()
		client = make_oauth_client()
		token = frappe.get_doc(
			{
				"doctype": "OAuth Bearer Token",
				"client": client.name,
				"user": user,
				"access_token": access_token,
				"expires_in": 3600,
				"scopes": "all openid",
				"status": "Active",
			}
		).insert(ignore_permissions=True)
		# the request opens its own connection, so the token must be committed
		frappe.db.commit()  # nosemgrep
		self.addCleanup(frappe.db.commit)
		self.addCleanup(frappe.delete_doc, "OAuth Client", client.name, force=1, ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "OAuth Bearer Token", token.name, force=1, ignore_permissions=True)

		response = self.put_chunk(
			"/api/v2/method/frappe.storage.upload.upload_chunk",
			upload_id,
			b"abcdefghij",
			headers={"Authorization": f"Bearer {access_token}"},
		)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		self.assertEqual(response.json["data"]["received"], 10)
