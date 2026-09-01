# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import os
import time
from contextlib import contextmanager
from unittest.mock import patch

from werkzeug.exceptions import Forbidden, NotFound

import frappe
import frappe.storage
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError
from frappe.storage.blob import put_blob
from frappe.storage.serve import serve_file
from frappe.storage.upload import (
	create_upload,
	delete_session,
	expire_stale_upload_sessions,
	finish_upload,
	get_session_paths,
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
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_v2", None)
		else:
			frappe.conf["storage_v2"] = previous


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
		from frappe.core.doctype.file.file import create_file_from_blob

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

	def test_unknown_blob_not_found(self):
		with flag_on(), frappe.storage.fake():
			with self.assertRaises(NotFound):
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
