# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Tests for uploading backups straight to an S3-compatible bucket.

These stand in a fake client for boto3 so the multipart contract can be asserted
exactly: parts arrive in order, the object is completed only when every byte was
accepted, and a backup that dies mid-dump aborts instead of leaving a truncated
object that looks like a complete backup.
"""

import os
import threading
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase, timeout
from frappe.utils.backup_destination import (
	DEFAULT_CHUNK_SIZE,
	MAX_PARTS,
	MIN_CHUNK_SIZE,
	OFFSITE_BACKUP_CONFIG_KEY,
	S3Destination,
	get_backup_destination,
	pick_chunk_size,
)


class FakeS3Client:
	"""Records the multipart calls a destination makes, in order."""

	def __init__(self, fail_on: str | None = None, part_delay: float = 0.0):
		self.fail_on = fail_on
		self.part_delay = part_delay
		self.calls: list[str] = []
		self.parts: list[bytes] = []
		self.objects: dict[str, bytes] = {}
		self.aborted: list[str] = []
		self.storage_classes: list[str | None] = []

	def _check(self, name):
		self.calls.append(name)
		if self.fail_on == name:
			raise RuntimeError(f"s3 refused {name}")

	def create_multipart_upload(self, Bucket, Key, **kwargs):
		self._check("create_multipart_upload")
		self.storage_classes.append(kwargs.get("StorageClass"))
		return {"UploadId": "upload-1"}

	def upload_part(self, Bucket, Key, PartNumber, UploadId, Body):
		self._check("upload_part")
		if self.part_delay:
			time.sleep(self.part_delay)
		assert PartNumber == len(self.parts) + 1, "parts must arrive in order"
		self.parts.append(Body)
		return {"ETag": f'"etag-{PartNumber}"'}

	def complete_multipart_upload(self, Bucket, Key, UploadId, MultipartUpload):
		self._check("complete_multipart_upload")
		self.objects[Key] = b"".join(self.parts)
		return {}

	def abort_multipart_upload(self, Bucket, Key, UploadId):
		self.calls.append("abort_multipart_upload")
		self.aborted.append(Key)
		return {}

	def put_object(self, Bucket, Key, Body, **kwargs):
		self._check("put_object")
		self.objects[Key] = Body
		return {}


def destination_with(client, **kwargs) -> S3Destination:
	destination = S3Destination("my-bucket", "backups/site1", **kwargs)
	destination.get_client = lambda: client
	return destination


# the whole destination lives under one site config key, as one nested object
SITE_CONFIG = {
	"endpoint": "https://s3.ap-south-1.amazonaws.com",
	"bucket": "configured-bucket",
	"path": "backups/site1",
	"region": "ap-south-1",
	"access_key": "configured-key",
	"secret_key": "configured-secret",
}


class TestBackupDestinationConfig(UnitTestCase):
	def test_the_config_key_is_read_from_site_config(self):
		with patch.object(frappe, "conf", {OFFSITE_BACKUP_CONFIG_KEY: SITE_CONFIG}):
			destination = get_backup_destination()

		self.assertEqual(destination.bucket, "configured-bucket")

	def test_site_config_supplies_everything(self):
		destination = get_backup_destination(config=SITE_CONFIG)

		self.assertEqual(destination.bucket, "configured-bucket")
		self.assertEqual(destination.prefix, "backups/site1")
		self.assertEqual(destination.region, "ap-south-1")
		self.assertEqual(destination.access_key, "configured-key")
		self.assertEqual(destination.key_for("db.sql.gz"), "backups/site1/db.sql.gz")
		self.assertEqual(destination.url_for("db.sql.gz"), "s3://configured-bucket/backups/site1/db.sql.gz")

	def test_command_line_wins_per_setting(self):
		"""Each argument overrides its own config key and leaves the rest alone."""
		destination = get_backup_destination(bucket="asked-for", config=SITE_CONFIG)

		self.assertEqual(destination.bucket, "asked-for")
		self.assertEqual(destination.region, "ap-south-1")
		self.assertEqual(destination.secret_key, "configured-secret")

	def test_command_line_alone_needs_no_config(self):
		destination = get_backup_destination(
			endpoint="https://minio.local:9000",
			bucket="ad-hoc",
			region="us-east-1",
			access_key="key",
			secret_key="secret",
			config={},
		)

		self.assertEqual(destination.bucket, "ad-hoc")
		self.assertEqual(destination.endpoint_url, "https://minio.local:9000")
		# an absent path is the bucket root, not a missing setting
		self.assertEqual(destination.prefix, "")

	def test_an_incomplete_destination_names_everything_that_is_missing(self):
		"""One error listing every gap, not one error per gap."""
		with self.assertRaises(frappe.ValidationError) as raised:
			get_backup_destination(bucket="only-a-bucket", config={})

		message = str(raised.exception)
		self.assertIn("endpoint", message)
		self.assertIn("region", message)
		self.assertIn("secret_key", message)
		self.assertNotIn("bucket,", message)

	def test_half_a_credential_pair_is_refused(self):
		config = dict(SITE_CONFIG)
		del config["secret_key"]

		with self.assertRaises(frappe.ValidationError) as raised:
			get_backup_destination(config=config)

		self.assertIn("give both, or neither", str(raised.exception))

	def test_ambient_credentials_stand_in_for_missing_keys(self):
		"""An instance profile is a legitimate way to authenticate."""
		config = {k: v for k, v in SITE_CONFIG.items() if k not in ("access_key", "secret_key")}

		with patch("frappe.utils.backup_destination.has_ambient_credentials", return_value=True):
			destination = get_backup_destination(config=config)
		self.assertIsNone(destination.access_key)

		with patch("frappe.utils.backup_destination.has_ambient_credentials", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				get_backup_destination(config=config)

	def test_unknown_destination_types_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			get_backup_destination(config={"type": "gcs", "bucket": "my-bucket"})

	def test_chunk_size_grows_to_fit_the_object(self):
		self.assertEqual(pick_chunk_size(0), DEFAULT_CHUNK_SIZE)
		self.assertEqual(pick_chunk_size(1024), DEFAULT_CHUNK_SIZE)
		self.assertEqual(pick_chunk_size(0, 1024), MIN_CHUNK_SIZE)

		# an object too big for 10,000 default-sized parts gets bigger parts
		huge = DEFAULT_CHUNK_SIZE * MAX_PARTS * 2
		self.assertGreaterEqual(pick_chunk_size(huge) * MAX_PARTS, huge)


class TestS3Streaming(UnitTestCase):
	@timeout(60)
	def test_bytes_written_to_the_descriptor_become_an_object(self):
		client = FakeS3Client()
		destination = destination_with(client, chunk_size=MIN_CHUNK_SIZE)
		payload = os.urandom(MIN_CHUNK_SIZE * 2 + 17)

		with destination.stream("database.sql.gz") as fd:
			os.write(fd, payload)

		self.assertEqual(client.objects["backups/site1/database.sql.gz"], payload)
		self.assertEqual(len(client.parts), 3)
		self.assertIn("complete_multipart_upload", client.calls)
		self.assertEqual(destination.size_of("database.sql.gz"), len(payload))

	@timeout(60)
	def test_the_pipe_keeps_draining_while_a_part_uploads(self):
		"""Reading and uploading must overlap.

		Done sequentially, the pipe goes undrained for the whole duration of every
		upload_part. The dump process blocks on write, stops reading its own
		database socket, and MariaDB aborts the connection after
		net_write_timeout - which kills the backup tens of seconds in, with an
		error that points at the database and says nothing about the upload.
		"""
		part_seconds = 1.0
		client = FakeS3Client(part_delay=part_seconds)
		destination = destination_with(client, chunk_size=MIN_CHUNK_SIZE)

		stalls = []
		with destination.stream("database.sql.gz") as fd:
			for _ in range(6):
				started = time.monotonic()
				buf = memoryview(b"x" * (1024 * 1024))
				while buf:  # os.write on a pipe is free to write short
					buf = buf[os.write(fd, buf) :]
				stalls.append(time.monotonic() - started)

		self.assertLess(
			max(stalls),
			part_seconds * 0.9,
			f"writer stalled {max(stalls):.2f}s against a {part_seconds}s part upload,"
			" so the pipe was not being drained while the part was in flight",
		)

	@timeout(60)
	def test_storage_class_is_applied(self):
		client = FakeS3Client()
		destination = destination_with(client, storage_class="STANDARD_IA")

		with destination.stream("database.sql.gz") as fd:
			os.write(fd, b"dump")

		self.assertEqual(client.storage_classes, ["STANDARD_IA"])

	@timeout(60)
	def test_an_empty_artifact_still_becomes_an_object(self):
		client = FakeS3Client()
		destination = destination_with(client)

		with destination.stream("empty"):
			pass

		self.assertEqual(client.objects["backups/site1/empty"], b"")
		self.assertNotIn("complete_multipart_upload", client.calls)

	@timeout(60)
	def test_a_failed_dump_aborts_instead_of_completing(self):
		"""A backup that dies halfway must leave nothing behind.

		This is the whole reason for multipart over a single PUT: a truncated
		stream would otherwise land as an object that looks like a real backup.
		"""
		client = FakeS3Client()
		destination = destination_with(client, chunk_size=MIN_CHUNK_SIZE)

		with self.assertRaises(ValueError):
			with destination.stream("database.sql.gz") as fd:
				os.write(fd, b"a partial dump")
				raise ValueError("mariadb-dump died")

		self.assertNotIn("complete_multipart_upload", client.calls)
		self.assertEqual(client.aborted, ["backups/site1/database.sql.gz"])
		self.assertEqual(client.objects, {})
		self.assertIsNone(destination.size_of("database.sql.gz"))

	@timeout(60)
	def test_an_upload_failure_surfaces_instead_of_the_broken_pipe(self):
		"""When S3 rejects the upload the producer dies of EPIPE moments later.

		The EPIPE is a symptom; the caller needs to be told what S3 said.
		"""
		client = FakeS3Client(fail_on="create_multipart_upload")
		destination = destination_with(client)

		with self.assertRaises(RuntimeError) as raised:
			with destination.stream("database.sql.gz") as fd:
				# the upload has already collapsed, so this fails with EPIPE
				for _ in range(1000):
					os.write(fd, b"x" * 4096)

		self.assertIn("s3 refused create_multipart_upload", str(raised.exception))

	@timeout(60)
	def test_a_failure_mid_upload_is_reported(self):
		client = FakeS3Client(fail_on="upload_part")
		destination = destination_with(client, chunk_size=MIN_CHUNK_SIZE)

		with self.assertRaises(Exception):
			with destination.stream("database.sql.gz") as fd:
				os.write(fd, os.urandom(MIN_CHUNK_SIZE * 2))

		self.assertNotIn("complete_multipart_upload", client.calls)
		self.assertEqual(client.objects, {})

	@timeout(60)
	def test_the_upload_thread_never_outlives_the_context(self):
		client = FakeS3Client()
		destination = destination_with(client)
		before = threading.active_count()

		with destination.stream("database.sql.gz") as fd:
			os.write(fd, b"dump")

		self.assertEqual(threading.active_count(), before)


class TestBackupToDestination(IntegrationTestCase):
	@timeout(300)
	def test_a_real_backup_reaches_the_bucket(self):
		"""End to end: the dump pipeline writes into the uploader's pipe."""
		from frappe.utils.backups import new_backup

		client = FakeS3Client()
		destination = destination_with(client)

		odb = new_backup(ignore_files=True, force=True, destination=destination)

		database = os.path.basename(odb.backup_path_db)
		config = os.path.basename(odb.backup_path_conf)

		self.assertIn(f"backups/site1/{database}", client.objects)
		self.assertIn(f"backups/site1/{config}", client.objects)
		self.assertGreater(destination.size_of(database), 0)

		# nothing was staged on disk on the way out
		self.assertFalse(os.path.exists(odb.backup_path_db))
		self.assertFalse(os.path.exists(odb.backup_path_conf))

		summary = odb.get_summary()
		self.assertEqual(summary["database"]["path"], destination.url_for(database))
