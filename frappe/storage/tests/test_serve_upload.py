# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import builtins
import hashlib
import io
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from threading import Barrier
from unittest.mock import patch
from urllib.parse import urlencode

from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.test import TestResponse

import frappe
import frappe.storage
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError
from frappe.storage.blob import put_blob
from frappe.storage.local_driver import LocalDriver
from frappe.storage.memory_driver import MemoryDriver
from frappe.storage.serve import serve_file, stream_blob
from frappe.storage.tests import reset_file_controller
from frappe.storage.upload import (
	BLOB_SESSION,
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
	load_session,
	upload_blob_chunk,
	upload_chunk,
)
from frappe.storage.url import make_signature
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import FrappeAPITestCase, make_request
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

	def backdate(self, *paths: str, hours: float = 25):
		stamp = time.time() - hours * 3600
		for path in paths:
			os.utime(path, (stamp, stamp))

	def send_chunk(self, upload_id: str, offset: int, data: bytes):
		# upload_chunk is PUT-only, raw body: see test_chunk_upload_route_is_put_only
		set_request(method="PUT", path="/", data=data)
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

	def open_blob_session(self, filename: str, size: int, is_private=True) -> str:
		result = create_blob_upload(filename, size, is_private=is_private)
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

	def test_finish_upload_runs_file_adoption_hook_before_insert_and_saves_mutation(self):
		content = b"file adoption hook " + frappe.generate_hash(length=16).encode()
		adopted_name = f"adopted-{frappe.generate_hash(length=10)}.txt"
		observed = []

		def adopt(*, doc):
			observed.append((doc.is_new(), bool(frappe.db.exists("File", {"blob": doc.blob}))))
			doc.file_name = adopted_name
			return doc

		original_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "after_file_upload":
				return [adopt]
			return original_get_hooks(hook, *args, **kwargs)

		with flag_on(), frappe.storage.fake(), patch.object(frappe, "get_hooks", side_effect=get_hooks):
			upload_id = self.open_session("before-hook.txt", len(content))
			self.send_chunk(upload_id, 0, content)
			file = finish_upload(upload_id)

		self.assertEqual(observed, [(True, False)])
		self.assertEqual(file.file_name, adopted_name)
		self.assertEqual(frappe.db.get_value("File", file.name, "file_name"), adopted_name)

	def test_finish_upload_propagates_hook_failure_for_transaction_rollback(self):
		content = b"failing file adoption hook " + frappe.generate_hash(length=16).encode()
		file_name = f"failure-{frappe.generate_hash(length=10)}.txt"
		marker = f"file-hook-{frappe.generate_hash(length=12)}"

		def fail_after_writing(*, doc):
			frappe.get_doc(doctype="ToDo", description=marker).insert()
			raise RuntimeError("file adoption failed")

		original_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "after_file_upload":
				return [fail_after_writing]
			return original_get_hooks(hook, *args, **kwargs)

		frappe.db.savepoint("file_upload_hook_failure")
		try:
			with flag_on(), frappe.storage.fake(), patch.object(
				frappe, "get_hooks", side_effect=get_hooks
			):
				upload_id = self.open_session(file_name, len(content))
				self.send_chunk(upload_id, 0, content)
				with self.assertRaisesRegex(RuntimeError, "file adoption failed"):
					finish_upload(upload_id)
				self.assertFalse(frappe.db.exists("File", {"file_name": file_name}))
		finally:
			frappe.db.rollback(save_point="file_upload_hook_failure")

		self.assertFalse(frappe.db.exists("ToDo", {"description": marker}))

	def test_legacy_upload_file_runs_file_adoption_hook_once(self):
		from frappe.handler import upload_file

		calls = []

		def adopt(*, doc):
			calls.append(doc)
			return doc

		original_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "after_file_upload":
				return [adopt]
			return original_get_hooks(hook, *args, **kwargs)

		content = b"legacy upload " + frappe.generate_hash(length=16).encode()
		with flag_on(), frappe.storage.fake(), patch.object(frappe, "get_hooks", side_effect=get_hooks):
			set_request(
				method="POST",
				path="/api/method/upload_file",
				data={"file": (io.BytesIO(content), "legacy.txt")},
			)
			file = upload_file()

		self.assertEqual(len(calls), 1)
		self.assertIs(calls[0], file)

	def test_trusted_chunked_roundtrip_creates_blob_without_file(self):
		hook_calls = []

		def adopt(*, doc):
			hook_calls.append(doc)
			return doc

		original_get_hooks = frappe.get_hooks

		def get_hooks(hook=None, *args, **kwargs):
			if hook == "after_file_upload":
				return [adopt]
			return original_get_hooks(hook, *args, **kwargs)

		with flag_on(), frappe.storage.fake() as store, patch.object(
			frappe, "get_hooks", side_effect=get_hooks
		):
			content = b"trusted blob upload " + frappe.generate_hash(length=16).encode()
			upload_id = self.open_blob_session("trusted.bin", len(content))

			first = upload_blob_chunk(upload_id, 0, content[:8])
			self.assertEqual(first["received"], 8)
			meta, _meta_path, _part_path = load_session(upload_id)
			self.assertEqual(meta["session_policy"], BLOB_SESSION)

			second = upload_blob_chunk(upload_id, 8, content[8:])
			self.assertEqual(second["received"], len(content))
			blob = finish_upload_to_blob(
				upload_id,
				checksum=hashlib.sha256(content).hexdigest(),
			)

			self.assertEqual(blob.file_size, len(content))
			self.assertEqual(frappe.db.count("File", {"blob": blob.name}), 0)
			self.assertEqual(hook_calls, [])
			self.assertTrue(store.exists(blob.key, is_private=True))
			meta_path, part_path = get_session_paths(upload_id)
			self.assertFalse(os.path.exists(meta_path))
			self.assertFalse(os.path.exists(part_path))

	def test_public_endpoints_reject_blob_only_sessions(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_blob_session("private.bin", 4)

			with self.assertRaises(frappe.ValidationError):
				self.send_chunk(upload_id, 0, b"data")
			with self.assertRaises(frappe.ValidationError):
				finish_upload(upload_id)

			# Rejection does not consume the session; the trusted path can finish it.
			upload_blob_chunk(upload_id, 0, b"data")
			blob = finish_upload_to_blob(upload_id)
			self.assertEqual(frappe.db.count("File", {"blob": blob.name}), 0)

	def test_trusted_endpoints_reject_file_sessions(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_session("public.txt", 4)

			with self.assertRaises(frappe.ValidationError):
				upload_blob_chunk(upload_id, 0, b"data")
			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)

	def test_trusted_upload_interfaces_are_not_http_whitelisted(self):
		self.assertNotIn(create_blob_upload, frappe.whitelisted)
		self.assertNotIn(upload_blob_chunk, frappe.whitelisted)
		self.assertNotIn(finish_upload_to_blob, frappe.whitelisted)

	def test_public_upload_cannot_choose_or_waive_session_policy(self):
		with flag_on(), frappe.storage.fake():
			with self.assertRaises(TypeError):
				create_upload("bypass.txt", 4, session_policy=BLOB_SESSION)
			with self.assertRaises(TypeError):
				create_upload("bypass.txt", 4, check_permission=False)
			with self.assertRaises(TypeError):
				create_upload("bypass.html", 4, restrict_mimetypes=False)

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

	def test_trusted_cumulative_size_violation_kills_session(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_blob_session("small.bin", 3)

			with self.assertRaises(frappe.ValidationError):
				upload_blob_chunk(upload_id, 0, b"four")

			meta_path, part_path = get_session_paths(upload_id)
			self.assertFalse(os.path.exists(meta_path))
			self.assertFalse(os.path.exists(part_path))

	def test_trusted_empty_session_is_retryable(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_blob_session("empty.bin", 10)

			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)

			meta_path, _part_path = get_session_paths(upload_id)
			self.assertTrue(os.path.exists(meta_path))
			upload_blob_chunk(upload_id, 0, b"data")
			blob = finish_upload_to_blob(upload_id)
			self.assertEqual(blob.file_size, 4)

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

	def test_trusted_checksum_failure_cleans_the_session(self):
		with flag_on(), frappe.storage.fake():
			content = b"trusted checksum mismatch"
			upload_id = self.open_blob_session("sum.txt", len(content))
			upload_blob_chunk(upload_id, 0, content)

			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id, checksum="0" * 64)

			meta_path, part_path = get_session_paths(upload_id)
			self.assertFalse(os.path.exists(meta_path))
			self.assertFalse(os.path.exists(meta_path + FINISHING_SUFFIX))
			self.assertFalse(os.path.exists(part_path))

	def test_trusted_finish_keeps_content_validation(self):
		with flag_on(), frappe.storage.fake():
			content = b"<html><script>bad()</script></html>"
			upload_id = self.open_blob_session("disguised.png", len(content))
			upload_blob_chunk(upload_id, 0, content)

			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)

			meta_path, part_path = get_session_paths(upload_id)
			self.assertFalse(os.path.exists(meta_path + FINISHING_SUFFIX))
			self.assertFalse(os.path.exists(part_path))

	def test_upload_session_bound_to_owner(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_session("owned.txt", 10)

			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				self.send_chunk(upload_id, 0, b"x")
			with self.assertRaises(frappe.PermissionError):
				finish_upload(upload_id, file_name="owned.txt")

	def test_trusted_upload_session_bound_to_owner(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_blob_session("owned.bin", 10)

			frappe.set_user("Guest")
			with self.assertRaises(frappe.PermissionError):
				upload_blob_chunk(upload_id, 0, b"x")
			with self.assertRaises(frappe.PermissionError):
				finish_upload_to_blob(upload_id)

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

	def test_trusted_finish_cannot_run_twice(self):
		with flag_on(), frappe.storage.fake():
			content = b"only one trusted finish"
			upload_id = self.open_blob_session("once.bin", len(content))
			upload_blob_chunk(upload_id, 0, content)

			blob = finish_upload_to_blob(upload_id)
			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)

			self.assertEqual(frappe.db.count("File Blob", {"name": blob.name}), 1)
			self.assertEqual(frappe.db.count("File", {"blob": blob.name}), 0)

	def test_concurrent_session_claim_has_a_single_winner(self):
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_session("race.txt", 4)
			meta_path, _part_path = get_session_paths(upload_id)
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

			winners = [claimed for claimed in results if claimed]
			self.assertEqual(len(winners), 1)
			self.addCleanup(delete_session, winners[0])

	def test_finish_refuses_a_session_consumed_while_it_is_read(self):
		"""The winner of a finish race deletes the session while the loser is
		still reading its meta file. The loser has to see the stable session
		error, not the raw OSError of the vanished file."""
		content = b"one winner only"
		with flag_on(), frappe.storage.fake():
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

			# the loser claimed nothing and left no session artifact behind
			self.assertFalse(os.path.exists(meta_path + FINISHING_SUFFIX))
			self.assertFalse(os.path.exists(meta_path))

	def test_finish_refuses_a_session_whose_part_vanishes_after_the_claim(self):
		"""Claiming the session does not pin the part file. A concurrent chunk
		write that overruns the declared size deletes it, so the finisher has to
		see the stable session error, not the raw OSError of the vanished part."""
		content = b"claimed then robbed"
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_blob_session("robbed.bin", len(content))
			upload_blob_chunk(upload_id, 0, content)
			meta_path, part_path = get_session_paths(upload_id)
			real_rename = os.rename

			def rob_after_claim(src, dst, *args, **kwargs):
				result = real_rename(src, dst, *args, **kwargs)
				if src == meta_path:
					# stands in for a concurrent oversize chunk write
					delete_session(part_path)
				return result

			with patch("os.rename", rob_after_claim):
				with self.assertRaisesRegex(frappe.ValidationError, "no data"):
					finish_upload_to_blob(upload_id)

			# the claim was still released, so nothing survives the failure
			self.assertFalse(os.path.exists(meta_path + FINISHING_SUFFIX))
			self.assertFalse(os.path.exists(part_path))

	def test_finish_refuses_a_vanished_part_before_claiming_the_session(self):
		"""The no-data check runs before the claim, so a session whose part file
		is gone stays unclaimed and the client can retry it."""
		content = b"bytes that go missing"
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_blob_session("missing.bin", len(content))
			upload_blob_chunk(upload_id, 0, content)
			meta_path, part_path = get_session_paths(upload_id)
			delete_session(part_path)

			with self.assertRaisesRegex(frappe.ValidationError, "no data"):
				finish_upload_to_blob(upload_id)

			self.assertFalse(os.path.exists(meta_path + FINISHING_SUFFIX))
			self.assertTrue(os.path.exists(meta_path))

	def test_chunk_write_refuses_a_session_whose_part_is_already_gone(self):
		"""A finish that consumed the session deleted its part file. A chunk
		still in flight has to refuse: re-creating the file would resurrect a
		dead session and report bytes as received that no finish ever reads."""
		content = b"written after the end"
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_blob_session("resurrected.bin", len(content))
			_meta_path, part_path = get_session_paths(upload_id)
			# stands in for the winner's delete_session in _finish_upload_to_blob
			delete_session(part_path)

			with self.assertRaisesRegex(frappe.ValidationError, "no data"):
				upload_blob_chunk(upload_id, 0, content)

			self.assertFalse(os.path.exists(part_path))

	def test_chunk_write_resumes_without_truncating_earlier_bytes(self):
		"""Opening the part file without an existence probe must still append
		to an in-progress session rather than restart it."""
		first, second = b"first half ", b"second half"
		with flag_on(), frappe.storage.fake():
			upload_id = self.open_blob_session("resumed.bin", len(first) + len(second))
			_meta_path, part_path = get_session_paths(upload_id)

			self.assertEqual(upload_blob_chunk(upload_id, 0, first)["received"], len(first))
			result = upload_blob_chunk(upload_id, len(first), second)

			self.assertEqual(result["received"], len(first) + len(second))
			with open(part_path, "rb") as f:
				self.assertEqual(f.read(), first + second)

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

	def test_trusted_create_skips_legacy_permission_and_filename_mime_gates(self):
		content = b"trusted opaque content"
		with flag_on(), frappe.storage.fake():
			frappe.set_user("Guest")
			try:
				upload_id = self.open_blob_session("trusted.html", len(content))
				upload_blob_chunk(upload_id, 0, content)
				blob = finish_upload_to_blob(upload_id)
				self.assertEqual(blob.file_size, len(content))
				self.assertEqual(frappe.db.count("File", {"blob": blob.name}), 0)
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

	def test_trusted_direct_upload_finishes_to_blob_and_deletes_temporary_object(self):
		content = b"trusted direct bytes " + frappe.generate_hash(length=16).encode()
		with flag_on(), use_driver(DirectTargetDriver()) as driver:
			result = create_blob_upload("direct.bin", len(content))
			self.assertEqual(result["mode"], "direct")
			upload_id = result["upload_id"]
			self._sessions.append(upload_id)
			driver.write(f"uploads/{upload_id}", io.BytesIO(content), is_private=True)

			blob = finish_upload_to_blob(upload_id)

			self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
			self.assertEqual(frappe.db.count("File", {"blob": blob.name}), 0)
			self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))

	def test_trusted_direct_upload_enforces_declared_size(self):
		with flag_on(), use_driver(DirectTargetDriver()) as driver:
			result = create_blob_upload("oversize.bin", 3)
			upload_id = result["upload_id"]
			self._sessions.append(upload_id)
			driver.write(f"uploads/{upload_id}", io.BytesIO(b"four"), is_private=True)

			with self.assertRaises(frappe.ValidationError):
				finish_upload_to_blob(upload_id)

			meta_path, _part_path = get_session_paths(upload_id)
			self.assertFalse(os.path.exists(meta_path))
			self.assertFalse(os.path.exists(meta_path + FINISHING_SUFFIX))
			self.assertFalse(driver.exists(f"uploads/{upload_id}", is_private=True))

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

	def test_authorized_stream_uses_native_url_only_when_enabled(self):
		with flag_on(), use_driver(NativeUrlDriver()):
			content = b"dav native " + frappe.generate_hash(length=16).encode()
			blob = put_blob(io.BytesIO(content), is_private=True, filename="n.txt")
			set_request(method="GET", path="/dav/n.txt")

			response = stream_blob(blob, "n.txt")
			self.assertEqual(response.status_code, 200)
			self.assertEqual(response_body(response), content)
			response.close()

			with patch.dict(frappe.conf, {"drive_webdav_s3_redirect": 1}):
				response = stream_blob(blob, "n.txt")

			self.assertEqual(response.status_code, 302)
			self.assertIn(blob.key, response.headers["Location"])

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

	def test_range_request_served_from_non_local_driver(self):
		with flag_on(), frappe.storage.fake():
			content = b"0123456789abcdefghijklmnopqrstuvwxyz"
			blob = put_blob(io.BytesIO(content), is_private=True, filename="data.bin")
			set_request(method="GET", path="/dav/data.bin", headers={"Range": "bytes=5-14"})

			response = stream_blob(blob, "data.bin")

			self.assertEqual(response.status_code, 206)
			self.assertEqual(response.headers["Content-Range"], f"bytes 5-14/{len(content)}")
			self.assertEqual(response.headers["Accept-Ranges"], "bytes")
			self.assertEqual(response_body(response), content[5:15])
			response.close()

	def test_open_ended_range_returns_tail(self):
		with flag_on(), frappe.storage.fake():
			content = b"0123456789abcdefghijklmnopqrstuvwxyz"
			blob = put_blob(io.BytesIO(content), is_private=True, filename="data.bin")
			set_request(method="GET", path="/dav/data.bin", headers={"Range": "bytes=20-"})

			response = stream_blob(blob, "data.bin")

			self.assertEqual(response.status_code, 206)
			self.assertEqual(response.headers["Content-Range"], f"bytes 20-35/{len(content)}")
			self.assertEqual(response_body(response), content[20:])
			response.close()

	def test_unsatisfiable_range_returns_416(self):
		with flag_on(), frappe.storage.fake():
			content = b"short content"
			blob = put_blob(io.BytesIO(content), is_private=True, filename="data.bin")
			set_request(method="GET", path="/dav/data.bin", headers={"Range": "bytes=100-200"})

			response = stream_blob(blob, "data.bin")

			self.assertEqual(response.status_code, 416)
			self.assertEqual(response.headers["Content-Range"], f"bytes */{len(content)}")
			self.assertEqual(response_body(response), b"")

	def test_matching_etag_returns_304_without_reading_driver(self):
		with flag_on(), frappe.storage.fake() as store:
			blob = put_blob(io.BytesIO(b"conditional content"), is_private=True, filename="data.bin")
			set_request(method="GET", path="/dav/data.bin", headers={"If-None-Match": f'"{blob.checksum}"'})

			with patch.object(store, "read") as read, patch.object(store, "read_range") as read_range:
				response = stream_blob(blob, "data.bin")

			self.assertEqual(response.status_code, 304)
			self.assertEqual(response.headers["ETag"], f'"{blob.checksum}"')
			read.assert_not_called()
			read_range.assert_not_called()

	def test_stream_blob_skips_permission_and_access_log(self):
		with flag_on(), frappe.storage.fake():
			content = b"already authorized"
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

	def test_chunk_refuses_form_encoded_bodies_without_buffering_them(self):
		# get_request_bytes must refuse by Content-Type alone, before Werkzeug's
		# form parser ever reads the socket: touching request.form/request.files
		# on a streaming request path (max_content_length lifted to None by
		# frappe/app.py:init_request) would otherwise spool an attacker-chosen
		# body of any size before the declared-size limit below is ever checked.
		huge_part = b"x" * (256 * 1024)
		cases = [
			("multipart/form-data", {"file": (io.BytesIO(huge_part), "huge.bin")}),
			("application/x-www-form-urlencoded", {"a": "x" * (256 * 1024)}),
		]
		for mimetype, data in cases:
			with self.subTest(mimetype=mimetype):
				set_request(method="PUT", path="/", data=data)
				frappe.local.request.max_content_length = None
				raw_input = frappe.local.request.environ["wsgi.input"]
				try:
					with self.assertRaises(frappe.ValidationError):
						get_request_bytes(limit=4)
					# never read: refused by the Content-Type header alone
					self.assertEqual(raw_input.tell(), 0)
				finally:
					del frappe.local.request

	def test_chunk_upload_route_is_put_only(self):
		# POST was dropped: init_request (frappe/app.py) only lifts the
		# make_form_dict/max_content_length treatment for a streaming request
		# path on a PUT (frappe.hooks.streaming_request_paths). A POST here
		# would still run make_form_dict first, which decodes the whole body
		# as text before the handler ever sees it - corrupting or crashing on
		# binary chunk data - and caps it at the generic upload size, not the
		# session's declared size. PUT is also the only contract the spec
		# documents for this route (frappe-file-storage-v2-spec.md: "PUT
		# /api/method/...upload_chunk").
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[upload_chunk], ("PUT",))

	def test_get_request_bytes_stops_reading_at_the_limit(self):
		# streaming request paths lift the generic per-request byte cap
		# (frappe/app.py:init_request), so get_request_bytes must bound its own
		# read: a limit must never let the full body land in memory.
		huge_body = b"x" * (64 * 1024)
		set_request(method="PUT", path="/", data=huge_body)
		try:
			data = get_request_bytes(limit=4)
		finally:
			del frappe.local.request

		self.assertEqual(data, b"xxxxx")  # limit + 1 bytes, never the full 64 KiB body

	def test_chunk_upload_route_is_a_registered_streaming_request_path(self):
		# frappe.storage.upload.upload_chunk must skip make_form_dict's
		# full-body buffering and the generic upload cap, or every chunk is
		# double-buffered and capped far below a session's declared size.
		self.assertIn(
			"/api/method/frappe.storage.upload.upload_chunk",
			frappe.get_hooks("streaming_request_paths"),
		)

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


class TestUploadChunkRouting(FrappeAPITestCase):
	"""PUT .../upload_chunk through the real WSGI pipeline (frappe.app.application).

	TestServeUpload.send_chunk calls upload_chunk() directly via set_request,
	which never runs frappe.app.init_request. That hides exactly the bug this
	guards against: init_request's streaming_request_paths match runs against
	the routed request path, and /api/v2/method/... reaches upload_chunk
	through a different Werkzeug Rule (frappe/api/v2.py) than the unversioned
	form the hook declares (frappe/hooks.py). A path-matching regression here
	does not raise - make_form_dict drains request.stream before upload_chunk
	ever reads it, so the chunk write silently receives zero bytes.
	"""

	def setUp(self):
		super().setUp()
		self._sessions = []

	def tearDown(self):
		for upload_id in self._sessions:
			delete_session(*get_session_paths(upload_id))
		super().tearDown()

	def open_session(self, filename: str, size: int) -> str:
		with flag_on():
			frappe.set_user("Administrator")
			result = create_upload(filename, size)
		self.assertEqual(result["mode"], "chunked")
		upload_id = result["upload_id"]
		self._sessions.append(upload_id)
		return upload_id

	def put_chunk(self, endpoint: str, upload_id: str, offset: int, data: bytes) -> TestResponse:
		query = urlencode({"upload_id": upload_id, "offset": offset, "sid": self.sid})
		# storage_v2 must read as enabled inside the request's own thread: it
		# calls frappe.init() fresh (frappe/app.py:init_request), which loads
		# frappe.local.conf from frappe.config.get_site_config, not from the
		# flag_on() override this test set in its own thread's frappe.local.
		configured = frappe._dict({**frappe.get_site_config(), "storage_v2": 1})
		with patch("frappe.config.get_site_config", return_value=configured):
			return make_request(
				target=self.TEST_CLIENT.open,
				args=(f"{endpoint}?{query}",),
				kwargs={"method": "PUT", "data": data, "content_type": "application/octet-stream"},
			)

	def test_v2_route_receives_the_full_chunk_body(self):
		upload_id = self.open_session("v2-route.bin", 10)
		response = self.put_chunk(
			"/api/v2/method/frappe.storage.upload.upload_chunk", upload_id, 0, b"abcdefghij"
		)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		# frappe.api.v2.handle_rpc_call returns its value directly, so
		# frappe.api.handle stores it under "data", not "message" (v1's key,
		# used below - it goes through frappe.handler.handle() instead).
		self.assertEqual(response.json["data"]["received"], 10)

	def test_v1_route_receives_the_full_chunk_body(self):
		upload_id = self.open_session("v1-route.bin", 10)
		response = self.put_chunk(
			"/api/v1/method/frappe.storage.upload.upload_chunk", upload_id, 0, b"abcdefghij"
		)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
		self.assertEqual(response.json["message"]["received"], 10)

	def test_v2_route_bounds_the_chunk_at_the_declared_session_size(self):
		# get_request_bytes(limit=meta["size"]) must be the read limit here,
		# not the generic per-request cap: init_request lifts that cap to None
		# for a streaming path, so only the session's own declared size can
		# still catch an oversized chunk.
		upload_id = self.open_session("v2-cap.bin", 4)
		response = self.put_chunk(
			"/api/v2/method/frappe.storage.upload.upload_chunk", upload_id, 0, b"too-long-a-chunk"
		)
		self.assertEqual(response.status_code, 417, response.get_data(as_text=True))
