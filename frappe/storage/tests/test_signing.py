# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import io
import time
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import frappe
import frappe.storage
from frappe.storage.url import make_signature, signed_url, signed_url_for_blob, verify_signature
from frappe.tests import IntegrationTestCase


class TestSigning(IntegrationTestCase):
	"""Sign/verify roundtrip and signed_url behavior.

	Uses only the storage core: blobs come from put_blob under fake(),
	and File rows are stand-in dicts."""

	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	@staticmethod
	def make_blob(content: bytes = b"signing test content"):
		with frappe.storage.fake():
			return frappe.storage.put_blob(io.BytesIO(content), is_private=True)

	def assertSignedPath(self, url: str, blob_name: str, quoted: str, filename: str):
		self.assertTrue(url.startswith(f"/private/files/{blob_name}/{quoted}?"), url)
		query = parse_qs(urlparse(url).query)
		self.assertTrue(verify_signature(blob_name, filename, query["e"][0], query["s"][0]))

	def test_signature_verifies_only_its_own_inputs(self):
		expires = int(time.time()) + 60
		sig = make_signature("blob-1", "a.txt", expires)
		self.assertEqual(sig, make_signature("blob-1", "a.txt", expires))
		self.assertTrue(verify_signature("blob-1", "a.txt", expires, sig))
		# expires arrives as a query-string value in practice
		self.assertTrue(verify_signature("blob-1", "a.txt", str(expires), sig))

		flipped = sig[:-1] + ("0" if sig[-1] != "0" else "1")
		past = int(time.time()) - 1
		rejected = (
			("blob-1", "a.txt", expires, flipped),
			("blob-1", "b.txt", expires, sig),
			("blob-2", "a.txt", expires, sig),
			("blob-1", "a.txt", expires + 1, sig),
			("blob-1", "a.txt", past, make_signature("blob-1", "a.txt", past)),
			# junk inputs must fail closed, not raise
			("blob-1", "a.txt", "not-a-number", sig),
			("blob-1", "a.txt", None, sig),
			("blob-1", "a.txt", expires, ""),
			("blob-1", "a.txt", expires, None),
		)
		for args in rejected:
			with self.subTest(args=args):
				self.assertFalse(verify_signature(*args))

	def test_signed_url_expires_after_its_ttl(self):
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

		# valid at the expiry second, rejected one second later
		with patch("frappe.storage.url.time.time", return_value=float(expires)):
			self.assertTrue(verify_signature(blob.name, "a.txt", expires, sig))
		with patch("frappe.storage.url.time.time", return_value=float(expires + 1)):
			self.assertFalse(verify_signature(blob.name, "a.txt", expires, sig))

	def test_signed_url_falls_back_to_a_signed_private_files_path(self):
		# MemoryDriver.download_url returns None, so the URL is a signed path
		blob = self.make_blob()

		url = signed_url(frappe._dict(blob=blob.name, file_name="hello world.txt"))
		self.assertSignedPath(url, blob.name, "hello%20world.txt", "hello world.txt")

		for blob_arg in (blob.name, blob):
			with self.subTest(blob_arg=blob_arg):
				url = signed_url_for_blob(blob_arg, "node name.txt")
				self.assertSignedPath(url, blob.name, "node%20name.txt", "node name.txt")

		# the filename stays in one path segment
		url = signed_url_for_blob(blob, "reports/q1 #final?.pdf")
		self.assertSignedPath(url, blob.name, "reports_q1%20_final_.pdf", "reports_q1 _final_.pdf")

	def test_native_url_preferred(self):
		blob = self.make_blob(b"native url content")
		file = frappe._dict(blob=blob.name, file_name="a.txt")
		# signed_url resolves the driver by blob.driver name, so patch the
		# registry instance, not the fake() override
		driver = frappe.storage.get_driver(blob.driver)
		native = "https://storage.example.com/presigned/a.txt"

		for sign, filename, ttl in (
			(lambda: signed_url(file, expires_in=900), "a.txt", 900),
			(lambda: signed_url_for_blob(blob, "node.txt", expires_in=120), "node.txt", 120),
		):
			with self.subTest(filename=filename):
				with patch.object(driver, "download_url", return_value=native) as mocked:
					self.assertEqual(sign(), native)
				mocked.assert_called_once_with(
					blob.key, filename, ttl, is_private=True, mime_type=blob.mime_type, as_attachment=False
				)

		# without a native URL the same file falls back to a signed path
		self.assertTrue(signed_url(file).startswith(f"/private/files/{blob.name}/a.txt?"))
