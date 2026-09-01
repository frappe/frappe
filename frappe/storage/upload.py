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


@frappe.whitelist(allow_guest=True, methods=["POST"])
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

	size = cint(size)
	check_declared_size(size)

	upload_id = frappe.generate_hash(length=20)

	native = get_driver().upload_target(f"uploads/{upload_id}", size)
	if native:
		return {"mode": "direct", **native}

	save_session_meta(
		upload_id,
		{
			"filename": filename,
			"size": size,
			"is_private": cint(is_private),
			"doctype": doctype,
			"docname": docname,
			"owner": frappe.session.user,
			"created_at": int(time.time()),
		},
	)
	return {"mode": "chunked", "upload_id": upload_id}


@frappe.whitelist(allow_guest=True, methods=["POST", "PUT"])
def upload_chunk(upload_id: str, offset: int | str = 0):
	"""Write the request body into the session's part file at ``offset``.

	The cumulative size must stay within the declared size; a violation
	deletes the session. Re-sending an already received chunk is allowed
	(idempotent retry), writing past the end of the part file is not."""
	check_enabled()
	meta, meta_path, part_path = load_session(upload_id)

	offset = cint(offset)
	received = os.path.getsize(part_path) if os.path.exists(part_path) else 0
	if offset < 0 or offset > received:
		frappe.throw(_("Invalid chunk offset"))

	chunk = get_request_bytes()
	if offset + len(chunk) > cint(meta.get("size")):
		delete_session(meta_path, part_path)
		frappe.throw(_("Upload exceeds the declared file size"))

	with open(part_path, "r+b" if os.path.exists(part_path) else "wb") as f:
		f.seek(offset)
		f.write(chunk)

	return {"upload_id": upload_id, "received": os.path.getsize(part_path)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
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

	from frappe.core.doctype.file.file import create_file_from_blob
	from frappe.storage.blob import put_blob, validate_upload

	meta, meta_path, part_path = load_session(upload_id)

	doctype = doctype or meta.get("doctype")
	docname = docname or meta.get("docname")
	file_name = file_name or meta.get("filename")
	is_private = cint(meta.get("is_private")) if is_private is None else cint(is_private)

	ignore_permissions = check_upload_permission(doctype, docname)

	if not os.path.exists(part_path):
		frappe.throw(_("Upload session has no data"))

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


def expire_stale_upload_sessions(max_age_hours: int = 24) -> int:
	"""Delete upload sessions untouched for ``max_age_hours``. Return the count removed."""
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

	for entry in os.listdir(uploads_dir):
		if not entry.endswith(".meta"):
			continue
		meta_path = os.path.join(uploads_dir, entry)
		part_path = os.path.join(uploads_dir, entry[: -len(".meta")] + ".part")
		# an active chunked upload keeps touching the part file
		if max(mtime(meta_path), mtime(part_path)) < cutoff:
			delete_session(meta_path, part_path)
			removed += 1

	for entry in os.listdir(uploads_dir):
		if not entry.endswith(".part"):
			continue
		part_path = os.path.join(uploads_dir, entry)
		meta_path = os.path.join(uploads_dir, entry[: -len(".part")] + ".meta")
		if not os.path.exists(meta_path) and mtime(part_path) < cutoff:
			delete_session(meta_path, part_path)
			removed += 1

	return removed


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
	with open(meta_path, "w") as f:
		json.dump(meta, f)
	open(part_path, "wb").close()


def load_session(upload_id: str) -> tuple[dict, str, str]:
	meta_path, part_path = get_session_paths(upload_id)
	if not os.path.exists(meta_path):
		frappe.throw(_("Upload session not found or expired"))
	with open(meta_path) as f:
		meta = json.load(f)
	return meta, meta_path, part_path


def delete_session(meta_path: str, part_path: str):
	for path in (meta_path, part_path):
		try:
			os.remove(path)
		except OSError:
			pass


def get_request_bytes() -> bytes:
	request = frappe.local.request
	if request.files and "file" in request.files:
		return request.files["file"].stream.read()
	return request.get_data(cache=False)
