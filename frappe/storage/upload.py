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

import frappe
import frappe.storage
from frappe import _
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError
from frappe.storage.driver import get_driver
from frappe.utils import cint

UPLOADS_DIR = ".uploads"
UPLOAD_ID_PATTERN = re.compile(r"[A-Za-z0-9]+")
FINISHING_SUFFIX = ".finishing"


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

	size = cint(size)
	check_declared_size(size)

	upload_id = frappe.generate_hash(length=20)

	native = get_driver().upload_target(f"uploads/{upload_id}", size, is_private=bool(cint(is_private)))
	mode = "direct" if native else "chunked"

	save_session_meta(
		upload_id,
		{
			"mode": mode,
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
	if meta.get("mode") == "direct":
		frappe.throw(_("This upload session expects a direct upload, not chunks"))

	offset = cint(offset)
	received = os.path.getsize(part_path) if os.path.exists(part_path) else 0
	if offset < 0 or offset > received:
		frappe.throw(_("Invalid chunk offset"))

	chunk = get_request_bytes()
	if offset + len(chunk) > cint(meta.get("size")):
		delete_session(meta_path, part_path)
		frappe.throw(_("Upload exceeds the declared file size"))

	# part_path is built by get_session_paths from an alphanumeric-only upload_id
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
	with open(part_path, "r+b" if os.path.exists(part_path) else "wb") as f:
		f.seek(offset)
		f.write(chunk)

	return {"upload_id": upload_id, "received": os.path.getsize(part_path)}


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
	from frappe.storage.blob import put_blob, validate_upload

	meta, meta_path, part_path = load_session(upload_id)

	doctype = doctype or meta.get("doctype")
	docname = docname or meta.get("docname")
	file_name = file_name or meta.get("filename")
	is_private = cint(meta.get("is_private")) if is_private is None else cint(is_private)

	ignore_permissions = check_upload_permission(doctype, docname)
	check_restricted_mimetypes(file_name)

	# fail before claiming when no bytes arrived, so the client can retry
	direct = meta.get("mode") == "direct"
	temp_is_private = bool(cint(meta.get("is_private")))
	if direct:
		if not get_driver().exists(f"uploads/{upload_id}", is_private=temp_is_private):
			frappe.throw(_("Upload session has no data"))
	elif not os.path.exists(part_path):
		frappe.throw(_("Upload session has no data"))

	# atomic claim: a concurrent or replayed finish_upload must not create
	# a second File row from the same session
	meta_path = claim_session(meta_path)

	if direct:
		blob = store_direct_upload(
			upload_id, temp_is_private, is_private=bool(is_private), filename=file_name
		)
	else:
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		with open(part_path, "rb") as stream:
			blob = put_blob(stream, is_private=bool(is_private), filename=file_name)

	if checksum and blob.checksum != checksum:
		delete_session(meta_path, part_path)
		frappe.throw(_("Checksum mismatch"))

	validate_upload(blob, file_name)

	file = create_file_from_blob(
		blob,
		file_name,
		attached_to_doctype=doctype,
		attached_to_name=docname,
		attached_to_field=fieldname,
		is_private=bool(is_private),
		ignore_permissions=ignore_permissions,
	)

	delete_session(meta_path, part_path)
	return file


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

	with stream:
		blob = put_blob(stream, is_private=is_private, filename=filename)
	driver.delete(temp_key, is_private=temp_is_private)
	return blob


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
			try:
				# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
				with open(path) as f:
					meta = json.load(f)
			except (OSError, ValueError):
				pass
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
	if not os.path.exists(meta_path):
		frappe.throw(_("Upload session not found or expired"))
	# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
	with open(meta_path) as f:
		meta = json.load(f)
	if meta.get("owner") != frappe.session.user:
		# sessions are bound to the user who opened them
		raise frappe.PermissionError
	return meta, meta_path, part_path


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
