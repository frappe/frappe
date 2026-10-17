# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import base64
import hashlib
import importlib.util
import io
import json
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import frappe
from frappe.storage.blob import put_blob
from frappe.storage.driver import get_driver_classes
from frappe.storage.memory_driver import MemoryDriver
from frappe.storage.s3_driver import UPLOAD_TARGET_TTL, S3Driver
from frappe.storage.serve import serve_public_file
from frappe.storage.tests import use_driver
from frappe.storage.upload import upload_key
from frappe.storage.url import signed_url_for_blob
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request

HAS_BOTO3 = importlib.util.find_spec("boto3") is not None

TEST_DB_NAME = "s3_test_site_db"

TEST_CONFIG = {
	"bucket": "test-bucket",
	"region": "eu-central-1",
	"endpoint_url": "https://s3.example.com",
	"access_key_id": "AKIATEST",
	"secret_access_key": "secret",
}


class StubClientError(Exception):
	"""Stands in for botocore.exceptions.ClientError."""

	def __init__(self, code):
		super().__init__(code)
		self.response = {"Error": {"Code": code}}


def site_config(**config):
	"""Patch frappe.conf with a storage_driver_config."""
	return patch.object(
		frappe, "conf", frappe._dict(db_name=TEST_DB_NAME, storage_driver_config=frappe._dict(config))
	)


@contextmanager
def stubbed_boto3():
	"""Yield the fake s3 client an S3Driver built in this context will use.

	Injects fake boto3/botocore modules into sys.modules, so these tests run
	with or without the real library installed."""
	client = MagicMock(name="s3_client")
	boto3_mod = MagicMock(name="boto3")
	boto3_mod.client.return_value = client
	botocore_exceptions = MagicMock(name="botocore.exceptions")
	botocore_exceptions.ClientError = StubClientError
	modules = {
		"boto3": boto3_mod,
		"botocore": MagicMock(name="botocore"),
		"botocore.config": MagicMock(name="botocore.config"),
		"botocore.exceptions": botocore_exceptions,
	}
	with patch.dict(sys.modules, modules):
		client.boto3_module = boto3_mod
		yield client


def make_driver(**config):
	with stubbed_boto3() as client, site_config(**(config or TEST_CONFIG)):
		driver = S3Driver()
	driver.test_client = client
	return driver


class TestS3DriverConfig(IntegrationTestCase):
	def test_s3_is_a_builtin_driver_configured_from_site_config(self):
		self.assertEqual(get_driver_classes()["s3"], "frappe.storage.s3_driver.S3Driver")

		call = make_driver(**TEST_CONFIG).test_client.boto3_module.client.call_args
		self.assertEqual(call.args, ("s3",))
		self.assertEqual(call.kwargs["region_name"], "eu-central-1")
		self.assertEqual(call.kwargs["endpoint_url"], "https://s3.example.com")
		self.assertEqual(call.kwargs["aws_access_key_id"], "AKIATEST")
		self.assertEqual(call.kwargs["aws_secret_access_key"], "secret")

		# anything left out falls back to boto3's own defaults and credential chain
		kwargs = make_driver(bucket="test-bucket").test_client.boto3_module.client.call_args.kwargs
		for name in ("aws_access_key_id", "aws_secret_access_key", "region_name", "endpoint_url"):
			self.assertNotIn(name, kwargs)

	def test_unusable_config_raises_a_clear_error(self):
		with self.subTest("no bucket"), site_config(region="eu-central-1"):
			self.assertRaisesRegex(frappe.ValidationError, "bucket", S3Driver)
		with self.subTest("no config"), patch.object(frappe, "conf", frappe._dict()):
			self.assertRaisesRegex(frappe.ValidationError, "bucket", S3Driver)
		# sys.modules[name] = None forces ImportError even if boto3 is installed
		with (
			self.subTest("no boto3"),
			patch.dict(sys.modules, {"boto3": None}),
			site_config(bucket="test-bucket"),
		):
			self.assertRaisesRegex(frappe.ValidationError, "pip install boto3", S3Driver)


class TestS3SitePrefix(IntegrationTestCase):
	"""Sites sharing one bucket keep their objects under their own prefix."""

	def test_prefix_defaults_to_a_hash_of_the_database_name_or_is_configured(self):
		expected = hashlib.sha256(TEST_DB_NAME.encode()).hexdigest()[:12] + "/"
		self.assertEqual(make_driver(**TEST_CONFIG).key_prefix, expected)

		self.assertEqual(make_driver(**TEST_CONFIG, prefix="tenant-a.v2").key_prefix, "tenant-a.v2/")
		self.assertEqual(make_driver(**TEST_CONFIG, prefix="/tenant-a/").key_prefix, "tenant-a/")
		for invalid in ("tenant a", "tenant/a", "../tenant"):
			with self.subTest(prefix=invalid), self.assertRaises(frappe.ValidationError):
				make_driver(**TEST_CONFIG, prefix=invalid)

	def test_new_keys_start_with_the_prefix_and_delete_stays_inside_it(self):
		driver = make_driver(**TEST_CONFIG, prefix="tenant-a")
		client = driver.test_client
		self.addCleanup(frappe.db.rollback)

		with use_driver(driver):
			blob = put_blob(io.BytesIO(b"prefixed bytes"), is_private=True, filename="report.pdf")
			self.assertEqual(upload_key("upload123"), "tenant-a/uploads/upload123")
		self.assertEqual(blob.key, f"tenant-a/{blob.name}/report.pdf")
		client.upload_fileobj.assert_called_once()
		self.assertEqual(client.upload_fileobj.call_args.args[2], f"private/tenant-a/{blob.name}/report.pdf")

		driver.delete(blob.key, is_private=True)
		client.delete_object.assert_called_once_with(
			Bucket="test-bucket", Key=f"private/tenant-a/{blob.name}/report.pdf"
		)

		# another site's object, such as one a restored backup points at
		client.delete_object.reset_mock()
		driver.delete(f"tenant-b/{blob.name}/report.pdf", is_private=True)
		driver.delete("legacy/report.pdf")
		client.delete_object.assert_not_called()


class TestS3DriverBehavior(IntegrationTestCase):
	"""Behavior tests against a stubbed boto3 client. Run without boto3."""

	def setUp(self):
		super().setUp()
		self.driver = make_driver(**TEST_CONFIG)
		self.client = self.driver.test_client
		self.key = f"{self.driver.key_prefix}abcdef0123/report.pdf"

	def presigned_params(self) -> dict:
		return self.client.generate_presigned_url.call_args.kwargs["Params"]

	def test_objects_live_under_their_namespace(self):
		for is_private, namespace in ((False, "public"), (True, "private")):
			with self.subTest(namespace=namespace):
				self.client.reset_mock()
				object_key = {"Bucket": "test-bucket", "Key": f"{namespace}/{self.key}"}
				body = io.BytesIO(b"stored bytes")
				self.client.get_object.return_value = {"Body": body}

				stream = io.BytesIO(b"hello")
				self.driver.write(self.key, stream, is_private=is_private)
				self.client.upload_fileobj.assert_called_once_with(stream, "test-bucket", object_key["Key"])

				self.assertIs(self.driver.read(self.key, is_private=is_private), body)
				self.client.get_object.assert_called_with(**object_key)
				# ranges use S3's native Range header
				self.assertIs(self.driver.read_range(self.key, 10, 19, is_private=is_private), body)
				self.client.get_object.assert_called_with(**object_key, Range="bytes=10-19")
				self.assertIs(self.driver.read_range(self.key, 10, None, is_private=is_private), body)
				self.client.get_object.assert_called_with(**object_key, Range="bytes=10-")

				self.assertTrue(self.driver.exists(self.key, is_private=is_private))
				self.client.head_object.assert_called_once_with(**object_key)

				self.driver.delete(self.key, is_private=is_private)
				self.client.delete_object.assert_called_once_with(**object_key)

	def test_missing_objects_and_client_errors(self):
		self.client.head_object.side_effect = StubClientError("404")
		self.assertFalse(self.driver.exists(self.key, is_private=True))
		self.client.get_object.side_effect = StubClientError("NoSuchKey")
		self.assertRaises(FileNotFoundError, self.driver.read, self.key)

		# any other error propagates
		self.client.head_object.side_effect = StubClientError("AccessDenied")
		self.client.get_object.side_effect = StubClientError("AccessDenied")
		self.assertRaises(StubClientError, self.driver.exists, self.key)
		self.assertRaises(StubClientError, self.driver.read, self.key)

	def test_download_url_is_a_presigned_get(self):
		self.client.generate_presigned_url.return_value = "https://signed.example.com/x"
		url = self.driver.download_url(self.key, "report.pdf", 300, is_private=True)
		self.assertEqual(url, "https://signed.example.com/x")

		call = self.client.generate_presigned_url.call_args
		self.assertEqual(call.args, ("get_object",))
		self.assertEqual(call.kwargs["ExpiresIn"], 300)
		self.assertEqual(self.presigned_params()["Bucket"], "test-bucket")
		self.assertEqual(self.presigned_params()["Key"], f"private/{self.key}")

		# is_private defaults to False
		self.driver.download_url(self.key, "logo.png", 60)
		self.assertEqual(self.presigned_params()["Key"], f"public/{self.key}")

	def test_download_url_disposition(self):
		self.driver.download_url(self.key, "report.pdf", 60, mime_type="application/pdf")
		self.assertEqual(
			self.presigned_params()["ResponseContentDisposition"],
			"inline; filename=\"report.pdf\"; filename*=UTF-8''report.pdf",
		)

		downloads = (
			("report.pdf", "application/pdf", True),
			("page.html", "text/html", False),
			("logo.svg", "image/svg+xml", False),
			("feed.xml", "application/octet-stream", False),
			("app.js", "application/octet-stream", False),
			# the filename is caller-chosen: an HTML blob named .txt still downloads
			("notes.txt", "text/html", False),
		)
		for filename, mime_type, as_attachment in downloads:
			with self.subTest(filename=filename, mime_type=mime_type):
				self.driver.download_url(
					self.key, filename, 60, mime_type=mime_type, as_attachment=as_attachment
				)
				self.assertTrue(
					self.presigned_params()["ResponseContentDisposition"].startswith("attachment; ")
				)

		self.driver.download_url(self.key, 'we"ird nämé/\r\n.pdf', 60)
		disposition = self.presigned_params()["ResponseContentDisposition"]
		# no quote, backslash or line break may survive in the quoted-string
		self.assertIn('filename="weird nm/.pdf"', disposition)
		self.assertNotIn("\r", disposition)
		self.assertNotIn("\n", disposition)
		self.assertIn("filename*=UTF-8''we%22ird%20n%C3%A4m%C3%A9%2F%0D%0A.pdf", disposition)

	def test_download_url_content_type(self):
		cases = [
			("report.pdf", "application/pdf", "application/pdf"),
			# an unsniffed blob is typed by its filename
			("notes.txt", "application/octet-stream", "text/plain"),
			("report.pdf", None, "application/pdf"),
			("data.unknownext", "application/octet-stream", "application/octet-stream"),
			# a sniffed type wins over the filename
			("photo.txt", "image/png", "image/png"),
		]
		for filename, mime_type, served in cases:
			with self.subTest(filename=filename, mime_type=mime_type):
				self.driver.download_url(self.key, filename, 60, mime_type=mime_type)
				self.assertEqual(self.presigned_params()["ResponseContentType"], served)

	def test_upload_target_is_a_presigned_post(self):
		fields = {"key": "private/uploads/xyz", "policy": "p", "x-amz-signature": "s"}
		self.client.generate_presigned_post.return_value = {
			"url": "https://test-bucket.s3.example.com",
			"fields": fields,
		}
		target = self.driver.upload_target("uploads/xyz", 1024, is_private=True)
		self.assertEqual(
			target, {"mode": "direct", "url": "https://test-bucket.s3.example.com", "fields": fields}
		)

		call = self.client.generate_presigned_post.call_args
		self.assertEqual(call.kwargs["Bucket"], "test-bucket")
		self.assertEqual(call.kwargs["Key"], "private/uploads/xyz")
		self.assertEqual(call.kwargs["ExpiresIn"], UPLOAD_TARGET_TTL)
		self.assertIn(["content-length-range", 1024, 1024], call.kwargs["Conditions"])


@unittest.skipUnless(HAS_BOTO3, "boto3 not installed")
class TestS3DriverWithRealBoto3(IntegrationTestCase):
	"""Presigning is offline in boto3; this needs the real lib, not a bucket."""

	def setUp(self):
		super().setUp()
		with site_config(**TEST_CONFIG):
			self.driver = S3Driver()

	def test_presigned_get_and_post(self):
		url = self.driver.download_url(
			"ab/cd/deadbeef", "report.pdf", 300, is_private=True, mime_type="application/pdf"
		)
		parsed = urlparse(url)
		query = parse_qs(parsed.query)
		self.assertTrue(parsed.path.endswith("/private/ab/cd/deadbeef"))
		self.assertEqual(query["X-Amz-Expires"], ["300"])
		self.assertIn("X-Amz-Signature", query)
		self.assertEqual(query["response-content-type"], ["application/pdf"])
		disposition = query["response-content-disposition"][0]
		self.assertTrue(disposition.startswith("inline; "))
		self.assertIn("report.pdf", disposition)

		target = self.driver.upload_target("uploads/abc123", 2048, is_private=True)
		self.assertEqual(target["mode"], "direct")
		self.assertEqual(target["fields"]["key"], "private/uploads/abc123")
		policy = json.loads(base64.b64decode(target["fields"]["policy"]))
		self.assertIn(["content-length-range", 2048, 2048], policy["conditions"])


class TestS3ServesLikeLocal(IntegrationTestCase):
	"""A file shows inline or downloads the same way from S3 as from Frappe.

	Blobs are stored through the stubbed S3 driver, so the presigned URL the
	serve route redirects to can be inspected. The other side streams the
	same bytes from memory through the same ``/files/`` route."""

	PDF = b"%PDF-1.4\n1 0 obj << >> endobj\ntrailer << >>\n%%EOF\n"
	CASES = (
		# (content, filename, served type, downloads without being asked)
		(PDF, "report.pdf", "application/pdf", False),
		(b"plain notes", "notes.txt", "text/plain", False),
		(b"<!doctype html><p>hi</p>", "page.html", "text/html", True),
		(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "logo.svg", "image/svg+xml", True),
	)

	def setUp(self):
		super().setUp()
		self.driver = make_driver(**TEST_CONFIG)
		self.driver.test_client.generate_presigned_url.return_value = "https://signed.example.com/x"
		self.memory = MemoryDriver()
		frappe.local.storage_driver_override = self.driver

	def tearDown(self):
		frappe.local.storage_driver_override = None
		frappe.local.form_dict = frappe._dict()
		if hasattr(frappe.local, "request"):
			del frappe.local.request
		frappe.db.rollback()
		super().tearDown()

	def presigned_params(self) -> dict:
		return self.driver.test_client.generate_presigned_url.call_args.kwargs["Params"]

	def serve(self, blob, filename: str, **query):
		path = f"/files/{blob.name}/{filename}"
		set_request(method="GET", path=path)
		frappe.local.form_dict = frappe._dict(query)
		return serve_public_file(path)

	def s3_served(self, blob, filename: str, **query) -> tuple[str, str]:
		"""Serve through ``/files/`` and read what the S3 redirect target will send."""
		response = self.serve(blob, filename, **query)
		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.headers["Location"], "https://signed.example.com/x")
		# a public redirect is cached for half the presigned URL's hour
		self.assertEqual(response.headers["Cache-Control"], "public, max-age=1800")
		self.assertEqual(self.driver.test_client.generate_presigned_url.call_args.kwargs["ExpiresIn"], 3600)
		params = self.presigned_params()
		return params["ResponseContentType"], params["ResponseContentDisposition"].split(";")[0]

	def local_served(self, content: bytes, filename: str, **query) -> tuple[str, str]:
		"""Serve the same bytes through ``/files/`` from a driver with no native URL."""
		with use_driver(self.memory):
			response = self.serve(put_blob(io.BytesIO(content)), filename, **query)
		self.assertEqual(response.status_code, 200)
		return response.mimetype, response.headers["Content-Disposition"].split(";")[0]

	def test_s3_and_local_agree_on_type_and_disposition(self):
		for content, filename, served, downloads in self.CASES:
			blob = put_blob(io.BytesIO(content))
			for query, expected in (
				({}, "attachment" if downloads else "inline"),
				({"download": "1"}, "attachment"),
			):
				with self.subTest(filename=filename, query=query):
					self.assertEqual(self.s3_served(blob, filename, **query), (served, expected))
					self.assertEqual(self.local_served(content, filename, **query), (served, expected))

	def test_signed_url_for_blob_can_ask_for_a_download(self):
		blob = put_blob(io.BytesIO(self.PDF), is_private=True)

		self.assertEqual(signed_url_for_blob(blob, "report.pdf"), "https://signed.example.com/x")
		self.assertEqual(self.presigned_params()["ResponseContentType"], "application/pdf")
		self.assertTrue(self.presigned_params()["ResponseContentDisposition"].startswith("inline; "))

		signed_url_for_blob(blob, "report.pdf", as_attachment=True)
		self.assertTrue(self.presigned_params()["ResponseContentDisposition"].startswith("attachment; "))

		# without a native URL the same request falls back to a signed path that downloads
		with use_driver(self.memory):
			local = put_blob(io.BytesIO(self.PDF), is_private=True)
			self.assertIn("&download=1", signed_url_for_blob(local, "report.pdf", as_attachment=True))
			self.assertNotIn("download=", signed_url_for_blob(local, "report.pdf"))
