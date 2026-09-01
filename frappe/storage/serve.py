# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Serve route for Storage v2 blobs: ``GET /f/<blob>/<filename>``.

Access is granted by any one of:

- a valid signature (``?e=<epoch>&s=<sig>``, see ``frappe/storage/url.py``),
- the blob being public,
- a non-Guest session where some File row linked to the blob is downloadable
  (mirrors ``find_file_by_url``'s any-row rule).

Response modes, in order: driver-native signed URL (302 redirect),
X-Accel-Redirect (nginx sends the bytes), streamed ``send_file`` with
Range support. Mirrors ``frappe.utils.response.send_private_file``.
"""

import mimetypes
import os
from typing import TYPE_CHECKING
from urllib.parse import quote

import werkzeug.utils
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.wrappers import Response

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.storage.driver import get_driver
from frappe.storage.url import verify_signature

if TYPE_CHECKING:
	from frappe.core.doctype.file_blob.file_blob import FileBlob

FORCE_DOWNLOAD_EXTENSIONS = (".svg", ".html", ".htm", ".xml")
# MIME types never served inline: the URL filename is caller-chosen, so the
# decision must key on the effective Content-Type, not on the extension alone.
FORCE_DOWNLOAD_MIME_TYPES = frozenset(
	{
		"text/html",
		"application/xhtml+xml",
		"image/svg+xml",
		"application/javascript",
		"text/javascript",
		"text/xml",
		"application/xml",
	}
)
NATIVE_URL_TTL = 60


def serve_file(path: str) -> Response:
	"""Handle ``GET /f/<blob>/<filename>``."""
	blob_name, filename = parse_path(path)
	blob = get_blob(blob_name)

	if not can_access(blob, filename):
		raise Forbidden(_("You don't have permission to access this file"))

	if blob.is_private:
		make_access_log(
			doctype="File Blob",
			document=blob.name,
			file_type=os.path.splitext(filename)[1].lstrip("."),
		)

	return build_response(blob, filename)


def parse_path(path: str) -> tuple[str, str]:
	"""Split ``/f/<blob>/<filename>`` into (blob_name, filename)."""
	parts = path[len("/f/") :].split("/", 1) if path.startswith("/f/") else []
	blob_name = parts[0] if parts else ""
	if not blob_name:
		raise NotFound
	filename = parts[1] if len(parts) > 1 and parts[1] else blob_name
	return blob_name, filename


def get_blob(blob_name: str) -> "FileBlob":
	if not frappe.db.table_exists("File Blob") or not frappe.db.exists("File Blob", blob_name):
		# same response as a failed permission check, so an unauthenticated
		# caller cannot probe which blob names exist
		raise Forbidden(_("You don't have permission to access this file"))
	return frappe.get_doc("File Blob", blob_name)


def can_access(blob: "FileBlob", filename: str) -> bool:
	expires = frappe.form_dict.get("e")
	signature = frappe.form_dict.get("s")
	if (expires or signature) and verify_signature(blob.name, filename, expires, signature):
		return True

	if not blob.is_private:
		return True

	return frappe.session.user != "Guest" and has_file_permission(blob.name)


def has_file_permission(blob_name: str) -> bool:
	"""True if any File row linked to the blob is downloadable by the session user.

	Mirrors ``find_file_by_url``: the same blob may back many attachments;
	access through any one of them is enough."""
	for file_data in frappe.get_all("File", filters={"blob": blob_name}, fields="*"):
		file = frappe.get_doc(doctype="File", **file_data)
		if file.is_downloadable():
			return True
	return False


def build_response(blob: "FileBlob", filename: str) -> Response:
	driver = get_driver(blob.driver)
	is_private = bool(blob.is_private)

	native = driver.download_url(blob.key, filename, NATIVE_URL_TTL, is_private=is_private)
	if native:
		return werkzeug.utils.redirect(native, 302)

	mime_type = blob.mime_type or "application/octet-stream"
	if mime_type == "application/octet-stream":
		# filetype cannot sniff text formats; fall back to the filename
		mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

	# key the inline-vs-download decision on the effective Content-Type, not
	# only on the caller-supplied filename: /f/<blob>/x.txt naming an HTML
	# blob must not render inline on the site origin
	extension = os.path.splitext(filename)[1].lower()
	as_attachment = extension in FORCE_DOWNLOAD_EXTENSIONS or mime_type in FORCE_DOWNLOAD_MIME_TYPES

	if blob.driver == "local" and frappe.local.request.headers.get("X-Use-X-Accel-Redirect"):
		return x_accel_response(blob, filename, mime_type, as_attachment)

	if local_path := getattr(driver, "get_path", None):
		# real file on disk: send_file gets size + mtime, so Range works
		filepath = local_path(blob.key, is_private)
		if not os.path.exists(filepath):
			raise NotFound
		file = filepath
	else:
		try:
			file = driver.read(blob.key, is_private=is_private)
		except FileNotFoundError:
			raise NotFound

	return werkzeug.utils.send_file(
		file,
		environ=frappe.local.request.environ,
		mimetype=mime_type,
		conditional=True,
		as_attachment=as_attachment,
		download_name=filename,
	)


def x_accel_response(blob: "FileBlob", filename: str, mime_type: str, as_attachment: bool) -> Response:
	"""Let nginx send the bytes. Mirrors ``send_private_file``'s X-Accel branch."""
	if blob.is_private:
		private_path = frappe.local.conf.get("private_path", "private")
		accel_path = "/protected/" + os.path.join(private_path, "files", "blobs", blob.key)
	else:
		accel_path = "/files/blobs/" + blob.key

	response = Response()
	response.headers["X-Accel-Redirect"] = quote(frappe.utils.encode(accel_path))
	response.headers["Cache-Control"] = "private,max-age=3600,stale-while-revalidate=86400"
	response.headers["Accept-Ranges"] = "bytes"
	response.headers["Content-Type"] = mime_type

	if as_attachment:
		response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"

	return response
