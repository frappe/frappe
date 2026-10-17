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

from werkzeug.exceptions import Forbidden, NotFound

import frappe
import frappe.storage
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError
from frappe.storage.blob import put_blob
from frappe.storage.local_driver import LocalDriver
from frappe.storage.memory_driver import MemoryDriver
from frappe.storage.serve import serve_private_file, serve_public_file, stream_blob
from frappe.storage.tests import (
	hook_value,
	storage_v2,
	unique_bytes,
	use_driver,
)
from frappe.storage.upload import (
	FINISHING_SUFFIX,
	claim_session,
	create_blob_upload,
	delete_session,
	expire_stale_upload_sessions,
	finish_upload_to_blob,
	get_session_paths,
	get_uploads_dir,
	upload_blob_chunk,
)
from frappe.storage.url import make_signature
from frappe.tests import IntegrationTestCase
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


class TestServeUpload(IntegrationTestCase):
	"""GET /files/ and /private/files/ serve routes and blob upload sessions.

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

	def open_session(self, filename: str, size: int, *, mode="chunked") -> str:
		result = create_blob_upload(filename, size)
		self.assertEqual(result["mode"], mode)
		self._sessions.append(result["upload_id"])
		return result["upload_id"]

	def attach_blob(self, blob, file_name: str):
		"""A File row linked to ``blob``, which grants access to a private blob."""
		folder = "/private/files" if blob.is_private else "/files"
		return frappe.get_doc(
			doctype="File", file_name=file_name, file_url=f"{folder}/{blob.name}/{file_name}"
		).insert(ignore_permissions=True)

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
			self.attach_blob(blob, "report.txt")
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
			self.attach_blob(private, "sign.png")
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
				create_blob_upload("off.txt", 10)
			with self.assertRaises(frappe.ValidationError):
				upload_blob_chunk("doesnotmatter", 0, b"x")
			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob("doesnotmatter")

		with storage_v2(), frappe.storage.fake():
			with patch("frappe.core.api.file.get_max_file_size", return_value=1024):
				with self.assertRaises(MaxFileSizeReachedError):
					create_blob_upload("big.bin", 2048)
			for upload_id in ("", "../../etc/passwd", "abc.def", "abc/def"):
				with self.subTest(upload_id=upload_id), self.assertRaises(frappe.ValidationError):
					get_session_paths(upload_id)
			with self.assertRaises(frappe.ValidationError):
				upload_blob_chunk("../../etc/passwd", 0, b"x")

	def test_upload_sessions_stay_off_http(self):
		import frappe.storage.upload

		self.assertEqual(
			[f for f in frappe.whitelisted if f.__module__ == frappe.storage.upload.__name__], []
		)

	# ---- upload sessions: flows ----

	def test_chunked_upload_creates_one_blob(self):
		with storage_v2(), frappe.storage.fake() as store:
			content = unique_bytes(b"chunked upload ") * 20
			half = len(content) // 2
			upload_id = self.open_session("hello.txt", len(content))

			# only an offset that leaves no hole is accepted
			for offset in (5, -1):
				with self.subTest(offset=offset), self.assertRaises(frappe.ValidationError):
					upload_blob_chunk(upload_id, offset, b"x")
			self.assertEqual(upload_blob_chunk(upload_id, 0, content[:half])["received"], half)
			# retrying a received chunk is allowed, writing past the end is not
			self.assertEqual(upload_blob_chunk(upload_id, 0, content[:half])["received"], half)
			with self.assertRaises(frappe.ValidationError):
				upload_blob_chunk(upload_id, half + 1, b"x")
			self.assertEqual(upload_blob_chunk(upload_id, half, content[half:])["received"], len(content))
			with open(get_session_paths(upload_id)[1], "rb") as f:
				self.assertEqual(f.read(), content)

			checksum = hashlib.sha256(content).hexdigest()
			blob = finish_upload_to_blob(upload_id, checksum=checksum)
			self.assertEqual((blob.checksum, blob.file_size), (checksum, len(content)))
			self.assertTrue(store.exists(blob.key, is_private=True))
			self.assertEqual(self.session_files(upload_id), set())

			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)

	def test_upload_creates_a_blob_without_file_gates_or_hooks(self):
		hook_calls = []

		def adopt(*, doc):
			hook_calls.append(doc)
			return doc

		content = unique_bytes(b"<!DOCTYPE html><html><body>")
		with storage_v2(), frappe.storage.fake(), hook_value("after_file_upload", [adopt]):
			# a Guest may open a session for an .html name: the caller authorizes it
			frappe.set_user("Guest")
			upload_id = self.open_session("trusted.html", len(content))
			upload_blob_chunk(upload_id, 0, content)
			blob = finish_upload_to_blob(upload_id)
			self.assertEqual(blob.file_size, len(content))
			self.assertEqual(frappe.db.count("File", {"blob": blob.name}), 0)
			self.assertEqual(hook_calls, [])

	def test_direct_upload_finishes_from_the_bucket_object(self):
		with storage_v2(), use_driver(DirectTargetDriver()) as driver:
			content = unique_bytes(b"direct upload bytes ")
			upload_id = self.open_session("direct.bin", len(content), mode="direct")
			with self.assertRaises(frappe.ValidationError):
				upload_blob_chunk(upload_id, 0, b"x")
			# finishing before the browser uploaded fails and keeps the session
			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)

			driver.write(f"uploads/{upload_id}", io.BytesIO(content), is_private=True)
			blob = finish_upload_to_blob(upload_id)
			self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
			self.assertTrue(driver.exists(blob.key, is_private=True))
			self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))

			upload_id = self.open_session("oversize.bin", 3, mode="direct")
			driver.write(f"uploads/{upload_id}", io.BytesIO(b"four"), is_private=True)
			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)
			self.assertEqual(self.session_files(upload_id), set())
			self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))

	def test_direct_upload_object_that_vanishes_before_the_read_fails(self):
		with storage_v2(), use_driver(VanishingDirectDriver()):
			upload_id = self.open_session("gone.txt", 10, mode="direct")
			# exists() passes the pre-flight check, read() then finds nothing
			with self.assertRaisesRegex(frappe.ValidationError, "no data"):
				finish_upload_to_blob(upload_id)
			self.assertEqual(self.session_files(upload_id), set())

	# ---- upload sessions: rules ----

	def test_session_rules(self):
		content = b"session rule bytes"
		failing_finishes = (
			(unique_bytes(b"checksum mismatch "), "sum.txt", "0" * 64),
			(b"<html><script>bad()</script></html>", "disguised.png", None),
		)
		with storage_v2(), frappe.storage.fake():
			with self.subTest(rule="bound to the owner"):
				upload_id = self.open_session("owned.bin", 10)
				with self.set_user("Guest"):
					with self.assertRaises(frappe.PermissionError):
						upload_blob_chunk(upload_id, 0, b"x")
					with self.assertRaises(frappe.PermissionError):
						finish_upload_to_blob(upload_id)

			with self.subTest(rule="an oversize chunk kills the session"):
				upload_id = self.open_session("small.bin", 3)
				with self.assertRaises(frappe.ValidationError):
					upload_blob_chunk(upload_id, 0, b"four")
				self.assertEqual(self.session_files(upload_id), set())
				with self.assertRaises(frappe.ValidationError):
					upload_blob_chunk(upload_id, 0, b"x")

			for failing_content, filename, checksum in failing_finishes:
				with self.subTest(rule="a failed finish drops the session", filename=filename):
					upload_id = self.open_session(filename, len(failing_content))
					upload_blob_chunk(upload_id, 0, failing_content)
					with self.assertRaises(frappe.ValidationError):
						finish_upload_to_blob(upload_id, checksum=checksum)
					self.assertEqual(self.session_files(upload_id), set())

			with self.subTest(rule="a finish without bytes is retryable"):
				upload_id = self.open_session("empty.bin", len(content))
				with self.assertRaisesRegex(frappe.ValidationError, "no data"):
					finish_upload_to_blob(upload_id)
				self.assertEqual(self.session_files(upload_id), {"meta", "part"})
				upload_blob_chunk(upload_id, 0, content)
				self.assertEqual(finish_upload_to_blob(upload_id).file_size, len(content))

			# a finish that consumed the session deleted its part file; a chunk
			# still in flight must not re-create it and report bytes nobody reads
			with self.subTest(rule="a session without its part file refuses work"):
				upload_id = self.open_session("missing.bin", len(content))
				upload_blob_chunk(upload_id, 0, content)
				delete_session(get_session_paths(upload_id)[1])
				# the no-data check runs before the claim, so the session stays unclaimed
				with self.assertRaisesRegex(frappe.ValidationError, "no data"):
					finish_upload_to_blob(upload_id)
				with self.assertRaisesRegex(frappe.ValidationError, "no data"):
					upload_blob_chunk(upload_id, 0, content)
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
			upload_id = self.open_session("race.bin", len(content))
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
			upload_id = self.open_session("robbed.bin", len(content))
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
