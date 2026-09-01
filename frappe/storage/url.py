# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
"""Signed, expiring URLs for private blobs.

URL shape: ``/f/<blob>/<filename>?e=<epoch>&s=<sig>``. A valid signature
grants access with no session and no permission query. Signing key is
derived from the site ``encryption_key``."""

import hashlib
import hmac
import time
from typing import TYPE_CHECKING
from urllib.parse import quote

import frappe
from frappe.storage.driver import get_driver

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File

KEY_CONTEXT = b"frappe-storage-v2-url"


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


def signed_url(file: "File", expires_in: int = 3600) -> str:
	"""Return an expiring download URL for a v2 File row.

	Prefers the driver's native signed URL (e.g. S3 presigned GET) when the
	driver returns one."""
	blob = frappe.get_doc("File Blob", file.blob)
	filename = file.file_name or blob.name

	driver = get_driver(blob.driver)
	native = driver.download_url(blob.key, filename, expires_in, is_private=bool(blob.is_private))
	if native:
		return native

	expires = int(time.time()) + expires_in
	sig = make_signature(blob.name, filename, expires)
	return f"/f/{blob.name}/{quote(filename)}?e={expires}&s={sig}"
