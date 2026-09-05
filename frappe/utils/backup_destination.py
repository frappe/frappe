# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Destinations a backup can be written to as it is produced.

A destination hands back a writable file descriptor and nothing else. The backup
pipeline - `mariadb-dump | gzip | gpg` - writes to that descriptor exactly as it
would write to a file, so no part of *producing* a backup needs to know where it
lands. For a local backup the descriptor is the file; for S3 it is one end of a
pipe whose other end is being fed to a multipart upload as the bytes arrive, so
a multi-GB dump is never staged on disk.
"""

import contextlib
import os
import queue
import threading

import frappe
from frappe import _

# S3 accepts at most 10,000 parts per upload and at least 5 MiB per part (the
# last one excepted), so the chunk size caps the object size: 16 MiB gives a
# 160 GiB ceiling, and pick_chunk_size() raises it for anything larger.
#
# Chunk size is also how long the producer can be stalled. A part is uploaded
# while the next one is being read, so once both are occupied the dump waits
# chunk_size / throughput seconds for the in-flight part to land. That wait has
# to stay well under the database's net_write_timeout (60s on MariaDB by
# default) or the server aborts the dump mid-backup. At a sluggish 1.5 MiB/s a
# 16 MiB part waits ~11s; a 64 MiB one waits ~45s, which is close enough to the
# limit that a single hiccup kills a backup that has been running for an hour.
DEFAULT_CHUNK_SIZE = 16 * 1024**2
MIN_CHUNK_SIZE = 5 * 1024**2
MAX_PARTS = 10_000

# Site config key holding the whole offsite destination as one nested object.
OFFSITE_BACKUP_CONFIG_KEY = "offsite_backup_config"

SUPPORTED_TYPES = ("s3",)

# Settings a streamed backup cannot be attempted without. `path` is deliberately
# absent: an empty prefix means the bucket root, which is a real answer rather
# than a missing one.
REQUIRED_SETTINGS = ("endpoint", "bucket", "region")


def get_backup_destination(
	*,
	endpoint: str | None = None,
	bucket: str | None = None,
	path: str | None = None,
	region: str | None = None,
	access_key: str | None = None,
	secret_key: str | None = None,
	session_token: str | None = None,
	config: dict | None = None,
):
	"""Resolve where a streamed backup goes.

	Command line arguments win; anything not given falls back to the
	`offsite_backup_config` key in site config. That way an ad-hoc `bench backup`
	can point somewhere else without editing config, while a scheduled backup
	keeps its credentials out of the process table.
	"""
	config = dict(config if config is not None else frappe.conf.get(OFFSITE_BACKUP_CONFIG_KEY) or {})

	destination_type = config.get("type", "s3")
	if destination_type not in SUPPORTED_TYPES:
		frappe.throw(
			_("Unsupported backup destination type {0}. Supported: {1}").format(
				destination_type, ", ".join(SUPPORTED_TYPES)
			)
		)

	def setting(name, override):
		return override if override is not None else config.get(name)

	resolved = {
		name: setting(name, value)
		for name, value in {
			"endpoint": endpoint,
			"bucket": bucket,
			"region": region,
			"access_key": access_key,
			"secret_key": secret_key,
			# Present for temporary credentials (STS AssumeRole and the
			# equivalents on MinIO, Ceph and R2); absent for long-lived keys.
			"session_token": session_token,
		}.items()
	}

	# Everything that is missing is reported at once. Finding out about the second
	# missing setting only after fixing the first is a miserable way to configure
	# something that otherwise only runs at 4am.
	missing = [name for name in REQUIRED_SETTINGS if not resolved[name]]

	if bool(resolved["access_key"]) != bool(resolved["secret_key"]):
		missing.append("access_key + secret_key (give both, or neither)")
	elif not resolved["access_key"] and not has_ambient_credentials():
		missing.append("access_key + secret_key (or credentials boto3 can find itself)")

	if missing:
		frappe.throw(
			_("Offsite backup destination is incomplete. Missing: {0}.").format(", ".join(missing))
			+ " "
			+ _("Pass them as --s3-* options or set them under `{0}` in site config.").format(
				OFFSITE_BACKUP_CONFIG_KEY
			)
		)

	return S3Destination(
		bucket=resolved["bucket"],
		prefix=setting("path", path) or "",
		endpoint_url=resolved["endpoint"],
		region=resolved["region"],
		access_key=resolved["access_key"],
		secret_key=resolved["secret_key"],
		session_token=resolved["session_token"],
		addressing_style=config.get("addressing_style", "auto"),
		storage_class=config.get("storage_class"),
		chunk_size=config.get("chunk_size"),
		connect_timeout=config.get("connect_timeout", 60),
		read_timeout=config.get("read_timeout", 300),
		max_attempts=config.get("max_attempts", 10),
	)


def has_ambient_credentials() -> bool:
	"""Whether boto3 can find credentials without being handed any.

	An instance profile or the standard AWS_* environment variables are a
	legitimate way to run this, so absent keys are only an error when nothing
	else supplies them either.
	"""
	try:
		import boto3

		return boto3.Session().get_credentials() is not None
	except Exception:
		return False


def pick_chunk_size(expected_size: int, chunk_size: int | None = None) -> int:
	"""Return a part size that fits `expected_size` inside S3's 10,000 part limit."""
	chunk_size = chunk_size or DEFAULT_CHUNK_SIZE
	needed = -(-(expected_size or 0) // MAX_PARTS)  # ceiling division
	return max(MIN_CHUNK_SIZE, chunk_size, needed)


class S3Destination:
	"""An S3-compatible bucket - AWS, R2, MinIO, Wasabi, B2, Spaces, Ceph.

	Auth is the same everywhere because it is the S3 protocol, not a per-provider
	design: an access key, a secret key and SigV4. Three settings absorb what does
	differ between providers, all of them settable from site config:

	    AWS       endpoint https://s3.<region>.amazonaws.com, real region
	    R2        endpoint https://<account>.r2.cloudflarestorage.com, region "auto"
	    B2        endpoint https://s3.<region>.backblazeb2.com, region must match it
	    Wasabi    endpoint https://s3.<region>.wasabisys.com
	    Spaces    endpoint https://<region>.digitaloceanspaces.com
	    MinIO     any endpoint, region usually "us-east-1",
	              addressing_style "path" (bucket.<host> won't resolve on an IP)

	Every artifact goes up as a multipart upload rather than a single `PUT`.
	That is not an optimisation: `put_object` needs the body's length up front
	and needs to rewind it to retry, and a pipe can do neither. Multipart also
	buys the property that matters most for a backup - the object does not exist
	until the last part is accepted, so a dump that dies halfway leaves nothing
	behind rather than an object that looks like a complete backup.
	"""

	def __init__(
		self,
		bucket: str,
		prefix: str = "",
		*,
		endpoint_url: str | None = None,
		region: str | None = None,
		access_key: str | None = None,
		secret_key: str | None = None,
		session_token: str | None = None,
		addressing_style: str = "auto",
		storage_class: str | None = None,
		chunk_size: int | None = None,
		connect_timeout: int = 60,
		read_timeout: int = 300,
		max_attempts: int = 10,
	):
		self.bucket = bucket
		self.prefix = prefix.strip("/")
		self.endpoint_url = endpoint_url
		self.region = region
		self.access_key = access_key
		self.secret_key = secret_key
		self.session_token = session_token
		self.addressing_style = addressing_style
		self.storage_class = storage_class
		self.chunk_size = pick_chunk_size(0, chunk_size)
		self.connect_timeout = connect_timeout
		self.read_timeout = read_timeout
		self.max_attempts = max_attempts

		# name -> bytes accepted, filled in as each artifact finishes uploading
		self.uploaded: dict[str, int] = {}

	def __repr__(self):
		return f"<S3Destination {self.url_for('')}>"

	def key_for(self, name: str) -> str:
		return f"{self.prefix}/{name}" if self.prefix else name

	def url_for(self, name: str) -> str:
		return f"s3://{self.bucket}/{self.key_for(name)}"

	def size_of(self, name: str) -> int | None:
		return self.uploaded.get(name)

	def get_client(self):
		"""Build an S3 client.

		Credentials are optional: leaving them out of the site config falls
		through to boto3's usual chain, so an instance role or the standard AWS_*
		environment variables work without putting long-lived keys on disk.
		"""
		try:
			import boto3
			from botocore.config import Config
		except ImportError:
			frappe.throw(
				_("boto3 is required to back up to {0}. Install it with `pip install boto3`.").format(
					self.url_for("")
				)
			)

		return boto3.client(
			"s3",
			endpoint_url=self.endpoint_url,
			region_name=self.region,
			aws_access_key_id=self.access_key,
			aws_secret_access_key=self.secret_key,
			aws_session_token=self.session_token,
			config=Config(
				signature_version="s3v4",
				s3={"addressing_style": self.addressing_style},
				connect_timeout=self.connect_timeout,
				read_timeout=self.read_timeout,
				# A streamed backup cannot be resumed: the dump is not rewindable, so
				# one part that exhausts its retries throws away however many GiB
				# already went up. Parts are held in memory and therefore always
				# safe to re-send, so retries are cheap insurance against the
				# transient connection drops a multi-hour upload will meet.
				retries={"max_attempts": self.max_attempts, "mode": "standard"},
				# botocore defaults both of these to "when_supported", which adds
				# x-amz-sdk-checksum-algorithm / x-amz-checksum-* headers to every
				# upload. AWS understands them; several S3-compatible providers
				# reject the request outright. "when_required" sends them only
				# where the API demands it, which is what keeps this working
				# against anything that speaks S3 rather than only against AWS.
				request_checksum_calculation="when_required",
				response_checksum_validation="when_supported",
			),
		)

	def verify(self):
		"""Fail now if the bucket can't be reached, rather than after the dump.

		A backup is a long, expensive thing to get to the end of. One HEAD against
		the bucket turns a wrong key or a mistyped bucket name into a
		two-hundred-millisecond error instead of an hour of dumping followed by one.
		"""
		from botocore.exceptions import BotoCoreError, ClientError

		try:
			self.get_client().head_bucket(Bucket=self.bucket)
		except ClientError as e:
			code = e.response.get("Error", {}).get("Code")
			if code in ("AccessDenied", "403"):
				# The credentials were good enough to be told "no" - the policy
				# just doesn't allow listing. Uploading may well be permitted, so
				# this isn't grounds to refuse the backup.
				return
			frappe.throw(_("Cannot reach backup destination {0}: {1}").format(self.url_for(""), code or e))
		except BotoCoreError as e:
			frappe.throw(_("Cannot reach backup destination {0}: {1}").format(self.url_for(""), e))

	def download_url(self, name: str, expires_in: int = 3600) -> str:
		"""A presigned URL that downloads `name` without credentials.

		A streamed backup leaves nothing on disk to serve, so this is how a
		finished artifact gets handed to someone: a signed, time-limited GET that
		carries its own authorisation.
		"""
		return self.get_client().generate_presigned_url(
			"get_object",
			Params={"Bucket": self.bucket, "Key": self.key_for(name)},
			ExpiresIn=expires_in,
		)

	@contextlib.contextmanager
	def stream(self, name: str, expected_size: int = 0):
		"""Yield a descriptor whose bytes become the object `name`.

		The upload runs on its own thread reading the other end of a pipe, so it
		overlaps with the dump instead of following it - and the pipe's own
		backpressure paces the dump to whatever the bucket can take.
		"""
		# Built here, on the caller's thread: reporting a configuration problem
		# needs frappe's thread-local context, and a missing boto3 or a malformed
		# endpoint should fail before the dump starts rather than halfway through.
		client = self.get_client()

		state = {"abort": False, "error": None, "size": 0}
		read_fd, write_fd = os.pipe()

		uploader = threading.Thread(
			target=self._upload,
			args=(client, name, read_fd, state, pick_chunk_size(expected_size, self.chunk_size)),
			name=f"backup-upload-{name}",
			daemon=True,
		)
		uploader.start()

		try:
			yield write_fd
		except BaseException as producer_error:
			state["abort"] = True
			os.close(write_fd)
			uploader.join()
			# A failed upload closes its end of the pipe, which usually kills the
			# dump with EPIPE a moment later. Report the upload failure - the
			# broken pipe is a symptom, not the cause.
			if state["error"]:
				raise state["error"] from producer_error
			raise
		else:
			os.close(write_fd)
			uploader.join()
			if state["error"]:
				raise state["error"]

		self.uploaded[name] = state["size"]

	def _upload(self, client, name: str, read_fd: int, state: dict, chunk_size: int):
		"""Drain the pipe into a multipart upload, reading and sending at once.

		Reading and uploading must overlap. Done sequentially, the pipe goes
		undrained for the whole duration of every `upload_part` - tens of seconds
		on a slow link - and a dump process blocked on write stops reading its own
		database socket, which MariaDB kills after `net_write_timeout` (60s by
		default). One chunk of lookahead keeps the producer fed while a part is in
		flight, at the cost of holding two chunks instead of one.
		"""
		key = self.key_for(name)
		upload_id = None
		chunks: queue.Queue = queue.Queue(maxsize=1)

		def drain_pipe():
			# Owning the descriptor here means every exit path closes it, so a
			# producer still writing fails fast on EPIPE rather than blocking on a
			# pipe nobody reads.
			try:
				with os.fdopen(read_fd, "rb") as source:
					while not state["abort"]:
						chunk = source.read(chunk_size)
						if not chunk:
							break
						chunks.put(chunk)
			except Exception as e:
				if not state["error"]:
					state["error"] = e
			finally:
				# Blocking, not put_nowait: if the queue happened to be full the
				# sentinel would be dropped and the consumer would wait on an
				# end-of-stream that never arrives. The consumer's `finally`
				# drains the queue, so this can always make progress.
				chunks.put(None)

		reader = threading.Thread(target=drain_pipe, name=f"backup-read-{name}", daemon=True)
		reader.start()

		try:
			parts = []
			size = 0
			upload_id = client.create_multipart_upload(**self._object_args(key))["UploadId"]

			while True:
				chunk = chunks.get()
				if chunk is None:
					break

				part = client.upload_part(
					Bucket=self.bucket,
					Key=key,
					PartNumber=len(parts) + 1,
					UploadId=upload_id,
					Body=chunk,
				)
				parts.append({"ETag": part["ETag"], "PartNumber": len(parts) + 1})
				size += len(chunk)

			if state["abort"] or state["error"]:
				# The producer or the reader failed; leave upload_id set so
				# `finally` aborts rather than completing a partial object.
				return

			if parts:
				client.complete_multipart_upload(
					Bucket=self.bucket,
					Key=key,
					UploadId=upload_id,
					MultipartUpload={"Parts": parts},
				)
			else:
				# A multipart upload with no parts cannot be completed, and an
				# empty artifact still has to exist.
				client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
				client.put_object(Body=b"", **self._object_args(key))

			upload_id = None
			state["size"] = size
		except Exception as e:
			state["error"] = e
		finally:
			# Release a reader parked on a full queue so it can close the pipe.
			state["abort"] = True
			while reader.is_alive():
				with contextlib.suppress(queue.Empty):
					chunks.get_nowait()
				reader.join(0.1)

			if upload_id:
				# Nothing here should mask the real failure, and an orphaned
				# upload is caught by the bucket's incomplete-upload lifecycle
				# rule anyway.
				with contextlib.suppress(Exception):
					client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)

	def _object_args(self, key: str) -> dict:
		args = {"Bucket": self.bucket, "Key": key}
		if self.storage_class:
			args["StorageClass"] = self.storage_class
		return args
