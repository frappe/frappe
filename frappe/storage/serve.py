# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Serve ``/files/`` and ``/private/files/`` URLs through Storage v2.

See "Serving /files/ and /private/files/" in ``frappe/storage/SPEC.md``."""

import os
from typing import TYPE_CHECKING

import werkzeug.utils
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.http import parse_range_header
from werkzeug.wrappers import Request, Response
from werkzeug.wsgi import wrap_file

import frappe
from frappe import _
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.storage.blob import served_type
from frappe.storage.driver import get_driver
from frappe.storage.url import PRIVATE_PREFIX, native_download_url, parse_blob_url, verify_signature
from frappe.utils import cint
from frappe.utils.response import x_accel_response

if TYPE_CHECKING:
	from frappe.core.doctype.file_blob.file_blob import FileBlob

NATIVE_URL_TTL = 60

# A public file's native URL is cacheable. The redirect is cached for half
# the URL's lifetime, so a cached redirect never points at an expired URL.
PUBLIC_NATIVE_URL_TTL = 3600


def serve_public_file(path: str) -> Response:
	"""Handle a ``GET /files/...`` request that nginx did not find on disk."""
	if not (parsed := find_public_blob(path)):
		raise NotFound
	return blob_response(*parsed)


def serve_private_file(path: str) -> Response:
	"""Handle ``GET /private/files/...``: a private blob, else a v1 URL.

	An unknown blob falls through to the v1 lookup, which answers 403 like
	a failed permission check, so a caller cannot probe for blob names."""
	parsed = find_blob(path, is_private=True)
	if not parsed:
		return frappe.utils.response.download_private_file(path)

	blob, filename = parsed
	if not can_access(blob, filename):
		raise Forbidden(_("You don't have permission to access this file"))

	make_access_log(
		doctype="File Blob",
		document=blob.name,
		file_type=os.path.splitext(filename)[1].lstrip("."),
	)

	return blob_response(blob, filename)


def blob_response(blob: "str | FileBlob", filename: str) -> Response:
	"""Serve an authorized blob: a native URL redirect, else the bytes.

	``?download=1`` needs no signature: a download is never less safe than inline."""
	as_attachment = bool(cint(frappe.form_dict.get("download")))
	return stream_blob(blob, filename, as_attachment=as_attachment, allow_native_redirect=True)


def find_blob(path: str, *, is_private: bool) -> "tuple[FileBlob, str] | None":
	"""Return ``(blob, filename)`` when ``path`` is the URL of an existing
	blob with the privacy its prefix implies, else None."""
	parsed = parse_blob_url(path)
	if not parsed or parsed[0] != is_private or not frappe.db.table_exists("File Blob"):
		return None
	_is_private, blob_name, filename = parsed
	if not frappe.db.exists("File Blob", {"name": blob_name, "is_private": cint(is_private)}):
		return None
	return frappe.get_doc("File Blob", blob_name), filename


def find_public_blob(path: str) -> "tuple[FileBlob, str] | None":
	"""Return ``(blob, filename)`` behind a ``/files/`` URL: a public blob, or
	a v1 URL whose bytes moved into a blob."""
	if parsed := find_blob(path, is_private=False):
		return parsed
	if row := frappe.db.get_value(
		"File", {"file_url": path, "is_private": 0, "blob": ("is", "set")}, ["blob", "file_name"]
	):
		return frappe.get_doc("File Blob", row[0]), row[1] or os.path.basename(path)
	return None


def find_readable_blob(path: str, fid: str | None = None) -> "tuple[FileBlob, str] | None":
	"""Return ``(blob, filename)`` behind a files URL the session user may read, else None.

	The serve routes' session rules without signatures, for server-side readers like the PDF renderer."""
	from frappe.core.doctype.file.utils import find_file_by_url

	if not path.startswith(PRIVATE_PREFIX):
		return find_public_blob(path)
	if frappe.session.user == "Guest":
		return None
	if parsed := find_blob(path, is_private=True):
		return parsed if has_file_permission(parsed[0].name) else None
	file = find_file_by_url(path, name=fid)
	if file and file.get("blob"):
		return frappe.get_doc("File Blob", file.blob), file.file_name or os.path.basename(path)
	return None


def can_access(blob: "FileBlob", filename: str) -> bool:
	expires = frappe.form_dict.get("e")
	signature = frappe.form_dict.get("s")
	if (expires or signature) and verify_signature(blob.name, filename, expires, signature):
		return True

	return frappe.session.user != "Guest" and has_file_permission(blob.name)


def has_file_permission(blob_name: str) -> bool:
	"""True if the session user can download any File row linked to the blob, like ``find_file_by_url``."""
	for file_data in frappe.get_all("File", filters={"blob": blob_name}, fields="*"):
		file = frappe.get_doc(doctype="File", **file_data)
		if file.is_downloadable():
			return True
	return False


def stream_blob(
	blob: "str | FileBlob",
	filename: str,
	*,
	as_attachment: bool = False,
	environ: dict | None = None,
	allow_native_redirect: bool = False,
) -> Response:
	"""Serve a blob the caller has authorized. No permission check, no access log.

	``allow_native_redirect`` allows a 302 to the driver's URL. It is off by
	default because some clients (WebDAV) cannot follow cross-host redirects."""
	if isinstance(blob, str):
		blob = frappe.get_doc("File Blob", blob)

	request = Request(environ) if environ is not None else frappe.local.request
	driver = get_driver(blob.driver)
	is_private = bool(blob.is_private)

	if allow_native_redirect:
		if response := _native_url_response(blob, filename, as_attachment=as_attachment):
			return response

	# keyed on the effective Content-Type, not only on the caller-supplied
	# filename: /files/<blob>/x.txt naming an HTML blob must not render inline
	# on the site origin
	mime_type, as_attachment = served_type(filename, blob.mime_type, as_attachment=as_attachment)

	etag = blob.checksum
	if request.if_none_match.contains_weak(etag):
		response = Response(status=304)
		response.set_etag(etag)
		return response

	if local_path := getattr(driver, "get_path", None):
		filepath = local_path(blob.key, is_private)
		if not os.path.exists(filepath):
			# checked before X-Accel too: nginx would pass a missing public
			# file back to Python, which would redirect to it again
			raise NotFound

		if request.headers.get("X-Use-X-Accel-Redirect"):
			response = x_accel_response(x_accel_path(blob), filename, mime_type, as_attachment)
			response.set_etag(etag)
			return response

		# real file on disk: send_file gets size + mtime, so Range works
		return werkzeug.utils.send_file(
			filepath,
			environ=request.environ,
			mimetype=mime_type,
			conditional=True,
			as_attachment=as_attachment,
			download_name=filename,
			etag=etag,
		)

	return _stream_driver_response(blob, filename, request, mime_type=mime_type, as_attachment=as_attachment)


def _native_url_response(blob: "FileBlob", filename: str, *, as_attachment: bool = False) -> Response | None:
	expires_in = NATIVE_URL_TTL if blob.is_private else PUBLIC_NATIVE_URL_TTL
	if not (native := native_download_url(blob, filename, expires_in, as_attachment=as_attachment)):
		return None
	response = werkzeug.utils.redirect(native, 302)
	if not blob.is_private:
		response.headers["Cache-Control"] = f"public, max-age={PUBLIC_NATIVE_URL_TTL // 2}"
	return response


def _stream_driver_response(
	blob: "FileBlob", request_filename: str, request: Request, *, mime_type: str, as_attachment: bool
) -> Response:
	driver = get_driver(blob.driver)
	is_private = bool(blob.is_private)
	file_size = int(blob.file_size or 0)
	range_header = request.headers.get("Range")
	status = 200
	content_range = None

	try:
		if range_header:
			requested = parse_range_header(range_header)
			resolved = (
				requested.range_for_length(file_size)
				if requested and requested.units == "bytes" and len(requested.ranges) == 1
				else None
			)
			if resolved is None:
				response = Response(status=416)
				response.headers["Content-Range"] = f"bytes */{file_size}"
				response.headers["Accept-Ranges"] = "bytes"
				response.set_etag(blob.checksum)
				return response

			start, stop = resolved
			end = stop - 1
			file = driver.read_range(blob.key, start, end, is_private=is_private)
			content_length = stop - start
			content_range = f"bytes {start}-{end}/{file_size}"
			status = 206
		else:
			file = driver.read(blob.key, is_private=is_private)
			content_length = file_size
	except FileNotFoundError:
		raise NotFound from None

	response = Response(
		wrap_file(request.environ, file), status=status, mimetype=mime_type, direct_passthrough=True
	)
	response.content_length = content_length
	response.headers["Accept-Ranges"] = "bytes"
	if content_range:
		response.headers["Content-Range"] = content_range
	response.headers.set(
		"Content-Disposition", "attachment" if as_attachment else "inline", filename=request_filename
	)
	response.set_etag(blob.checksum)
	return response


def x_accel_path(blob: "FileBlob") -> str:
	"""nginx-internal path of a local blob."""
	if not blob.is_private:
		return "/files/" + blob.key
	private_path = frappe.local.conf.get("private_path", "private")
	return "/protected/" + os.path.join(private_path, "files", blob.key)
