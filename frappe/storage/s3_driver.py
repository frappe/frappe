# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
from typing import IO
from urllib.parse import quote

import frappe
from frappe import _
from frappe.storage.driver import StorageDriver

# TTL for presigned POST upload targets, in seconds.
UPLOAD_TARGET_TTL = 600

# head_object / get_object error codes that mean "no such object".
MISSING_KEY_CODES = ("404", "NoSuchKey", "NotFound")


class S3Driver(StorageDriver):
	"""Store blobs in an S3 (or S3-compatible) bucket.

	``boto3`` is an optional dependency, imported lazily on instantiation.

	Site config, under ``storage_driver_config``:

	- ``bucket`` (required): bucket name.
	- ``region``: AWS region name.
	- ``endpoint_url``: for S3-compatible stores (MinIO, R2, ...).
	- ``access_key_id`` / ``secret_access_key``: static credentials.
	  When absent, the default boto3 credential chain applies.

	Object keys are the blob key under a ``private/`` or ``public/``
	prefix, picked by the ``is_private`` kwarg."""

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

	def object_key(self, key: str, is_private: bool = False) -> str:
		return f"{'private' if is_private else 'public'}/{key}"

	def write(self, key: str, stream: IO[bytes], *, is_private: bool = False) -> None:
		self.client.upload_fileobj(stream, self.bucket, self.object_key(key, is_private))

	def read(self, key: str, *, is_private: bool = False) -> IO[bytes]:
		try:
			response = self.client.get_object(Bucket=self.bucket, Key=self.object_key(key, is_private))
		except self._client_error as e:
			if e.response.get("Error", {}).get("Code") in MISSING_KEY_CODES:
				raise FileNotFoundError(key) from e
			raise
		# botocore's StreamingBody is already file-like: read() and close()
		return response["Body"]

	def delete(self, key: str, *, is_private: bool = False) -> None:
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
		self, key: str, filename: str, expires_in: int, *, is_private: bool = True
	) -> str | None:
		"""Presigned GET with the filename carried in Content-Disposition.

		Defaults to the private namespace: native download URLs exist to
		serve private blobs; public blobs have plain bucket URLs."""
		ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "").replace("\\", "")
		disposition = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
		return self.client.generate_presigned_url(
			"get_object",
			Params={
				"Bucket": self.bucket,
				"Key": self.object_key(key, is_private),
				"ResponseContentDisposition": disposition,
			},
			ExpiresIn=expires_in,
		)

	def upload_target(self, key: str, size: int, *, is_private: bool = True) -> dict | None:
		"""Presigned POST for direct browser-to-bucket upload.

		The content-length-range condition pins the upload to the declared
		size, so the size check done at session creation cannot be bypassed."""
		post = self.client.generate_presigned_post(
			Bucket=self.bucket,
			Key=self.object_key(key, is_private),
			Conditions=[["content-length-range", size, size]],
			ExpiresIn=UPLOAD_TARGET_TTL,
		)
		return {"mode": "direct", "url": post["url"], "fields": post["fields"]}
