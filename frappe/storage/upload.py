# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Blob upload sessions for Storage v2: open, send chunks or upload direct, finish.

Trusted server API, not whitelisted: the caller authorizes the destination.
Sessions live in ``private/files/.uploads/``. See ``SPEC.md`` ("Upload").
"""

import json
import os
import re
import time
from typing import TYPE_CHECKING

import frappe
import frappe.storage
from frappe import _
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError
from frappe.storage.driver import get_driver
from frappe.utils import cint

if TYPE_CHECKING:
	from frappe.core.doctype.file_blob.file_blob import FileBlob

UPLOADS_DIR = ".uploads"
UPLOAD_ID_PATTERN = re.compile(r"[A-Za-z0-9]+")
FINISHING_SUFFIX = ".finishing"


def create_blob_upload(filename: str, size: int, *, is_private: bool = True) -> dict:
	"""Open a session bound to the current user. Checks the size before any byte lands."""
	check_enabled()
	size = cint(size)
	check_declared_size(size)

	upload_id = frappe.generate_hash(length=20)
	native = get_driver().upload_target(upload_key(upload_id), size, is_private=bool(is_private))
	mode = "direct" if native else "chunked"

	save_session_meta(
		upload_id,
		{
			"mode": mode,
			"filename": filename,
			"size": size,
			"is_private": cint(is_private),
			"owner": frappe.session.user,
			"created_at": int(time.time()),
		},
	)
	if native:
		return {"mode": "direct", "upload_id": upload_id, **native}
	return {"mode": "chunked", "upload_id": upload_id}


def upload_blob_chunk(upload_id: str, offset: int, data: bytes) -> dict:
	"""Write ``data`` at ``offset``. A retried chunk is fine; a hole or an oversize write is not."""
	check_enabled()
	meta, meta_path, part_path = load_session(upload_id)
	if meta.get("mode") == "direct":
		frappe.throw(_("This upload session expects a direct upload, not chunks"))

	offset = cint(offset)
	if offset < 0 or offset > session_size(part_path):
		frappe.throw(_("Invalid chunk offset"))

	if offset + len(data) > cint(meta.get("size")):
		delete_session(meta_path, part_path)
		frappe.throw(_("Upload exceeds the declared file size"))

	with open_session_part(part_path, write=True) as f:
		f.seek(offset)
		f.write(data)

	return {"upload_id": upload_id, "received": session_size(part_path)}


def finish_upload_to_blob(upload_id: str, *, checksum: str | None = None) -> "FileBlob":
	"""Store the session's bytes as a blob and drop the session. Creates no File row."""
	from frappe.storage.blob import put_blob, validate_upload

	check_enabled()
	meta, meta_path, part_path = load_session(upload_id)
	filename = meta.get("filename")
	is_private = bool(cint(meta.get("is_private")))
	direct = meta.get("mode") == "direct"
	# fail before the claim, so the client can still send the bytes and retry
	if not has_session_data(upload_id, meta, part_path):
		frappe.throw(_("Upload session has no data"))

	# a single winner when two finishes race on one session
	meta_path = claim_session(meta_path)

	try:
		if direct:
			blob = store_direct_upload(upload_id, is_private=is_private, filename=filename)
		else:
			with open_session_part(part_path) as stream:
				blob = put_blob(stream, is_private=is_private, filename=filename)

		if blob.file_size == 0:
			frappe.throw(_("Upload session has no data"))
		if blob.file_size > cint(meta.get("size")):
			frappe.throw(_("Upload exceeds the declared file size"))
		if checksum and blob.checksum != checksum:
			frappe.throw(_("Checksum mismatch"))

		validate_upload(blob, filename)
		return blob
	finally:
		delete_session(meta_path, part_path)


def has_session_data(upload_id: str, meta: dict, part_path: str) -> bool:
	if meta.get("mode") == "direct":
		return get_driver().exists(upload_key(upload_id), is_private=bool(cint(meta.get("is_private"))))
	return session_size(part_path) > 0


def store_direct_upload(upload_id: str, *, is_private: bool, filename: str | None) -> "FileBlob":
	"""Copy a direct (browser -> bucket) upload into a blob, then delete the temporary object."""
	from frappe.storage.blob import put_blob

	driver = get_driver()
	temp_key = upload_key(upload_id)
	try:
		stream = driver.read(temp_key, is_private=is_private)
	except FileNotFoundError:
		frappe.throw(_("Upload session has no data"))

	try:
		with stream:
			return put_blob(stream, is_private=is_private, filename=filename)
	finally:
		try:
			driver.delete(temp_key, is_private=is_private)
		except Exception:
			frappe.logger("storage").warning(
				f"storage: could not delete finished direct upload {temp_key}", exc_info=True
			)


def expire_stale_upload_sessions(max_age_hours: int = 24) -> int:
	"""Delete sessions untouched for ``max_age_hours``, with their direct-upload objects.

	Return the count removed."""
	uploads_dir = frappe.get_site_path("private", "files", UPLOADS_DIR)
	if not os.path.isdir(uploads_dir):
		return 0

	cutoff = time.time() - max_age_hours * 3600
	removed = 0

	def mtime(path: str) -> float:
		try:
			return os.path.getmtime(path)
		except OSError:
			return 0.0

	sessions: dict[str, list[str]] = {}
	for entry in os.listdir(uploads_dir):
		upload_id = entry.split(".", 1)[0]
		sessions.setdefault(upload_id, []).append(os.path.join(uploads_dir, entry))

	for upload_id, paths in sessions.items():
		# an active session keeps touching one of its files
		if max(mtime(path) for path in paths) >= cutoff:
			continue
		delete_stale_driver_upload(upload_id, paths)
		delete_session(*paths)
		removed += 1

	return removed


def delete_stale_driver_upload(upload_id: str, paths: list[str]) -> None:
	"""Best effort: drop the driver-side temp object of a stale direct session."""
	meta = None
	for path in paths:
		if path.endswith((".meta", ".meta" + FINISHING_SUFFIX)):
			meta = read_session_meta(path)
			break
	if not meta or meta.get("mode") != "direct":
		return
	try:
		get_driver().delete(upload_key(upload_id), is_private=bool(cint(meta.get("is_private"))))
	except Exception:
		frappe.logger("storage").warning(
			f"storage: could not delete stale direct upload {upload_key(upload_id)}", exc_info=True
		)


def upload_key(upload_id: str) -> str:
	"""Driver key of a direct upload's temporary object, under the site prefix."""
	return f"{get_driver().key_prefix}uploads/{upload_id}"


def check_enabled():
	if not frappe.storage.enabled():
		frappe.throw(_("File Storage v2 is not enabled for this site"))


def check_declared_size(size: int):
	from frappe.core.api.file import get_max_file_size

	max_file_size = get_max_file_size()
	if size > max_file_size:
		frappe.throw(
			_("File size exceeded the maximum allowed size of {0} MB").format(max_file_size / 1048576),
			exc=MaxFileSizeReachedError,
		)


def get_uploads_dir() -> str:
	path = frappe.get_site_path("private", "files", UPLOADS_DIR)
	os.makedirs(path, exist_ok=True)
	return path


def get_session_paths(upload_id: str) -> tuple[str, str]:
	if not upload_id or not UPLOAD_ID_PATTERN.fullmatch(str(upload_id)):
		frappe.throw(_("Invalid upload id"))
	uploads_dir = get_uploads_dir()
	return (
		os.path.join(uploads_dir, f"{upload_id}.meta"),
		os.path.join(uploads_dir, f"{upload_id}.part"),
	)


def save_session_meta(upload_id: str, meta: dict):
	meta_path, part_path = get_session_paths(upload_id)
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
	with open(meta_path, "w") as f:
		json.dump(meta, f)
	if meta.get("mode") != "direct":
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		open(part_path, "wb").close()


def load_session(upload_id: str) -> tuple[dict, str, str]:
	"""Return the session's meta, meta path and part path. Only its owner may load it."""
	meta_path, part_path = get_session_paths(upload_id)
	# read without an existence check first: a concurrent finish may delete it
	meta = read_session_meta(meta_path)
	if meta is None:
		frappe.throw(_("Upload session not found or expired"))
	if meta.get("owner") != frappe.session.user:
		raise frappe.PermissionError
	return meta, meta_path, part_path


def read_session_meta(meta_path: str) -> dict | None:
	"""Return the session meta, or None when it is gone or unreadable. Logs unreadable files."""
	try:
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		with open(meta_path) as f:
			meta = json.load(f)
	except FileNotFoundError:
		return None
	except (OSError, ValueError):
		frappe.logger("storage").warning(f"storage: unreadable session meta {meta_path}", exc_info=True)
		return None
	if not isinstance(meta, dict):
		frappe.logger("storage").warning(f"storage: session meta {meta_path} is not an object")
		return None
	return meta


def session_size(part_path: str) -> int:
	"""Bytes received so far. Return 0 when the part file is gone."""
	try:
		return os.path.getsize(part_path)
	except FileNotFoundError:
		return 0
	except OSError:
		frappe.logger("storage").warning(f"storage: unreadable upload part {part_path}", exc_info=True)
		return 0


def open_session_part(part_path: str, *, write: bool = False):
	"""Open a session's part file without creating it. Throw when it is gone.

	A missing part file means the session is dead: a concurrent finish, an
	oversize chunk or the stale sweep removed it."""
	flags = os.O_RDWR if write else os.O_RDONLY
	try:
		# part_path is built by get_session_paths from an alphanumeric-only upload_id
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		fd = os.open(part_path, flags)
	except FileNotFoundError:
		frappe.throw(_("Upload session has no data"))
	except OSError:
		frappe.logger("storage").warning(f"storage: unreadable upload part {part_path}", exc_info=True)
		frappe.throw(_("Upload session has no data"))
	return os.fdopen(fd, "r+b" if write else "rb")


def claim_session(meta_path: str) -> str:
	"""Rename the meta file to claim the session for finishing. Return the claimed path."""
	claimed = meta_path + FINISHING_SUFFIX
	try:
		os.rename(meta_path, claimed)
	except OSError:
		frappe.throw(_("Upload session not found or expired"))
	return claimed


def delete_session(*paths: str):
	for path in paths:
		try:
			os.remove(path)
		except OSError:
			pass
