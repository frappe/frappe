# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Three-step upload flow for Storage v2.

1. ``create_upload``: permission and size checks, then a driver-native
   direct-upload target or a server-side chunked session.
2. ``upload_chunk``: append request bytes at an offset; cumulative size
   is enforced against the declared size on every chunk.
3. ``finish_upload``: spool the parts into a blob, verify the checksum,
   validate content, create the File row, drop the session.

Sessions live under ``sites/<site>/private/files/.uploads/`` as
``<upload_id>.meta`` (json) + ``<upload_id>.part`` (bytes). Stale
sessions are swept by ``expire_stale_upload_sessions`` (called from GC).
"""

import json
import mimetypes
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
FILE_SESSION = "file"
BLOB_SESSION = "blob"


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
def create_upload(
	filename: str,
	size: int,
	is_private: bool | int | str = 0,
	doctype: str | None = None,
	docname: str | None = None,
):
	"""Open an upload session. Checks permission and size before any byte lands."""
	check_enabled()
	check_upload_permission(doctype, docname)
	check_restricted_mimetypes(filename)
	return _create_upload(
		filename,
		size,
		is_private=is_private,
		session_policy=FILE_SESSION,
		doctype=doctype,
		docname=docname,
	)


def create_blob_upload(filename: str, size: int, *, is_private: bool = True) -> dict:
	"""Open a trusted blob-only upload session.

	The caller is responsible for authorizing its destination. This function is
	deliberately not HTTP-whitelisted and skips only the framework attachment
	permission and restricted-filename MIME gates.
	"""
	check_enabled()
	return _create_upload(
		filename,
		size,
		is_private=is_private,
		session_policy=BLOB_SESSION,
	)


def _create_upload(
	filename: str,
	size: int,
	*,
	is_private: bool | int | str,
	session_policy: str,
	doctype: str | None = None,
	docname: str | None = None,
) -> dict:
	"""Create a session whose File-versus-blob policy is chosen by its server wrapper."""

	size = cint(size)
	check_declared_size(size)

	upload_id = frappe.generate_hash(length=20)

	native = get_driver().upload_target(f"uploads/{upload_id}", size, is_private=bool(cint(is_private)))
	mode = "direct" if native else "chunked"

	save_session_meta(
		upload_id,
		{
			"mode": mode,
			"session_policy": session_policy,
			"filename": filename,
			"size": size,
			"is_private": cint(is_private),
			"doctype": doctype,
			"docname": docname,
			"owner": frappe.session.user,
			"created_at": int(time.time()),
		},
	)
	if native:
		return {"mode": "direct", "upload_id": upload_id, **native}
	return {"mode": "chunked", "upload_id": upload_id}


@frappe.whitelist(allow_guest=True, methods=["POST", "PUT"])  # nosemgrep: guest-whitelisted-method
def upload_chunk(upload_id: str, offset: int | str = 0):
	"""Write the request body into the session's part file at ``offset``.

	The cumulative size must stay within the declared size; a violation
	deletes the session. Re-sending an already received chunk is allowed
	(idempotent retry), writing past the end of the part file is not."""
	check_enabled()
	meta, meta_path, part_path = load_session(upload_id)
	require_session_policy(meta, FILE_SESSION)
	# re-checked per chunk, not only at create_upload: the session outlives
	# the request that opened it, and every guest is the same session user,
	# so the owner check in load_session does not gate guests on its own
	check_upload_permission(meta.get("doctype"), meta.get("docname"))
	return _write_upload_chunk(upload_id, offset, get_request_bytes(), meta, meta_path, part_path)


def upload_blob_chunk(upload_id: str, offset: int, data: bytes) -> dict:
	"""Append bytes to a trusted blob-only session after caller authorization.

	This ordinary Python interface is deliberately not HTTP-whitelisted.
	"""
	check_enabled()
	meta, meta_path, part_path = load_session(upload_id)
	require_session_policy(meta, BLOB_SESSION)
	return _write_upload_chunk(upload_id, offset, data, meta, meta_path, part_path)


def _write_upload_chunk(
	upload_id: str,
	offset: int | str,
	data: bytes,
	meta: dict,
	meta_path: str,
	part_path: str,
) -> dict:
	"""Write one chunk for either public File or trusted blob sessions."""
	if meta.get("mode") == "direct":
		frappe.throw(_("This upload session expects a direct upload, not chunks"))

	offset = cint(offset)
	received = session_size(part_path)
	if offset < 0 or offset > received:
		frappe.throw(_("Invalid chunk offset"))

	if offset + len(data) > cint(meta.get("size")):
		delete_session(meta_path, part_path)
		frappe.throw(_("Upload exceeds the declared file size"))

	# save_session_meta creates the part file with the session, so a missing one
	# means a concurrent finish already consumed it. Open it in one call and
	# refuse: probing first would raise, and re-creating it would resurrect a
	# dead session and report bytes as received that nobody will ever read.
	with open_session_part(part_path, write=True) as f:
		f.seek(offset)
		f.write(data)

	return {"upload_id": upload_id, "received": session_size(part_path)}


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
def finish_upload(
	upload_id: str,
	checksum: str | None = None,
	file_name: str | None = None,
	doctype: str | None = None,
	docname: str | None = None,
	fieldname: str | None = None,
	is_private: bool | int | str | None = None,
):
	"""Turn a finished session into a blob and a File row.

	Arguments override the values declared at ``create_upload``; anything
	not passed falls back to the session meta."""
	check_enabled()

	from frappe.core.doctype.file.file_v2 import create_file_from_blob

	meta, meta_path, part_path = load_session(upload_id)
	require_session_policy(meta, FILE_SESSION)

	doctype = doctype or meta.get("doctype")
	docname = docname or meta.get("docname")
	file_name = file_name or meta.get("filename")
	is_private = cint(meta.get("is_private")) if is_private is None else cint(is_private)

	ignore_permissions = check_upload_permission(doctype, docname)
	check_restricted_mimetypes(file_name)
	blob = _finish_upload_to_blob(
		upload_id,
		meta,
		meta_path,
		part_path,
		checksum=checksum,
		filename=file_name,
		is_private=bool(is_private),
	)

	return create_file_from_blob(
		blob,
		file_name,
		attached_to_doctype=doctype,
		attached_to_name=docname,
		attached_to_field=fieldname,
		is_private=bool(is_private),
		ignore_permissions=ignore_permissions,
	)


def finish_upload_to_blob(
	upload_id: str,
	*,
	checksum: str | None = None,
	filename: str | None = None,
	is_private: bool | None = None,
) -> "FileBlob":
	"""Finish a trusted blob-only session without creating a File row.

	This ordinary Python interface is deliberately not HTTP-whitelisted. The
	caller must have re-authorized its destination before invoking it.
	"""
	check_enabled()
	meta, meta_path, part_path = load_session(upload_id)
	require_session_policy(meta, BLOB_SESSION)
	filename = filename or meta.get("filename")
	is_private = bool(cint(meta.get("is_private"))) if is_private is None else bool(cint(is_private))
	return _finish_upload_to_blob(
		upload_id,
		meta,
		meta_path,
		part_path,
		checksum=checksum,
		filename=filename,
		is_private=is_private,
	)


def _finish_upload_to_blob(
	upload_id: str,
	meta: dict,
	meta_path: str,
	part_path: str,
	*,
	checksum: str | None,
	filename: str | None,
	is_private: bool,
) -> "FileBlob":
	"""Claim, validate, and clean up either kind of upload session."""
	from frappe.storage.blob import put_blob, validate_upload

	# fail before claiming when no bytes arrived, so the client can retry
	direct = meta.get("mode") == "direct"
	temp_is_private = bool(cint(meta.get("is_private")))
	if direct:
		if not get_driver().exists(f"uploads/{upload_id}", is_private=temp_is_private):
			frappe.throw(_("Upload session has no data"))
	elif session_size(part_path) == 0:
		frappe.throw(_("Upload session has no data"))

	# atomic claim: a concurrent or replayed finish_upload must not create
	# a second File row from the same session
	meta_path = claim_session(meta_path)

	try:
		if direct:
			blob = store_direct_upload(upload_id, temp_is_private, is_private=is_private, filename=filename)
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


def store_direct_upload(upload_id: str, temp_is_private: bool, *, is_private: bool, filename: str | None):
	"""Spool a driver-native direct upload (browser -> bucket) into a blob.

	The client sent the bytes to ``uploads/<upload_id>`` in the namespace
	declared at ``create_upload``; the temporary object is deleted once the
	blob is stored."""
	from frappe.storage.blob import put_blob

	driver = get_driver()
	temp_key = f"uploads/{upload_id}"
	try:
		stream = driver.read(temp_key, is_private=temp_is_private)
	except FileNotFoundError:
		frappe.throw(_("Upload session has no data"))

	try:
		with stream:
			return put_blob(stream, is_private=is_private, filename=filename)
	finally:
		try:
			driver.delete(temp_key, is_private=temp_is_private)
		except Exception:
			frappe.logger("storage").warning(
				f"storage: could not delete finished direct upload {temp_key}", exc_info=True
			)


def expire_stale_upload_sessions(max_age_hours: int = 24) -> int:
	"""Delete upload sessions untouched for ``max_age_hours``. Return the count removed.

	Sweeps every session artifact (``.meta``, ``.part``, claimed
	``.meta.finishing``) and, for direct sessions, the driver-side
	``uploads/<upload_id>`` temporary object."""
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
		get_driver().delete(f"uploads/{upload_id}", is_private=bool(cint(meta.get("is_private"))))
	except Exception:
		frappe.logger("storage").warning(
			f"storage: could not delete stale direct upload uploads/{upload_id}", exc_info=True
		)


def check_enabled():
	if not frappe.storage.enabled():
		frappe.throw(_("File Storage v2 is not enabled for this site"))


def check_upload_permission(doctype: str | None = None, docname: str | None = None) -> bool:
	"""Enforce ``upload_file``'s gating rules. Return the ignore_permissions flag.

	Guests are allowed only when System Settings permit guest uploads, and
	only for the allowed doctypes. Logged-in users need write permission on
	the target document."""
	from frappe.handler import check_write_permission

	if frappe.session.user == "Guest":
		if not frappe.get_system_settings("allow_guests_to_upload_files"):
			raise frappe.PermissionError
		guest_allowed_docs = frappe.get_system_settings("allowed_doctypes_for_guest_uploads")
		if guest_allowed_docs:
			allowed_docs = [doc.strip() for doc in guest_allowed_docs.splitlines() if doc.strip()]
			if allowed_docs and doctype not in allowed_docs:
				frappe.throw(
					_("Guests are not allowed to upload files for {0} Doctype").format(doctype),
					frappe.PermissionError,
				)
		return True

	check_write_permission(doctype, docname)
	return False


def check_restricted_mimetypes(filename: str | None):
	"""Legacy parity with ``upload_file``'s ALLOWED_MIMETYPES gate.

	Guests and users without desk access may only upload the legacy
	allowlisted types. Active content disguised under an allowed extension
	is caught separately by ``validate_upload``'s content sniff."""
	from frappe.handler import ALLOWED_MIMETYPES

	if frappe.session.user == "Guest":
		restricted = True
	else:
		user = frappe.get_lazy_doc("User", frappe.session.user)
		restricted = not user.has_desk_access()
	if not restricted:
		return

	if mimetypes.guess_type(filename or "")[0] not in ALLOWED_MIMETYPES:
		frappe.throw(_("You can only upload JPG, PNG, GIF, PDF, TXT, CSV or Microsoft documents."))


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
	meta_path, part_path = get_session_paths(upload_id)
	meta = read_session_meta(meta_path)
	if meta is None:
		# a concurrent finish claims and deletes the session, so an
		# existence check before the read would leave a race window
		frappe.throw(_("Upload session not found or expired"))
	if meta.get("owner") != frappe.session.user:
		# sessions are bound to the user who opened them
		raise frappe.PermissionError
	return meta, meta_path, part_path


def read_session_meta(meta_path: str) -> dict | None:
	"""Read a session meta file. Return None when it is gone or unreadable.

	A gone file is the ordinary race, so it stays quiet. Bad permissions, a
	truncated file, or a bad device also read as an expired session. Log those:
	otherwise a broken uploads directory fails every upload with no signal."""
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
	"""Bytes received so far. Return 0 when the part file is gone.

	A concurrent finish deletes the part file, so a size read after an
	existence check would raise instead of reporting an empty session."""
	try:
		return os.path.getsize(part_path)
	except FileNotFoundError:
		return 0
	except OSError:
		frappe.logger("storage").warning(f"storage: unreadable upload part {part_path}", exc_info=True)
		return 0


def open_session_part(part_path: str, *, write: bool = False):
	"""Open a session's part file. Throw when it is gone or unreadable.

	Claiming a session does not pin its part file: a chunk write that loaded
	the session before the claim still deletes both files when it overruns the
	declared size, and the stale-session sweep does not spare a claimed
	session. So even a claimed finish can find the bytes gone. Neither mode
	creates the file, because a session without a part file is already dead."""
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


def require_session_policy(meta: dict, expected: str) -> None:
	"""Reject a session created for the other server-owned finish policy.

	Sessions from before this field was added are normal File sessions, which
	keeps in-flight public uploads compatible across an update.
	"""
	policy = meta.get("session_policy", FILE_SESSION)
	if policy != expected:
		frappe.throw(_("Upload session cannot be used by this endpoint"))


def claim_session(meta_path: str) -> str:
	"""Atomically claim a session for finishing. Return the claimed meta path.

	``os.rename`` guarantees a single winner when two finish_upload calls
	race on one session; the loser sees the meta file gone."""
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


def get_request_bytes() -> bytes:
	request = frappe.local.request
	if request.files and "file" in request.files:
		return request.files["file"].stream.read()
	return request.get_data(cache=False)
