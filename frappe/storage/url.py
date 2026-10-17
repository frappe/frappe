# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""URLs of Storage v2 blobs.

A blob's URL is ``/files/<blob>/<filename>`` when it is public and
``/private/files/<blob>/<filename>`` when it is private, the same prefixes
as v1. The stored URL uses the filename in the blob key, so nginx finds a
public local blob on disk. A URL served by Python may carry any filename;
it becomes the download name.

A signed URL adds ``?e=<epoch>&s=<sig>`` to a blob URL. A valid
signature grants access with no session and no permission query. The
signing key is derived from the site ``encryption_key``."""

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
	"""Split a blob URL into ``(is_private, blob_name, filename)``.

	Returns None for any other URL, such as a v1 ``/files/logo.png``. Only
	the shape is checked; the blob may not exist."""
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
	"""Return an expiring URL for a blob and caller-chosen filename.

	The file shows inline where a browser can show it safely. Pass
	``as_attachment`` to make it download instead.

	Prefers the driver's native signed URL (e.g. S3 presigned GET) when the
	driver returns one."""
	if isinstance(blob, str):
		blob = frappe.get_doc("File Blob", blob)

	driver = get_driver(blob.driver)
	native = driver.download_url(
		blob.key,
		filename,
		expires_in,
		is_private=bool(blob.is_private),
		mime_type=blob.mime_type,
		as_attachment=as_attachment,
	)
	if native:
		return native

	# a "/" in the name would split the URL path
	return signed_path(
		blob.name,
		key_filename(filename),
		int(time.time()) + expires_in,
		is_private=bool(blob.is_private),
		as_attachment=as_attachment,
	)


def signed_path(
	blob_name: str, filename: str, expires: int, *, is_private: bool, as_attachment: bool = False
) -> str:
	"""Site-relative blob URL signed until ``expires`` (epoch seconds).

	``filename`` is the unquoted download name; it is signed as given and
	quoted in the path."""
	signature = make_signature(blob_name, filename, expires)
	download = "&download=1" if as_attachment else ""
	prefix = PRIVATE_PREFIX if is_private else PUBLIC_PREFIX
	return f"{prefix}{blob_name}/{quote(filename, safe='')}?e={expires}&s={signature}{download}"


def signed_url(file: "File", expires_in: int = 3600) -> str:
	"""Return an expiring download URL for a v2 File row."""
	return signed_url_for_blob(file.blob, file.file_name or file.blob, expires_in)
