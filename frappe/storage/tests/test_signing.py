# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import io
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import frappe
import frappe.storage
from frappe.storage.url import make_signature, signed_url, verify_signature
from frappe.tests import IntegrationTestCase


class TestSigning(IntegrationTestCase):
	"""Sign/verify roundtrip and signed_url behavior.

	Uses only the storage core: blobs come from put_blob under fake(),
	and File rows are stand-in dicts (the File.blob field is owned by a
	later stage)."""

	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	@staticmethod
	def make_blob(content: bytes = b"signing test content", is_private: bool = True):
		with frappe.storage.fake():
			return frappe.storage.put_blob(io.BytesIO(content), is_private=is_private)

	def test_sign_verify_roundtrip(self):
		expires = int(time.time()) + 60
		sig = make_signature("blob-1", "a.txt", expires)
		self.assertTrue(verify_signature("blob-1", "a.txt", expires, sig))
		# expires arrives as a query-string value in practice
		self.assertTrue(verify_signature("blob-1", "a.txt", str(expires), sig))

	def test_expired_token_rejected(self):
		expires = int(time.time()) - 1
		sig = make_signature("blob-1", "a.txt", expires)
		self.assertFalse(verify_signature("blob-1", "a.txt", expires, sig))

	def test_tampered_values_rejected(self):
		expires = int(time.time()) + 60
		sig = make_signature("blob-1", "a.txt", expires)

		flipped = sig[:-1] + ("0" if sig[-1] != "0" else "1")
		self.assertFalse(verify_signature("blob-1", "a.txt", expires, flipped))
		# a different filename, blob or expiry must invalidate the signature
		self.assertFalse(verify_signature("blob-1", "b.txt", expires, sig))
		self.assertFalse(verify_signature("blob-2", "a.txt", expires, sig))
		self.assertFalse(verify_signature("blob-1", "a.txt", expires + 1, sig))
		# junk inputs must fail closed, not raise
		self.assertFalse(verify_signature("blob-1", "a.txt", "not-a-number", sig))
		self.assertFalse(verify_signature("blob-1", "a.txt", None, sig))
		self.assertFalse(verify_signature("blob-1", "a.txt", expires, ""))
		self.assertFalse(verify_signature("blob-1", "a.txt", expires, None))

	def test_ttl_respected(self):
		blob = self.make_blob()
		file = frappe._dict(blob=blob.name, file_name="a.txt")

		before = int(time.time())
		url = signed_url(file, expires_in=120)
		after = int(time.time())

		query = parse_qs(urlparse(url).query)
		expires = int(query["e"][0])
		sig = query["s"][0]

		self.assertGreaterEqual(expires, before + 120)
		self.assertLessEqual(expires, after + 120)
		self.assertTrue(verify_signature(blob.name, "a.txt", expires, sig))

		# valid at the expiry second, rejected one second later
		with patch("frappe.storage.url.time.time", return_value=float(expires)):
			self.assertTrue(verify_signature(blob.name, "a.txt", expires, sig))
		with patch("frappe.storage.url.time.time", return_value=float(expires + 1)):
			self.assertFalse(verify_signature(blob.name, "a.txt", expires, sig))

	def test_signed_url_falls_back_to_f_path(self):
		# MemoryDriver.download_url returns None, so signed_url must build /f/
		blob = self.make_blob()
		file = frappe._dict(blob=blob.name, file_name="hello world.txt")

		url = signed_url(file)

		self.assertTrue(url.startswith(f"/f/{blob.name}/hello%20world.txt?"))
		query = parse_qs(urlparse(url).query)
		self.assertTrue(
			verify_signature(blob.name, "hello world.txt", query["e"][0], query["s"][0])
		)

	def test_native_url_preferred(self):
		blob = self.make_blob(b"native url content")
		file = frappe._dict(blob=blob.name, file_name="a.txt")
		# signed_url resolves the driver by blob.driver name, so patch the
		# registry instance, not the fake() override
		driver = frappe.storage.get_driver(blob.driver)
		native = "https://storage.example.com/presigned/a.txt"

		with patch.object(driver, "download_url", return_value=native) as mocked:
			self.assertEqual(signed_url(file, expires_in=900), native)

		mocked.assert_called_once_with(blob.key, "a.txt", 900)
		# without a native URL the same file falls back to /f/
		self.assertTrue(signed_url(file).startswith("/f/"))

	def test_signature_is_stable_for_same_inputs(self):
		expires = int(time.time()) + 60
		self.assertEqual(
			make_signature("blob-1", "a.txt", expires),
			make_signature("blob-1", "a.txt", expires),
		)
