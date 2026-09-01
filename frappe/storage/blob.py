# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import mimetypes
import tempfile
from typing import IO, TYPE_CHECKING

import filetype

import frappe
from frappe import _
from frappe.storage.driver import get_driver
from frappe.utils import cint

if TYPE_CHECKING:
	from frappe.core.doctype.file_blob.file_blob import FileBlob

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

# Leading markers browsers treat as HTML (per the WHATWG MIME sniffing spec).
_HTML_MARKERS = (b"<!doctype html", b"<html", b"<head", b"<body", b"<script", b"<iframe")


def make_key(checksum: str) -> str:
	"""Content-addressed object key: ``ab/cd/<sha256>``."""
	return f"{checksum[:2]}/{checksum[2:4]}/{checksum}"


def sanitized_extension(filename: str | None) -> str:
	"""Lowercase alnum extension from filename, or empty string."""
	if not filename or "." not in filename:
		return ""
	ext = filename.rsplit(".", 1)[1].lower()
	if ext and len(ext) <= 10 and ext.isascii() and ext.isalnum():
		return ext
	return ""


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
	MIME type implied by the claimed filename's extension."""
	if blob.mime_type not in ACTIVE_CONTENT_MIME_TYPES:
		return
	ext_mime = mimetypes.guess_type(claimed_filename or "")[0]
	if blob.mime_type != ext_mime:
		frappe.throw(
			_("File content does not match its extension"),
			frappe.ValidationError,
		)


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
	returns the existing blob with no write, even if its key carries a
	different extension. Blobs are immutable.

	``filename`` only contributes a sanitized lowercase extension to the
	key, so public local blobs stay nginx-servable with a correct
	Content-Type."""
	driver = get_driver()
	spool, size = spool_to_tempfile(stream)
	with spool:
		checksum = sha256_of(spool)
		mime_type = sniff_mime(spool)

		existing = frappe.db.get_value(
			"File Blob",
			{"checksum": checksum, "is_private": cint(is_private), "driver": driver.name},
		)
		if existing:
			return frappe.get_doc("File Blob", existing)

		key = make_key(checksum)
		if ext := sanitized_extension(filename):
			key = f"{key}.{ext}"

		blob = frappe.new_doc("File Blob")
		blob.update(
			{
				"key": key,
				"checksum": checksum,
				"file_size": size,
				"mime_type": mime_type,
				"driver": driver.name,
				"is_private": cint(is_private),
				"status": "Ready",
			}
		)
		driver.write(blob.key, spool, is_private=bool(is_private))
		blob.insert(ignore_permissions=True)
	return blob
