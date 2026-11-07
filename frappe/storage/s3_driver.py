# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import re
from typing import IO
from urllib.parse import quote

import frappe
from frappe import _
from frappe.storage.blob import served_type
from frappe.storage.driver import StorageDriver

# TTL for presigned POST upload targets, in seconds.
UPLOAD_TARGET_TTL = 600

SITE_PREFIX_PATTERN = re.compile(r"[A-Za-z0-9._-]+")

# head_object / get_object error codes that mean "no such object".
MISSING_KEY_CODES = ("404", "NoSuchKey", "NotFound")


def get_site_prefix(config: dict) -> str:
	"""The site's folder in the bucket: ``storage_driver_config.prefix``, else a hash of the database name.

	The hash keeps the database name out of the presigned URLs users see."""
	prefix = (config.get("prefix") or "").strip("/")
	if not prefix:
		return hashlib.sha256(frappe.conf.db_name.encode()).hexdigest()[:12]
	if not SITE_PREFIX_PATTERN.fullmatch(prefix):
		frappe.throw(_("The S3 storage prefix may only contain letters, digits, '-', '_' and '.'"))
	return prefix


class S3Driver(StorageDriver):
	"""Store blobs in an S3 (or S3-compatible) bucket, configured by ``storage_driver_config``.

	It deletes only keys under the site prefix, so a site restored from
	another site's backup can read that site's objects but never deletes them."""

	name = "s3"

	def __init__(self):
		config = frappe.conf.storage_driver_config or {}
		self.bucket = config.get("bucket")
		if not self.bucket:
			frappe.throw(
				_("The S3 storage driver requires a {0} in {1}").format(
					frappe.bold("bucket"), frappe.bold("storage_driver_config")
				)
			)

		try:
			import boto3
			from botocore.config import Config
			from botocore.exceptions import ClientError
		except ImportError:
			frappe.throw(
				_("The S3 storage driver requires the {0} package. Install it with: {1}").format(
					frappe.bold("boto3"), frappe.bold("pip install boto3")
				)
			)

		self._client_error = ClientError

		client_kwargs = {}
		for conf_key, boto_arg in (
			("region", "region_name"),
			("endpoint_url", "endpoint_url"),
			("access_key_id", "aws_access_key_id"),
			("secret_access_key", "aws_secret_access_key"),
		):
			if value := config.get(conf_key):
				client_kwargs[boto_arg] = value

		self.client = boto3.client("s3", config=Config(signature_version="s3v4"), **client_kwargs)
		self.key_prefix = f"{get_site_prefix(config)}/"

	def object_key(self, key: str, is_private: bool = False) -> str:
		return f"{'private' if is_private else 'public'}/{key}"

	def write(self, key: str, stream: IO[bytes], *, is_private: bool = False) -> None:
		self.client.upload_fileobj(stream, self.bucket, self.object_key(key, is_private))

	def read(self, key: str, *, is_private: bool = False) -> IO[bytes]:
		return self._get_object(key, is_private=is_private)["Body"]

	def read_range(self, key: str, start: int, end: int | None, *, is_private: bool = False) -> IO[bytes]:
		byte_range = f"bytes={start}-{'' if end is None else end}"
		return self._get_object(key, is_private=is_private, Range=byte_range)["Body"]

	def _get_object(self, key: str, *, is_private: bool = False, **kwargs):
		try:
			return self.client.get_object(Bucket=self.bucket, Key=self.object_key(key, is_private), **kwargs)
		except self._client_error as e:
			if e.response.get("Error", {}).get("Code") in MISSING_KEY_CODES:
				raise FileNotFoundError(key) from e
			raise

	def delete(self, key: str, *, is_private: bool = False) -> None:
		if not key.startswith(self.key_prefix):
			# another site's object, such as one a restored backup points at
			frappe.logger("storage").info(f"storage: kept {key}, it is outside this site's prefix")
			return
		# delete_object is idempotent; a missing key is not an error
		self.client.delete_object(Bucket=self.bucket, Key=self.object_key(key, is_private))

	def exists(self, key: str, *, is_private: bool = False) -> bool:
		try:
			self.client.head_object(Bucket=self.bucket, Key=self.object_key(key, is_private))
		except self._client_error as e:
			if e.response.get("Error", {}).get("Code") in MISSING_KEY_CODES:
				return False
			raise
		return True

	def download_url(
		self,
		key: str,
		filename: str,
		expires_in: int,
		*,
		is_private: bool = False,
		mime_type: str | None = None,
		as_attachment: bool = False,
	) -> str | None:
		"""Presigned GET that serves the blob's ``served_type`` Content-Type and disposition."""
		content_type, must_download = served_type(filename, mime_type, as_attachment=as_attachment)
		# the quoted-string fallback keeps printable ASCII only; filename*
		# carries the real name, percent-encoded per RFC 5987
		ascii_name = "".join(
			char for char in filename if char.isascii() and char.isprintable() and char not in '"\\'
		)
		disposition = (
			f"{'attachment' if must_download else 'inline'}; "
			f"filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename, safe='')}"
		)
		return self.client.generate_presigned_url(
			"get_object",
			Params={
				"Bucket": self.bucket,
				"Key": self.object_key(key, is_private),
				"ResponseContentType": content_type,
				"ResponseContentDisposition": disposition,
			},
			ExpiresIn=expires_in,
		)

	def upload_target(self, key: str, size: int, *, is_private: bool = False) -> dict | None:
		"""Presigned POST for direct browser-to-bucket upload, pinned to the declared size."""
		post = self.client.generate_presigned_post(
			Bucket=self.bucket,
			Key=self.object_key(key, is_private),
			Conditions=[["content-length-range", size, size]],
			ExpiresIn=UPLOAD_TARGET_TTL,
		)
		return {"mode": "direct", "url": post["url"], "fields": post["fields"]}
