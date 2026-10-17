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

	Every byte path asks this, so a file behaves the same on every driver.
	``application/octet-stream`` takes the filename's type: sniffing cannot recognise text."""
	mime_type = mime_type or "application/octet-stream"
	if mime_type == "application/octet-stream":
		mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
	extension = os.path.splitext(filename)[1].lower()
	must_download = (
		as_attachment or extension in FORCE_DOWNLOAD_EXTENSIONS or mime_type in FORCE_DOWNLOAD_MIME_TYPES
	)
	return mime_type, must_download


# In UTF-8 bytes: most filesystems allow 255 bytes per filename, and the
# local driver writes ``<filename>.part`` first. The key column counts
# characters, so a name within this limit also fits there.
MAX_KEY_FILENAME_BYTES = 200


def key_filename(filename: str | None) -> str:
	"""Filename as it appears in a blob key and URL: no path or URL delimiters, length-capped."""
	from frappe.core.doctype.file.utils import get_safe_file_name

	name = "".join(char for char in (filename or "") if char.isprintable())
	name = get_safe_file_name(name).strip().strip(".") or "file"
	if len(name.encode()) <= MAX_KEY_FILENAME_BYTES:
		return name
	stem, extension = os.path.splitext(name)
	if len(extension.encode()) > 20:
		extension = ""
	stem_budget = MAX_KEY_FILENAME_BYTES - len(extension.encode())
	return stem.encode()[:stem_budget].decode(errors="ignore") + extension


def make_key(driver: "StorageDriver", blob_name: str, filename: str | None) -> str:
	"""Object key for a blob: ``[<site prefix>/]<blob>/<filename>``, also its local path under the files root."""
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
	"""Reject active content hidden under a mismatched extension, and PDFs with JavaScript."""
	if blob.mime_type not in ACTIVE_CONTENT_MIME_TYPES:
		return
	ext_mime = mimetypes.guess_type(claimed_filename or "")[0]
	if blob.mime_type != ext_mime:
		frappe.throw(
			_("File content does not match its extension"),
			frappe.ValidationError,
		)
	if blob.mime_type == "application/pdf":
		from frappe.utils.pdf import pdf_contains_js

		with get_driver(blob.driver).read(blob.key, is_private=bool(blob.is_private)) as f:
			if pdf_contains_js(f.read()):
				frappe.throw(_("This PDF cannot be uploaded as it contains unsafe content."))


def spool_to_tempfile(stream: IO[bytes]) -> tuple[IO[bytes], int]:
	"""Copy stream into a spooled tempfile. Return (spool, size in bytes)."""
	spool = tempfile.SpooledTemporaryFile(max_size=SPOOL_MAX_MEMORY)
	size = 0
	while chunk := stream.read(CHUNK_SIZE):
		size += len(chunk)
		spool.write(chunk)
	spool.seek(0)
	return spool, size


def sha256_of(stream: IO[bytes]) -> str:
	stream.seek(0)
	digest = hashlib.file_digest(stream, "sha256").hexdigest()
	stream.seek(0)
	return digest


def put_blob(stream: IO[bytes], *, is_private: bool = False, filename: str | None = None) -> "FileBlob":
	"""Store the stream through the active driver. Return its File Blob.

	Best-effort dedup on ``(checksum, is_private, driver)``: identical content
	usually returns the existing blob, with its filename. Concurrent uploads may duplicate."""
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
		# registered before the write: a rolled-back insert removes these
		# bytes, which no other blob shares
		frappe.db.after_rollback.add(delete_bytes_on_rollback(driver, blob.key, bool(is_private)))
		driver.write(blob.key, spool, is_private=bool(is_private))
		blob.insert(ignore_permissions=True)
	return blob


def revive_blob(blob_name: str) -> bool:
	"""Lock an existing blob before linking it. False when GC deleted it first.

	The ``modified`` bump keeps GC away from a blob linked in an uncommitted transaction."""
	locked = frappe.db.get_value("File Blob", blob_name, "name", for_update=True)
	if not locked:
		return False
	frappe.db.set_value("File Blob", blob_name, "modified", now(), update_modified=False)
	return True


def delete_bytes_on_rollback(driver, key: str, is_private: bool):
	"""after_rollback callback: remove bytes whose File Blob row was rolled back.

	GC only sees File Blob rows, so it could never find these bytes."""

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
