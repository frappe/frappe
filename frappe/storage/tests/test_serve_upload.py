# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import os
import tempfile
import time
from contextlib import contextmanager
from unittest.mock import patch

from werkzeug.exceptions import Forbidden, NotFound

import frappe
import frappe.storage
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError
from frappe.storage.blob import put_blob
from frappe.storage.local_driver import LocalDriver
from frappe.storage.memory_driver import MemoryDriver
from frappe.storage.serve import serve_file
from frappe.storage.tests import reset_file_controller
from frappe.storage.upload import (
	FINISHING_SUFFIX,
	claim_session,
	create_upload,
	delete_session,
	expire_stale_upload_sessions,
	finish_upload,
	get_session_paths,
	get_uploads_dir,
	upload_chunk,
)
from frappe.storage.url import make_signature
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request


@contextmanager
def flag_on():
	"""Enable storage_v2 in site conf for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf["storage_v2"] = 1
	reset_file_controller()
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_v2", None)
		else:
			frappe.conf["storage_v2"] = previous
		reset_file_controller()


@contextmanager
def flag_off():
	"""Disable storage_v2 in site conf for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf.pop("storage_v2", None)
	reset_file_controller()
	try:
		yield
	finally:
		if previous is not None:
			frappe.conf["storage_v2"] = previous
		reset_file_controller()


@contextmanager
def use_driver(driver):
	"""Swap the active storage driver for a custom one, like fake()."""
	previous = getattr(frappe.local, "storage_driver_override", None)
	frappe.local.storage_driver_override = driver
	try:
		yield driver
	finally:
		frappe.local.storage_driver_override = previous


class NativeUrlDriver(MemoryDriver):
	"""Driver that hands out its own download URLs, like S3 presigned GET."""

	def download_url(self, key, filename, expires_in, *, is_private=False):
		return f"https://cdn.example/{key}?name={filename}&ttl={expires_in}"


class XAccelDriver(MemoryDriver):
	"""Bytes in memory, registered under the local driver name.

	Lets the X-Accel-Redirect branch run without site files: that branch
	returns before any byte is read."""

	name = "local"


class TempLocalDriver(LocalDriver):
	"""LocalDriver rooted in a temp dir, so get_path never touches the site."""

	def __init__(self, root):
		self.root = root

	def get_blobs_dir(self, is_private: bool = False) -> str:
		path = os.path.join(self.root, "private" if is_private else "public", "files", "blobs")
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


class UndeletableDirectDriver(DirectTargetDriver):
	"""Driver whose delete always fails, like an unreachable bucket."""

	def delete(self, key, *, is_private=False):
		raise RuntimeError("bucket unreachable")


def response_body(response) -> bytes:
	# send_file responses use direct_passthrough; get_data() would raise
	return b"".join(response.response)


class TestServeUpload(IntegrationTestCase):
	"""GET /f/ serve route and the three-step upload flow.

	Uses fake() (MemoryDriver), so no blob bytes touch the site dirs.
	Upload session files land in private/files/.uploads and are removed
	in tearDown."""

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._sessions = []

	def tearDown(self):
		for upload_id in self._sessions:
			delete_session(*get_session_paths(upload_id))
		frappe.local.form_dict = frappe._dict()
		if hasattr(frappe.local, "request"):
			del frappe.local.request
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDown()

	# ---- helpers ----

	def serve(self, path: str, **query):
		set_request(method="GET", path=path)
		frappe.local.form_dict = frappe._dict(query)
		try:
			return serve_file(path)
		finally:
			frappe.local.form_dict = frappe._dict()
			if hasattr(frappe.local, "request"):
				del frappe.local.request

	def serve_with_headers(self, path: str, headers: dict, **query):
		set_request(method="GET", path=path, headers=headers)
		frappe.local.form_dict = frappe._dict(query)
		try:
			return serve_file(path)
		finally:
			frappe.local.form_dict = frappe._dict()
			if hasattr(frappe.local, "request"):
				del frappe.local.request

	def send_chunk_as_file(self, upload_id: str, offset: int, data: bytes):
		"""Send a chunk as a multipart "file" field instead of a raw body."""
		set_request(method="POST", path="/", data={"file": (io.BytesIO(data), "chunk.bin")})
		try:
			return upload_chunk(upload_id, offset)
		finally:
			if hasattr(frappe.local, "request"):
				del frappe.local.request

	def backdate(self, *paths: str, hours: float = 25):
		stamp = time.time() - hours * 3600
		for path in paths:
			os.utime(path, (stamp, stamp))

	def send_chunk(self, upload_id: str, offset: int, data: bytes):
		set_request(method="POST", path="/", data=data)
		try:
			return upload_chunk(upload_id, offset)
		finally:
			if hasattr(frappe.local, "request"):
				del frappe.local.request

	def open_session(self, filename: str, size: int, is_private=1) -> str:
		result = create_upload(filename, size, is_private=is_private)
		self.assertEqual(result["mode"], "chunked")
		upload_id = result["upload_id"]
		self._sessions.append(upload_id)
		return upload_id

	# ---- serve route ----

	def test_signed_url_serves_private_blob_without_session(self):
		with flag_on(), frappe.storage.fake():
			blob = put_blob(io.BytesIO(b"private signed content"), is_private=True)
			expires = int(time.time()) + 60
			sig = make_signature(blob.name, "a.txt", expires)

			frappe.set_user("Guest")
			response = self.serve(f"/f/{blob.name}/a.txt", e=str(expires), s=sig)

			self.assertEqual(response.status_code, 200)
			self.assertEqual(response_body(response), b"private signed content")

	def test_expired_or_tampered_signature_forbidden(self):
		with flag_on(), frappe.storage.fake():
			blob = put_blob(io.BytesIO(b"expiring content"), is_private=True)
			frappe.set_user("Guest")

			expired = int(time.time()) - 1
			sig = make_signature(blob.name, "a.txt", expired)
			with self.assertRaises(Forbidden):
				self.serve(f"/f/{blob.name}/a.txt", e=str(expired), s=sig)

			expires = int(time.time()) + 60
			sig = make_signature(blob.name, "a.txt", expires)
			tampered = sig[:-1] + ("0" if sig[-1] != "0" else "1")
			with self.assertRaises(Forbidden):
				self.serve(f"/f/{blob.name}/a.txt", e=str(expires), s=tampered)

			# signature for one filename must not open another
			with self.assertRaises(Forbidden):
				self.serve(f"/f/{blob.name}/b.txt", e=str(expires), s=sig)

			# no signature at all: private blob, Guest session
			with self.assertRaises(Forbidden):
				self.serve(f"/f/{blob.name}/a.txt")

	def test_public_blob_served_unsigned(self):
		with flag_on(), frappe.storage.fake():
			blob = put_blob(io.BytesIO(b"public content"), is_private=False)

			frappe.set_user("Guest")
			response = self.serve(f"/f/{blob.name}/pub.txt")

			self.assertEqual(response.status_code, 200)
			self.assertEqual(response_body(response), b"public content")

	def test_session_with_permission_serves(self):
		from frappe.core.doctype.file.file_v2 import create_file_from_blob

		with flag_on(), frappe.storage.fake():
			blob = put_blob(io.BytesIO(b"attached content"), is_private=True)
			file = create_file_from_blob(blob, "attached.txt", is_private=True)
			self.assertEqual(file.blob, blob.name)

			# Administrator session, no signature: File-row permission applies
			response = self.serve(f"/f/{blob.name}/attached.txt")

			self.assertEqual(response.status_code, 200)
			self.assertEqual(response_body(response), b"attached content")

	def test_no_permission_forbidden(self):
		with flag_on(), frappe.storage.fake():
			# private blob with no File row: nobody passes is_downloadable()
			blob = put_blob(io.BytesIO(b"unlinked content"), is_private=True)

			with self.assertRaises(Forbidden):
				self.serve(f"/f/{blob.name}/secret.txt")

	def test_unknown_blob_forbidden_like_denied_access(self):
		# same response as a permission failure: no blob-existence oracle
		with flag_on(), frappe.storage.fake():
			with self.assertRaises(Forbidden):
				self.serve("/f/does-not-exist/a.txt")

	def test_svg_forced_attachment(self):
		svg = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'
		with flag_on(), frappe.storage.fake():
			blob = put_blob(io.BytesIO(svg), is_private=False)

			frappe.set_user("Guest")
			response = self.serve(f"/f/{blob.name}/image.svg")

			self.assertEqual(response.status_code, 200)
			disposition = response.headers.get("Content-Disposition") or ""
			self.assertTrue(disposition.startswith("attachment"))

	def test_active_content_forced_attachment_regardless_of_filename(self):
		# the URL filename is caller-chosen; an HTML blob requested as x.txt
		# must not render inline on the site origin
		html = b"<!DOCTYPE html><html><body>" + frappe.generate_hash(length=16).encode() + b"</body></html>"
		with flag_on(), frappe.storage.fake():
			blob = put_blob(io.BytesIO(html), is_private=False)
			self.assertEqual(blob.mime_type, "text/html")

			frappe.set_user("Guest")
			response = self.serve(f"/f/{blob.name}/innocent.txt")

			self.assertEqual(response.status_code, 200)
			disposition = response.headers.get("Content-Disposition") or ""
			self.assertTrue(disposition.startswith("attachment"))

	# ---- upload sessions ----

	def test_create_upload_rejects_oversize_before_bytes(self):
		with flag_on(), frappe.storage.fake():
			with patch("frappe.core.api.file.get_max_file_size", return_value=1024):
				with self.assertRaises(MaxFileSizeReachedError):
					create_upload("big.bin", 2048)

	def test_chunked_roundtrip_creates_file_and_blob(self):
		with flag_on(), frappe.storage.fake() as store:
			content = b"0123456789" * 120
			upload_id = self.open_session("hello.txt", len(content), is_private=1)

			half = len(content) // 2
			first = self.send_chunk(upload_id, 0, content[:half])
			self.assertEqual(first["received"], half)
			second = self.send_chunk(upload_id, half, content[half:])
			self.assertEqual(second["received"], len(content))

			checksum = hashlib.sha256(content).hexdigest()
			file = finish_upload(upload_id, checksum=checksum, file_name="hello.txt")

			self.assertTrue(file.blob)
			blob = frappe.get_doc("File Blob", file.blob)
			self.assertEqual(blob.checksum, checksum)
			self.assertEqual(blob.file_size, len(content))
			self.assertTrue(store.exists(blob.key, is_private=True))

			meta_path, part_path = get_session_paths(upload_id)
			self.assertFalse(os.path.exists(meta_path))
			self.assertFalse(os.path.exists(part_path))

	def test_cumulative_size_violation_kills_session(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_session("small.txt", 10)

			with self.assertRaises(frappe.ValidationError):
				self.send_chunk(upload_id, 0, b"x" * 20)

			meta_path, part_path = get_session_paths(upload_id)
			self.assertFalse(os.path.exists(meta_path))
			self.assertFalse(os.path.exists(part_path))

			# the session is gone; further chunks are rejected
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk(upload_id, 0, b"x")

	def test_checksum_mismatch_throws(self):
		with flag_on(), frappe.storage.fake():
			content = b"checksum mismatch content"
			upload_id = self.open_session("sum.txt", len(content))
			self.send_chunk(upload_id, 0, content)

			self.assertRaises(
				frappe.ValidationError,
				finish_upload,
				upload_id,
				checksum="0" * 64,
				file_name="sum.txt",
			)

	def test_upload_session_bound_to_owner(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_session("owned.txt", 10)

			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				self.send_chunk(upload_id, 0, b"x")
			with self.assertRaises(frappe.PermissionError):
				finish_upload(upload_id, file_name="owned.txt")

	def test_guest_chunks_stop_when_guest_uploads_are_turned_off(self):
		"""Every guest is the same session user, so the owner check does not
		gate them. The permission check has to run per chunk."""
		with flag_on(), frappe.storage.fake():
			with self.change_settings("System Settings", allow_guests_to_upload_files=1):
				frappe.set_user("Guest")
				upload_id = self.open_session("guest.txt", 10)
				self.assertEqual(self.send_chunk(upload_id, 0, b"abc")["received"], 3)

			with self.assertRaises(frappe.PermissionError):
				self.send_chunk(upload_id, 3, b"def")

	def test_finish_upload_cannot_run_twice(self):
		with flag_on(), frappe.storage.fake():
			content = b"only one file row"
			upload_id = self.open_session("once.txt", len(content))
			self.send_chunk(upload_id, 0, content)

			file = finish_upload(upload_id, file_name="once.txt")
			self.addCleanup(
				frappe.delete_doc, "File", file.name, force=1, ignore_permissions=True, ignore_missing=True
			)
			self.assertTrue(file.blob)

			with self.assertRaises(frappe.ValidationError):
				finish_upload(upload_id, file_name="once.txt")
			self.assertEqual(frappe.db.count("File", {"blob": file.blob}), 1)

	def test_claim_session_has_a_single_winner(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_session("race.txt", 4)
			meta_path, _part_path = get_session_paths(upload_id)

			claimed = claim_session(meta_path)
			self.addCleanup(delete_session, claimed)

			with self.assertRaises(frappe.ValidationError):
				claim_session(meta_path)

	def test_guest_upload_restricted_to_legacy_mimetypes(self):
		with flag_on(), frappe.storage.fake():
			with self.change_settings("System Settings", {"allow_guests_to_upload_files": 1}):
				frappe.set_user("Guest")
				try:
					with self.assertRaises(frappe.ValidationError):
						create_upload("evil.html", 10)

					upload_id = self.open_session("ok.png", 10)
					self.send_chunk(upload_id, 0, b"x" * 10)
					# the finish-time file_name override is gated too
					with self.assertRaises(frappe.ValidationError):
						finish_upload(upload_id, file_name="evil.html")
				finally:
					frappe.set_user("Administrator")

	def test_direct_upload_roundtrip(self):
		content = b"direct upload bytes " + frappe.generate_hash(length=16).encode()

		class DirectDriver(MemoryDriver):
			def upload_target(self, key, size, *, is_private=False):
				return {"mode": "direct", "url": "http://bucket.example/upload"}

		with flag_on():
			driver = DirectDriver()
			previous = getattr(frappe.local, "storage_driver_override", None)
			frappe.local.storage_driver_override = driver
			try:
				result = create_upload("direct.txt", len(content), is_private=1)
				self.assertEqual(result["mode"], "direct")
				upload_id = result["upload_id"]
				self._sessions.append(upload_id)

				# chunks are rejected for direct sessions
				with self.assertRaises(frappe.ValidationError):
					self.send_chunk(upload_id, 0, b"x")

				# finishing before the browser uploaded fails, session survives
				with self.assertRaises(frappe.ValidationError):
					finish_upload(upload_id, file_name="direct.txt")

				# simulate the browser PUT to the native target
				driver.write(f"uploads/{upload_id}", io.BytesIO(content), is_private=True)

				file = finish_upload(upload_id, file_name="direct.txt")
				self.addCleanup(
					frappe.delete_doc,
					"File",
					file.name,
					force=1,
					ignore_permissions=True,
					ignore_missing=True,
				)
				blob = frappe.get_doc("File Blob", file.blob)
				self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
				self.assertTrue(driver.exists(blob.key, is_private=True))
				# the temporary object is gone
				self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))
			finally:
				frappe.local.storage_driver_override = previous

	def test_stale_session_expiry_removes_files(self):
		with flag_on(), frappe.storage.fake():
			stale_id = self.open_session("stale.txt", 10)
			fresh_id = self.open_session("fresh.txt", 10)

			stale_meta, stale_part = get_session_paths(stale_id)
			backdated = time.time() - 25 * 3600
			os.utime(stale_meta, (backdated, backdated))
			os.utime(stale_part, (backdated, backdated))

			removed = expire_stale_upload_sessions(max_age_hours=24)

			self.assertGreaterEqual(removed, 1)
			self.assertFalse(os.path.exists(stale_meta))
			self.assertFalse(os.path.exists(stale_part))

			fresh_meta, fresh_part = get_session_paths(fresh_id)
			self.assertTrue(os.path.exists(fresh_meta))
			self.assertTrue(os.path.exists(fresh_part))

	# ---- serve route: response modes ----

	def test_path_without_a_blob_name_is_not_found(self):
		with flag_on(), frappe.storage.fake():
			with self.assertRaises(NotFound):
				self.serve("/f/")
			with self.assertRaises(NotFound):
				self.serve("/files/some.txt")

	def test_driver_native_url_redirects(self):
		with flag_on(), use_driver(NativeUrlDriver()):
			blob = put_blob(io.BytesIO(b"native " + frappe.generate_hash(length=16).encode()))

			frappe.set_user("Guest")
			response = self.serve(f"/f/{blob.name}/n.txt")

			self.assertEqual(response.status_code, 302)
			location = response.headers["Location"]
			self.assertIn(blob.key, location)
			self.assertIn("name=n.txt", location)
			self.assertIn("ttl=60", location)

	def test_missing_blob_bytes_are_not_found(self):
		with flag_on(), frappe.storage.fake() as store:
			blob = put_blob(io.BytesIO(b"vanishing " + frappe.generate_hash(length=16).encode()))
			store.delete(blob.key, is_private=False)

			with self.assertRaises(NotFound):
				self.serve(f"/f/{blob.name}/gone.txt")

	def test_x_accel_redirect_for_private_blob(self):
		with flag_on(), use_driver(XAccelDriver()):
			blob = put_blob(
				io.BytesIO(b"accel private " + frappe.generate_hash(length=16).encode()),
				is_private=True,
			)
			self.assertEqual(blob.driver, "local")
			expires = int(time.time()) + 60
			sig = make_signature(blob.name, "report.pdf", expires)

			frappe.set_user("Guest")
			response = self.serve_with_headers(
				f"/f/{blob.name}/report.pdf",
				{"X-Use-X-Accel-Redirect": "1"},
				e=str(expires),
				s=sig,
			)

			private_path = frappe.local.conf.get("private_path", "private")
			self.assertEqual(
				response.headers["X-Accel-Redirect"],
				"/protected/" + os.path.join(private_path, "files", "blobs", blob.key),
			)
			self.assertEqual(response.headers["Accept-Ranges"], "bytes")
			self.assertEqual(response.headers["Content-Type"], "application/pdf")
			self.assertIn("private", response.headers["Cache-Control"])
			# a pdf is not active content: it stays inline
			self.assertIsNone(response.headers.get("Content-Disposition"))

	def test_x_accel_redirect_for_public_blob_forces_attachment(self):
		svg = (
			b'<svg xmlns="http://www.w3.org/2000/svg"><!--' + frappe.generate_hash(16).encode() + b"--></svg>"
		)
		with flag_on(), use_driver(XAccelDriver()):
			blob = put_blob(io.BytesIO(svg), is_private=False, filename="logo.svg")

			frappe.set_user("Guest")
			response = self.serve_with_headers(f"/f/{blob.name}/logo.svg", {"X-Use-X-Accel-Redirect": "1"})

			self.assertEqual(response.headers["X-Accel-Redirect"], "/files/blobs/" + blob.key)
			self.assertEqual(response.headers["Content-Type"], "image/svg+xml")
			self.assertEqual(
				response.headers["Content-Disposition"],
				"attachment; filename*=UTF-8''logo.svg",
			)

	def test_range_request_served_from_disk(self):
		root = tempfile.TemporaryDirectory()
		self.addCleanup(root.cleanup)
		with flag_on(), use_driver(TempLocalDriver(root.name)):
			content = (b"range " + frappe.generate_hash(length=16).encode()) * 8
			blob = put_blob(io.BytesIO(content), is_private=False, filename="data.bin")

			frappe.set_user("Guest")
			response = self.serve_with_headers(f"/f/{blob.name}/data.bin", {"Range": "bytes=5-14"})

			self.assertEqual(response.status_code, 206)
			self.assertEqual(response.headers["Content-Range"], f"bytes 5-14/{len(content)}")
			self.assertEqual(response_body(response), content[5:15])
			response.close()

	def test_local_blob_with_missing_file_is_not_found(self):
		root = tempfile.TemporaryDirectory()
		self.addCleanup(root.cleanup)
		with flag_on(), use_driver(TempLocalDriver(root.name)) as driver:
			content = b"deleted from disk " + frappe.generate_hash(length=16).encode()
			blob = put_blob(io.BytesIO(content), is_private=False, filename="data.bin")
			os.remove(driver.get_path(blob.key, False))

			frappe.set_user("Guest")
			with self.assertRaises(NotFound):
				self.serve(f"/f/{blob.name}/data.bin")

	# ---- upload sessions: guards ----

	def test_upload_endpoints_need_the_flag(self):
		with flag_off():
			with self.assertRaises(frappe.ValidationError):
				create_upload("off.txt", 10)
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk("doesnotmatter", 0, b"x")
			with self.assertRaises(frappe.ValidationError):
				finish_upload("doesnotmatter")

	def test_invalid_upload_id_rejected(self):
		with flag_on(), frappe.storage.fake():
			for upload_id in ("", "../../etc/passwd", "abc.def", "abc/def"):
				with self.assertRaises(frappe.ValidationError):
					get_session_paths(upload_id)
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk("../../etc/passwd", 0, b"x")

	def test_chunk_offset_must_not_leave_a_hole(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_session("holes.txt", 10)

			# nothing received yet: only offset 0 is valid
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk(upload_id, 5, b"x")
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk(upload_id, -1, b"x")

			self.assertEqual(self.send_chunk(upload_id, 0, b"abc")["received"], 3)
			# retrying an already received chunk is allowed
			self.assertEqual(self.send_chunk(upload_id, 0, b"abc")["received"], 3)
			# writing past the end of the part file is not
			with self.assertRaises(frappe.ValidationError):
				self.send_chunk(upload_id, 4, b"x")

	def test_chunk_accepts_a_multipart_file_field(self):
		with flag_on(), frappe.storage.fake():
			content = b"multipart chunk " + frappe.generate_hash(length=16).encode()
			upload_id = self.open_session("multi.txt", len(content))

			result = self.send_chunk_as_file(upload_id, 0, content)
			self.assertEqual(result["received"], len(content))

			file = finish_upload(
				upload_id,
				checksum=hashlib.sha256(content).hexdigest(),
				file_name="multi.txt",
			)
			self.addCleanup(
				frappe.delete_doc, "File", file.name, force=1, ignore_permissions=True, ignore_missing=True
			)
			self.assertEqual(frappe.get_doc("File Blob", file.blob).file_size, len(content))

	def test_finish_without_a_part_file_fails_and_keeps_the_session(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_session("nodata.txt", 10)
			meta_path, part_path = get_session_paths(upload_id)
			os.remove(part_path)

			with self.assertRaises(frappe.ValidationError):
				finish_upload(upload_id, file_name="nodata.txt")

			# the session was not claimed, so the client can still send bytes
			self.assertTrue(os.path.exists(meta_path))
			self.assertFalse(os.path.exists(meta_path + FINISHING_SUFFIX))

	def test_direct_upload_object_that_vanishes_before_the_read_fails(self):
		with flag_on(), use_driver(VanishingDirectDriver()):
			result = create_upload("gone.txt", 10, is_private=1)
			self.assertEqual(result["mode"], "direct")
			upload_id = result["upload_id"]
			self._sessions.append(upload_id)
			meta_path, _part_path = get_session_paths(upload_id)
			self.addCleanup(delete_session, meta_path + FINISHING_SUFFIX)

			# exists() passes the pre-flight check, read() then finds nothing
			with self.assertRaises(frappe.ValidationError):
				finish_upload(upload_id, file_name="gone.txt")

			self.assertEqual(frappe.db.count("File", {"file_name": "gone.txt"}), 0)

	def test_guest_uploads_limited_to_allowed_doctypes(self):
		with flag_on(), frappe.storage.fake():
			with self.change_settings(
				"System Settings",
				{
					"allow_guests_to_upload_files": 1,
					"allowed_doctypes_for_guest_uploads": "ToDo\n\nBlog Post\n",
				},
			):
				frappe.set_user("Guest")
				with self.assertRaises(frappe.PermissionError):
					create_upload("ok.png", 10, doctype="Contact", docname="new-contact-1")

				result = create_upload("ok.png", 10, doctype="ToDo", docname="new-todo-1")
				self._sessions.append(result["upload_id"])
				self.assertEqual(result["mode"], "chunked")

	# ---- upload sessions: stale sweep ----

	def test_expire_removes_a_session_with_an_unreadable_timestamp(self):
		with flag_on(), frappe.storage.fake():
			uploads_dir = get_uploads_dir()
			broken = os.path.join(uploads_dir, f"{frappe.generate_hash(length=20)}.meta")
			os.symlink(os.path.join(uploads_dir, "does-not-exist"), broken)
			self.addCleanup(delete_session, broken)

			removed = expire_stale_upload_sessions(max_age_hours=24)

			self.assertGreaterEqual(removed, 1)
			self.assertFalse(os.path.lexists(broken))

	def test_expire_tolerates_corrupt_session_meta(self):
		with flag_on(), frappe.storage.fake():
			upload_id = frappe.generate_hash(length=20)
			self._sessions.append(upload_id)
			meta_path, part_path = get_session_paths(upload_id)
			# nosemgrep
			with open(meta_path, "w") as f:
				f.write("{ not json")
			open(part_path, "wb").close()
			self.backdate(meta_path, part_path)

			removed = expire_stale_upload_sessions(max_age_hours=24)

			self.assertGreaterEqual(removed, 1)
			self.assertFalse(os.path.exists(meta_path))
			self.assertFalse(os.path.exists(part_path))

	def test_expire_deletes_the_stale_direct_upload_object(self):
		with flag_on(), use_driver(DirectTargetDriver()) as driver:
			result = create_upload("stale-direct.txt", 10, is_private=1)
			upload_id = result["upload_id"]
			self._sessions.append(upload_id)
			driver.write(f"uploads/{upload_id}", io.BytesIO(b"x" * 10), is_private=True)

			meta_path, _part_path = get_session_paths(upload_id)
			self.backdate(meta_path)

			removed = expire_stale_upload_sessions(max_age_hours=24)

			self.assertGreaterEqual(removed, 1)
			self.assertFalse(os.path.exists(meta_path))
			self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))

	def test_expire_survives_a_driver_delete_failure(self):
		with flag_on(), use_driver(UndeletableDirectDriver()):
			result = create_upload("unreachable.txt", 10, is_private=1)
			upload_id = result["upload_id"]
			self._sessions.append(upload_id)

			meta_path, _part_path = get_session_paths(upload_id)
			self.backdate(meta_path)

			# the bucket is unreachable; the local session still goes away
			removed = expire_stale_upload_sessions(max_age_hours=24)

			self.assertGreaterEqual(removed, 1)
			self.assertFalse(os.path.exists(meta_path))
