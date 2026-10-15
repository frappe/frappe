# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import mimetypes
import os
import posixpath
import tempfile
from typing import IO, TYPE_CHECKING

import filetype

import frappe
from frappe import _
from frappe.storage.driver import get_driver
from frappe.utils import cint, now

if TYPE_CHECKING:
	from frappe.core.doctype.file_blob.file_blob import FileBlob
	from frappe.storage.driver import StorageDriver

CHUNK_SIZE = 64 * 1024
SPOOL_MAX_MEMORY = 1024 * 1024  # spill to disk beyond 1 MiB
SNIFF_BYTES = 8192

# MIME types a browser executes or scripts. A mismatch between these and the
# extension-implied type is an attack (evil.html renamed to evil.png).
ACTIVE_CONTENT_MIME_TYPES = frozenset(
	{
		"text/html",
		"application/xhtml+xml",
		"image/svg+xml",
		"application/pdf",
		"application/javascript",
		"text/javascript",
	}
)

# Served as a download, never inline, so a browser does not run them as a
# page. The URL filename is caller-chosen, so the decision keys on the served
# Content-Type as well as on the extension.
FORCE_DOWNLOAD_EXTENSIONS = (".svg", ".html", ".htm", ".xml")
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

# Leading markers browsers treat as HTML (per the WHATWG MIME sniffing spec).
_HTML_MARKERS = (b"<!doctype html", b"<html", b"<head", b"<body", b"<script", b"<iframe")


def served_type(filename: str, mime_type: str | None, *, as_attachment: bool = False) -> tuple[str, bool]:
	"""Return the Content-Type to serve a blob with, and whether it must download.

	Every byte path asks this: the Python stream, nginx, and a driver's
	native signed URL. So a file shows inline or downloads the same way on
	every driver. A blob stored as ``application/octet-stream`` takes the type
	its filename suggests, because magic-number sniffing cannot recognise text
	formats. Active content always downloads, whatever the caller asked."""
	mime_type = mime_type or "application/octet-stream"
	if mime_type == "application/octet-stream":
		mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
	extension = os.path.splitext(filename)[1].lower()
	must_download = (
		as_attachment or extension in FORCE_DOWNLOAD_EXTENSIONS or mime_type in FORCE_DOWNLOAD_MIME_TYPES
	)
	return mime_type, must_download


# A key holds the blob name and filename, so a long legacy path or name
# must still fit the File Blob ``key`` column.
MAX_KEY_FILENAME_LENGTH = 200


def key_filename(filename: str | None) -> str:
	"""Filename as it appears in a blob key and URL.

	Path separators and URL delimiters are replaced, and a long name is cut
	while its extension is kept."""
	from frappe.core.doctype.file.utils import get_safe_file_name

	name = "".join(char for char in (filename or "") if char.isprintable())
	name = get_safe_file_name(name).strip().strip(".") or "file"
	if len(name) <= MAX_KEY_FILENAME_LENGTH:
		return name
	stem, extension = os.path.splitext(name)
	if len(extension) > 20:
		extension = ""
	return stem[: MAX_KEY_FILENAME_LENGTH - len(extension)] + extension


def make_key(driver: "StorageDriver", blob_name: str, filename: str | None) -> str:
	"""Object key for a blob: ``[<site prefix>/]<blob>/<filename>``.

	The local driver stores the file at this path under ``public/files`` or
	``private/files``, so the file's URL and its path on disk match."""
	return f"{driver.key_prefix}{blob_name}/{key_filename(filename)}"


def key_basename(key: str) -> str:
	"""Filename part of a blob key, also for backfilled legacy keys."""
	return posixpath.basename(key)


def _sniff_active_text(head: bytes) -> str | None:
	"""Detect text-based active content that magic-number sniffing misses."""
	sample = head.lstrip()[:512].lower()
	if sample.startswith(b"<svg") or (sample.startswith(b"<?xml") and b"<svg" in sample):
		return "image/svg+xml"
	if sample.startswith(_HTML_MARKERS):
		return "text/html"
	return None


def sniff_mime(stream: IO[bytes]) -> str:
	"""Guess the MIME type from content bytes, not from a filename."""
	stream.seek(0)
	head = stream.read(SNIFF_BYTES)
	stream.seek(0)
	kind = filetype.guess(head)
	if kind:
		return kind.mime
	return _sniff_active_text(head) or "application/octet-stream"


def validate_upload(blob: "FileBlob", claimed_filename: str) -> None:
	"""Reject active content hidden under a mismatched extension.

	Raises frappe.ValidationError when the sniffed MIME type is active
	content (html, svg, xhtml, pdf, javascript) and does not match the
	MIME type implied by the claimed filename's extension. PDFs are also
	scanned for embedded JavaScript, like the legacy ``check_content``."""
	if blob.mime_type not in ACTIVE_CONTENT_MIME_TYPES:
		return
	ext_mime = mimetypes.guess_type(claimed_filename or "")[0]
	if blob.mime_type != ext_mime:
		frappe.throw(
			_("File content does not match its extension"),
			frappe.ValidationError,
		)
	if blob.mime_type == "application/pdf":
		validate_pdf_content(blob)


def validate_pdf_content(blob: "FileBlob") -> None:
	"""Reject PDFs with embedded JavaScript (legacy ``File.check_content`` parity)."""
	from frappe.utils.pdf import pdf_contains_js

	driver = get_driver(blob.driver)
	with driver.read(blob.key, is_private=bool(blob.is_private)) as f:
		content = f.read()
	if pdf_contains_js(content):
		frappe.throw(_("This PDF cannot be uploaded as it contains unsafe content."))


def spool_to_tempfile(stream: IO[bytes]) -> tuple[IO[bytes], int]:
	"""Copy stream into a spooled tempfile. Return (spool, size in bytes).

	Never holds the full content in RAM past ``SPOOL_MAX_MEMORY``."""
	spool = tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_MEMORY)
	size = 0
	while chunk := stream.read(CHUNK_SIZE):
		size += len(chunk)
		spool.write(chunk)
	spool.seek(0)
	return spool, size


def sha256_of(stream: IO[bytes]) -> str:
	stream.seek(0)
	digest = hashlib.sha256()
	while chunk := stream.read(CHUNK_SIZE):
		digest.update(chunk)
	stream.seek(0)
	return digest.hexdigest()


def put_blob(stream: IO[bytes], *, is_private: bool = False, filename: str | None = None) -> "FileBlob":
	"""Store the stream through the active driver. Return its File Blob.

	Deduplicates on ``(checksum, is_private, driver)``: identical content
	returns the existing blob with no write, keeping the existing blob's
	filename. Blobs are immutable.

	The key is ``<blob>/<filename>`` (see ``make_key``), so a public local
	blob sits on disk at its URL path and nginx serves it."""
	driver = get_driver()
	spool, size = spool_to_tempfile(stream)
	with spool:
		checksum = sha256_of(spool)
		mime_type = sniff_mime(spool)

		existing = frappe.db.get_value(
			"File Blob",
			{"checksum": checksum, "is_private": cint(is_private), "driver": driver.name},
		)
		if existing and revive_blob(existing):
			return frappe.get_doc("File Blob", existing)

		blob = frappe.new_doc("File Blob")
		blob.set_new_name()
		blob.update(
			{
				"key": make_key(driver, blob.name, filename),
				"checksum": checksum,
				"file_size": size,
				"mime_type": mime_type,
				"driver": driver.name,
				"is_private": cint(is_private),
				"status": "Ready",
			}
		)
		# registered before the write: a failed insert (such as a concurrent
		# upload of the same content winning the unique index) rolls back
		# and removes these bytes, which no other blob shares
		frappe.db.after_rollback.add(delete_bytes_on_rollback(driver, blob.key, bool(is_private)))
		driver.write(blob.key, spool, is_private=bool(is_private))
		blob.insert(ignore_permissions=True)
	return blob


def revive_blob(blob_name: str) -> bool:
	"""Lock a deduped blob and pull it out of the GC orphan window.

	Returns False when the row vanished between the dedup lookup and the
	lock (a concurrent GC pass deleted it); the caller then stores the
	content again. The ``modified`` bump keeps GC's cutoff away from a
	blob that is being relinked in an uncommitted transaction."""
	locked = frappe.db.get_value("File Blob", blob_name, "name", for_update=True)
	if not locked:
		return False
	frappe.db.set_value("File Blob", blob_name, "modified", now(), update_modified=False)
	return True


def delete_bytes_on_rollback(driver, key: str, is_private: bool):
	"""after_rollback callback: remove bytes whose File Blob row was rolled back.

	Without this, a rolled-back ``put_blob`` (failed validation, explicit
	rollback) leaves bytes on disk that GC can never find, because GC only
	sees File Blob rows."""

	def callback():
		if frappe.db.get_value(
			"File Blob", {"key": key, "driver": driver.name, "is_private": cint(is_private)}
		):
			# a committed row still owns these bytes
			return
		try:
			driver.delete(key, is_private=is_private)
		except Exception:
			frappe.logger("storage").warning(
				f"storage: could not delete rolled-back blob bytes (key {key})", exc_info=True
			)

	return callback
