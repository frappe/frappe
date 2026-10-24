# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Blob URLs, ``/files/<blob>/<filename>`` or ``/private/files/<blob>/<filename>``, and their signatures.

See "Signed URLs" in ``frappe/storage/SPEC.md``."""

import hashlib
import hmac
import re
import time
from typing import TYPE_CHECKING
from urllib.parse import quote

import frappe
from frappe.storage.blob import key_basename, key_filename
from frappe.storage.driver import get_driver

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File
	from frappe.core.doctype.file_blob.file_blob import FileBlob

KEY_CONTEXT = b"frappe-storage-v2-url"

PUBLIC_PREFIX = "/files/"
PRIVATE_PREFIX = "/private/files/"

# File Blob names are random 10-character hashes (autoname: hash)
BLOB_NAME_PATTERN = re.compile(r"[0-9a-z]{10}")


def blob_url(blob: "FileBlob") -> str:
	"""Stable, unsigned URL of a blob. It is stored in ``File.file_url``."""
	prefix = PRIVATE_PREFIX if blob.is_private else PUBLIC_PREFIX
	return f"{prefix}{blob.name}/{key_basename(blob.key)}"


def parse_blob_url(url: str) -> tuple[bool, str, str] | None:
	"""Split a blob URL into ``(is_private, blob_name, filename)``, else None.

	Only the shape is checked; the blob may not exist."""
	if url.startswith(PRIVATE_PREFIX):
		is_private, path = True, url[len(PRIVATE_PREFIX) :]
	elif url.startswith(PUBLIC_PREFIX):
		is_private, path = False, url[len(PUBLIC_PREFIX) :]
	else:
		return None
	blob_name, _, filename = path.partition("/")
	if not BLOB_NAME_PATTERN.fullmatch(blob_name) or not filename or "/" in filename:
		return None
	return is_private, blob_name, filename


def get_signing_key() -> bytes:
	"""Derive a URL signing key from the site encryption key."""
	from frappe.utils.password import get_encryption_key

	return hashlib.sha256(KEY_CONTEXT + b":" + get_encryption_key().encode()).digest()


def make_signature(blob_name: str, filename: str, expires: int) -> str:
	payload = f"{blob_name}:{filename}:{expires}"
	return hmac.new(get_signing_key(), payload.encode(), hashlib.sha256).hexdigest()


def verify_signature(blob_name: str, filename: str, expires: str | int, signature: str) -> bool:
	"""Return True if the signature matches and has not expired."""
	try:
		expires = int(expires)
	except (TypeError, ValueError):
		return False
	if expires < int(time.time()):
		return False
	expected = make_signature(blob_name, filename, expires)
	return hmac.compare_digest(expected, signature or "")


def signed_url_for_blob(
	blob: "str | FileBlob", filename: str, expires_in: int = 3600, *, as_attachment: bool = False
) -> str:
	"""Return an expiring URL for a blob, preferring the driver's native URL.

	The file shows inline where that is safe; ``as_attachment`` makes it download."""
	if isinstance(blob, str):
		blob = frappe.get_doc("File Blob", blob)
	if native := native_download_url(blob, filename, expires_in, as_attachment=as_attachment):
		return native

	# a "/" in the name would split the URL path
	filename = key_filename(filename)
	expires = int(time.time()) + expires_in
	signature = make_signature(blob.name, filename, expires)
	download = "&download=1" if as_attachment else ""
	prefix = PRIVATE_PREFIX if blob.is_private else PUBLIC_PREFIX
	return f"{prefix}{blob.name}/{quote(filename, safe='')}?e={expires}&s={signature}{download}"


def native_download_url(
	blob: "FileBlob", filename: str, expires_in: int, *, as_attachment: bool = False
) -> str | None:
	"""The driver's own signed URL for a blob (e.g. S3 presigned GET), else None."""
	return get_driver(blob.driver).download_url(
		blob.key,
		filename,
		expires_in,
		is_private=bool(blob.is_private),
		mime_type=blob.mime_type,
		as_attachment=as_attachment,
	)


def signed_url(file: "File", expires_in: int = 3600) -> str:
	"""Return an expiring download URL for a v2 File row."""
	return signed_url_for_blob(file.blob, file.file_name or file.blob, expires_in)
