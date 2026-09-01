# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import tempfile
from typing import IO, TYPE_CHECKING

import filetype

import frappe
from frappe.storage.driver import get_driver
from frappe.utils import cint

if TYPE_CHECKING:
	from frappe.core.doctype.file_blob.file_blob import FileBlob

CHUNK_SIZE = 64 * 1024
SPOOL_MAX_MEMORY = 1024 * 1024  # spill to disk beyond 1 MiB
SNIFF_BYTES = 8192


def make_key(checksum: str) -> str:
	"""Content-addressed object key: ``ab/cd/<sha256>``."""
	return f"{checksum[:2]}/{checksum[2:4]}/{checksum}"


def sniff_mime(stream: IO[bytes]) -> str:
	"""Guess the MIME type from content bytes, not from a filename."""
	stream.seek(0)
	kind = filetype.guess(stream.read(SNIFF_BYTES))
	stream.seek(0)
	return kind.mime if kind else "application/octet-stream"


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


def put_blob(stream: IO[bytes], *, is_private: bool = False) -> "FileBlob":
	"""Store the stream through the active driver. Return its File Blob.

	Deduplicates on ``(checksum, is_private, driver)``: identical content
	returns the existing blob with no write. Blobs are immutable."""
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

		blob = frappe.new_doc("File Blob")
		blob.update(
			{
				"key": make_key(checksum),
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
