# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import importlib.util
import io
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import frappe
from frappe.storage.driver import get_driver_classes
from frappe.storage.s3_driver import UPLOAD_TARGET_TTL, S3Driver
from frappe.tests import IntegrationTestCase

HAS_BOTO3 = importlib.util.find_spec("boto3") is not None

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
	return patch.object(frappe, "conf", frappe._dict(storage_driver_config=frappe._dict(config)))


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


class TestS3Registry(IntegrationTestCase):
	def test_s3_is_a_builtin_driver(self):
		classes = get_driver_classes()
		self.assertIn("s3", classes)
		self.assertEqual(classes["s3"], "frappe.storage.s3_driver.S3Driver")


class TestS3DriverConfig(IntegrationTestCase):
	def test_missing_bucket_raises(self):
		with site_config(region="eu-central-1"), self.assertRaisesRegex(frappe.ValidationError, "bucket"):
			S3Driver()

	def test_missing_config_raises(self):
		with patch.object(frappe, "conf", frappe._dict()), self.assertRaisesRegex(
			frappe.ValidationError, "bucket"
		):
			S3Driver()

	def test_missing_boto3_raises_clear_error(self):
		# sys.modules[name] = None forces ImportError even if boto3 is installed
		with (
			patch.dict(sys.modules, {"boto3": None}),
			site_config(bucket="test-bucket"),
			self.assertRaisesRegex(frappe.ValidationError, "pip install boto3"),
		):
			S3Driver()

	def test_config_reaches_boto3_client(self):
		driver = make_driver(**TEST_CONFIG)
		call = driver.test_client.boto3_module.client.call_args
		self.assertEqual(call.args, ("s3",))
		self.assertEqual(call.kwargs["region_name"], "eu-central-1")
		self.assertEqual(call.kwargs["endpoint_url"], "https://s3.example.com")
		self.assertEqual(call.kwargs["aws_access_key_id"], "AKIATEST")
		self.assertEqual(call.kwargs["aws_secret_access_key"], "secret")

	def test_credentials_default_to_boto3_chain(self):
		driver = make_driver(bucket="test-bucket")
		kwargs = driver.test_client.boto3_module.client.call_args.kwargs
		self.assertNotIn("aws_access_key_id", kwargs)
		self.assertNotIn("aws_secret_access_key", kwargs)
		self.assertNotIn("region_name", kwargs)
		self.assertNotIn("endpoint_url", kwargs)


class TestS3DriverBehavior(IntegrationTestCase):
	"""Behavior tests against a stubbed boto3 client. Run without boto3."""

	def setUp(self):
		super().setUp()
		self.driver = make_driver(**TEST_CONFIG)
		self.client = self.driver.test_client
		self.key = "ab/cd/abcdef0123456789"

	def test_write_streams_via_upload_fileobj(self):
		stream = io.BytesIO(b"hello")
		self.driver.write(self.key, stream)
		self.client.upload_fileobj.assert_called_once_with(stream, "test-bucket", f"public/{self.key}")

	def test_write_private_uses_private_prefix(self):
		stream = io.BytesIO(b"hello")
		self.driver.write(self.key, stream, is_private=True)
		self.client.upload_fileobj.assert_called_once_with(stream, "test-bucket", f"private/{self.key}")

	def test_read_returns_streaming_body(self):
		body = io.BytesIO(b"stored bytes")
		self.client.get_object.return_value = {"Body": body}
		stream = self.driver.read(self.key, is_private=True)
		self.assertIs(stream, body)
		self.assertEqual(stream.read(), b"stored bytes")
		self.client.get_object.assert_called_once_with(Bucket="test-bucket", Key=f"private/{self.key}")

	def test_read_missing_key_raises_file_not_found(self):
		self.client.get_object.side_effect = StubClientError("NoSuchKey")
		self.assertRaises(FileNotFoundError, self.driver.read, self.key)

	def test_read_other_errors_propagate(self):
		self.client.get_object.side_effect = StubClientError("AccessDenied")
		self.assertRaises(StubClientError, self.driver.read, self.key)

	def test_exists_true_on_head_object(self):
		self.client.head_object.return_value = {"ContentLength": 5}
		self.assertTrue(self.driver.exists(self.key))
		self.client.head_object.assert_called_once_with(Bucket="test-bucket", Key=f"public/{self.key}")

	def test_exists_false_on_404(self):
		self.client.head_object.side_effect = StubClientError("404")
		self.assertFalse(self.driver.exists(self.key, is_private=True))
		self.client.head_object.assert_called_once_with(Bucket="test-bucket", Key=f"private/{self.key}")

	def test_exists_other_errors_propagate(self):
		self.client.head_object.side_effect = StubClientError("AccessDenied")
		self.assertRaises(StubClientError, self.driver.exists, self.key)

	def test_delete_calls_delete_object(self):
		self.driver.delete(self.key, is_private=True)
		self.client.delete_object.assert_called_once_with(Bucket="test-bucket", Key=f"private/{self.key}")

	def test_download_url_presigned_get(self):
		self.client.generate_presigned_url.return_value = "https://signed.example.com/x"
		url = self.driver.download_url(self.key, "report.pdf", 300, is_private=True)
		self.assertEqual(url, "https://signed.example.com/x")

		call = self.client.generate_presigned_url.call_args
		self.assertEqual(call.args, ("get_object",))
		self.assertEqual(call.kwargs["ExpiresIn"], 300)
		params = call.kwargs["Params"]
		self.assertEqual(params["Bucket"], "test-bucket")
		self.assertEqual(params["Key"], f"private/{self.key}")
		self.assertIn("report.pdf", params["ResponseContentDisposition"])
		self.assertIn("attachment", params["ResponseContentDisposition"])

	def test_download_url_public_namespace(self):
		# is_private defaults to False: public namespace
		self.driver.download_url(self.key, "logo.png", 60)
		params = self.client.generate_presigned_url.call_args.kwargs["Params"]
		self.assertEqual(params["Key"], f"public/{self.key}")

	def test_download_url_quotes_filename(self):
		self.driver.download_url(self.key, 'we"ird nämé.pdf', 60)
		disposition = self.client.generate_presigned_url.call_args.kwargs["Params"][
			"ResponseContentDisposition"
		]
		# no raw quote character may survive inside the quoted-string
		self.assertNotIn('we"ird', disposition)
		self.assertIn("filename*=UTF-8''we%22ird%20n%C3%A4m%C3%A9.pdf", disposition)

	def test_upload_target_presigned_post(self):
		self.client.generate_presigned_post.return_value = {
			"url": "https://test-bucket.s3.example.com",
			"fields": {"key": "private/uploads/xyz", "policy": "p", "x-amz-signature": "s"},
		}
		target = self.driver.upload_target("uploads/xyz", 1024, is_private=True)
		self.assertEqual(
			target,
			{
				"mode": "direct",
				"url": "https://test-bucket.s3.example.com",
				"fields": {"key": "private/uploads/xyz", "policy": "p", "x-amz-signature": "s"},
			},
		)

		call = self.client.generate_presigned_post.call_args
		self.assertEqual(call.kwargs["Bucket"], "test-bucket")
		self.assertEqual(call.kwargs["Key"], "private/uploads/xyz")
		self.assertEqual(call.kwargs["ExpiresIn"], UPLOAD_TARGET_TTL)
		self.assertIn(["content-length-range", 1024, 1024], call.kwargs["Conditions"])


@unittest.skipUnless(HAS_BOTO3, "boto3 not installed")
class TestS3DriverWithRealBoto3(IntegrationTestCase):
	"""Presigning is offline in boto3; these need the real lib, not a bucket."""

	def make_real_driver(self):
		with site_config(**TEST_CONFIG):
			return S3Driver()

	def test_presigned_get_url_shape(self):
		from urllib.parse import parse_qs, urlparse

		driver = self.make_real_driver()
		url = driver.download_url("ab/cd/deadbeef", "report.pdf", 300, is_private=True)
		parsed = urlparse(url)
		query = parse_qs(parsed.query)
		self.assertTrue(parsed.path.endswith("/private/ab/cd/deadbeef"))
		self.assertEqual(query["X-Amz-Expires"], ["300"])
		self.assertIn("report.pdf", query["response-content-disposition"][0])
		self.assertIn("X-Amz-Signature", query)

	def test_presigned_post_shape(self):
		import base64
		import json

		driver = self.make_real_driver()
		target = driver.upload_target("uploads/abc123", 2048, is_private=True)
		self.assertEqual(target["mode"], "direct")
		self.assertEqual(target["fields"]["key"], "private/uploads/abc123")
		policy = json.loads(base64.b64decode(target["fields"]["policy"]))
		self.assertIn(["content-length-range", 2048, 2048], policy["conditions"])
