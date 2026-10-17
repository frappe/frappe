# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import io
import re
import time
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse

import frappe
import frappe.storage
from frappe.storage.email import (
	DEFAULT_EMAIL_URL_TTL,
	rewrite_text_urls_for_email,
	rewrite_urls_for_email,
)
from frappe.storage.tests import reset_file_controller
from frappe.storage.url import verify_signature
from frappe.tests import IntegrationTestCase
from frappe.utils import cint, get_url

SIGNED_BLOB_URL = re.compile(r"""(?:href|src)=["'](?P<url>[^"']*/private/files/[^"']+)["']""")


@contextmanager
def storage_v2_enabled():
	"""Enable storage_v2 in site conf for the duration of the block."""
	previous = frappe.conf.get("storage_v2")
	frappe.conf["storage_v2"] = 1
	reset_file_controller()
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_v2", None)
		else:
			frappe.conf["storage_v2"] = previous
		reset_file_controller()


@contextmanager
def email_url_ttl(seconds: int):
	previous = frappe.conf.get("storage_email_url_ttl")
	frappe.conf["storage_email_url_ttl"] = seconds
	try:
		yield
	finally:
		if previous is None:
			frappe.conf.pop("storage_email_url_ttl", None)
		else:
			frappe.conf["storage_email_url_ttl"] = previous


class TestEmailRewrite(IntegrationTestCase):
	"""rewrite_urls_for_email and its seam in the outgoing email build path."""

	def tearDown(self):
		frappe.db.rollback()
		super().tearDown()

	@staticmethod
	def make_blob(content: bytes = b"email rewrite test content", is_private: bool = True):
		"""A blob with one unattached File row owned by the session user."""
		with frappe.storage.fake():
			blob = frappe.storage.put_blob(io.BytesIO(content), is_private=is_private)
		file = frappe.new_doc("File")
		file.update({"file_name": "email.txt", "blob": blob.name, "is_private": cint(is_private)})
		file.name = frappe.generate_hash(length=10)
		file.owner = frappe.session.user
		file.db_insert()
		return blob

	@staticmethod
	def parse_signed(url: str):
		"""Split a signed private blob URL into (blob, filename, e, s)."""
		import html as html_lib

		# serializers may escape & as &amp; inside attributes
		parsed = urlparse(html_lib.unescape(url))
		blob, filename = parsed.path[len("/private/files/") :].split("/", 1)
		params = parse_qs(parsed.query)
		return blob, unquote(filename), params["e"][0], params["s"][0]

	def test_unsigned_url_becomes_signed_absolute(self):
		blob = self.make_blob()
		html = f'<p><a href="/private/files/{blob.name}/report.pdf">report</a></p>'

		with storage_v2_enabled():
			before = int(time.time())
			rewritten = rewrite_urls_for_email(html)

		self.assertNotEqual(rewritten, html)
		match = SIGNED_BLOB_URL.search(rewritten)
		self.assertIsNotNone(match)
		url = match.group("url")
		self.assertTrue(url.startswith(get_url().rstrip("/") + f"/private/files/{blob.name}/"))

		blob_name, filename, expires, signature = self.parse_signed(url)
		self.assertEqual(blob_name, blob.name)
		self.assertEqual(filename, "report.pdf")
		self.assertTrue(verify_signature(blob_name, filename, expires, signature))
		# default TTL is 30 days
		self.assertGreaterEqual(int(expires), before + DEFAULT_EMAIL_URL_TTL)
		self.assertLessEqual(int(expires), before + DEFAULT_EMAIL_URL_TTL + 10)

	def test_configured_ttl_respected(self):
		blob = self.make_blob()
		html = f'<img src="/private/files/{blob.name}/photo.png">'

		with storage_v2_enabled(), email_url_ttl(3600):
			before = int(time.time())
			rewritten = rewrite_urls_for_email(html)

		url = SIGNED_BLOB_URL.search(rewritten).group("url")
		blob_name, filename, expires, signature = self.parse_signed(url)
		self.assertTrue(verify_signature(blob_name, filename, expires, signature))
		self.assertGreaterEqual(int(expires), before + 3600)
		self.assertLessEqual(int(expires), before + 3600 + 10)

	def test_absolute_site_url_also_signed(self):
		blob = self.make_blob()
		site_url = get_url().rstrip("/")
		html = f'<a href="{site_url}/private/files/{blob.name}/a.txt">a</a>'

		with storage_v2_enabled():
			rewritten = rewrite_urls_for_email(html)

		self.assertNotEqual(rewritten, html)
		blob_name, filename, expires, signature = self.parse_signed(
			SIGNED_BLOB_URL.search(rewritten).group("url")
		)
		self.assertTrue(verify_signature(blob_name, filename, expires, signature))

	def test_already_signed_url_untouched(self):
		blob = self.make_blob()
		html = f'<a href="/private/files/{blob.name}/a.txt?e=1234567890&s=deadbeef">a</a>'

		with storage_v2_enabled():
			self.assertEqual(rewrite_urls_for_email(html), html)

	def test_other_urls_untouched(self):
		public = self.make_blob(b"email rewrite public content", is_private=False)
		private = self.make_blob()
		html = (
			'<a href="/files/plain.pdf">old</a>'
			'<img src="/private/files/x.png">'
			'<img src="/private/files/folder/inner/x.png">'
			f'<img src="/files/{public.name}/logo.png">'
			f'<a href="https://example.com/private/files/{private.name}/a.txt">foreign</a>'
			'<a href="mailto:someone@example.com">mail</a>'
		)
		with storage_v2_enabled():
			self.assertEqual(rewrite_urls_for_email(html), html)

	def test_blob_the_sender_cannot_download_left_unsigned(self):
		# a copied private URL must not become a signed link through email
		from frappe.storage.tests.test_file_integration import file_permissions_enforced

		secret = self.make_blob(b"email rewrite secret content")
		html = f'<a href="/private/files/{secret.name}/a.txt">a</a>'
		text = f"see /private/files/{secret.name}/a.txt"
		with storage_v2_enabled(), file_permissions_enforced(), self.set_user("test@example.com"):
			self.assertEqual(rewrite_urls_for_email(html), html)
			self.assertEqual(rewrite_text_urls_for_email(text), text)

			own = self.make_blob(b"email rewrite own content")
			own_html = f'<a href="/private/files/{own.name}/a.txt">a</a>'
			self.assertIsNotNone(SIGNED_BLOB_URL.search(rewrite_urls_for_email(own_html)))
			self.assertIn("&s=", rewrite_text_urls_for_email(f"see /private/files/{own.name}/a.txt"))

	def test_unknown_blob_left_alone(self):
		html = '<a href="/private/files/nosuchblob/a.txt">a</a>'
		with storage_v2_enabled():
			self.assertEqual(rewrite_urls_for_email(html), html)

	def test_flag_off_is_noop(self):
		blob = self.make_blob()
		html = f'<a href="/private/files/{blob.name}/a.txt">a</a>'
		frappe.conf.pop("storage_v2", None)
		self.assertEqual(rewrite_urls_for_email(html), html)

	def test_falsy_html_is_noop(self):
		with storage_v2_enabled():
			self.assertEqual(rewrite_urls_for_email(""), "")
			self.assertIsNone(rewrite_urls_for_email(None))

	def test_failure_returns_original_html(self):
		blob = self.make_blob()
		html = f'<a href="/private/files/{blob.name}/a.txt">a</a>'
		with (
			storage_v2_enabled(),
			patch("frappe.storage.url.make_signature", side_effect=Exception("boom")),
		):
			self.assertEqual(rewrite_urls_for_email(html), html)

	def test_seam_built_email_contains_signed_url(self):
		"""get_formatted_html is the seam every outgoing email passes through."""
		from frappe.email.email_body import get_formatted_html

		blob = self.make_blob()
		message = f'<p>see <a href="/private/files/{blob.name}/invoice.pdf">the invoice</a></p>'

		with storage_v2_enabled():
			# stub account: the test site has no outgoing Email Account
			html = get_formatted_html(
				"Test Subject",
				message,
				email_account=frappe._dict(name="Stub Email Account"),
				raw_html=True,
				add_css=False,
			)

		match = SIGNED_BLOB_URL.search(html)
		self.assertIsNotNone(match)
		blob_name, filename, expires, signature = self.parse_signed(match.group("url"))
		self.assertEqual(blob_name, blob.name)
		self.assertEqual(filename, "invoice.pdf")
		self.assertTrue(verify_signature(blob_name, filename, expires, signature))

	def test_stored_url_with_a_space_in_its_filename_is_signed(self):
		# a File's stored URL keeps the filename's spaces: /private/files/<blob>/my photo.png
		from frappe.email.email_body import get_formatted_html
		from frappe.storage.url import blob_url

		with frappe.storage.fake():
			blob = frappe.storage.put_blob(
				io.BytesIO(b"email rewrite photo with a space"), is_private=True, filename="my photo.png"
			)
		file = frappe.new_doc("File")
		file.update({"file_name": "my photo.png", "blob": blob.name, "is_private": 1})
		file.name = frappe.generate_hash(length=10)
		file.owner = frappe.session.user
		file.db_insert()
		message = f'<p><img src="{blob_url(blob)}"></p>'

		with storage_v2_enabled():
			html = get_formatted_html(
				"Test Subject",
				message,
				email_account=frappe._dict(name="Stub Email Account"),
				raw_html=True,
				add_css=False,
			)

		blob_name, filename, expires, signature = self.parse_signed(SIGNED_BLOB_URL.search(html).group("url"))
		self.assertEqual(blob_name, blob.name)
		self.assertEqual(filename, "my photo.png")
		self.assertTrue(verify_signature(blob_name, filename, expires, signature))

	def test_text_urls_signed(self):
		"""Bare private blob URLs in a plain-text body are signed too."""
		blob = self.make_blob()
		text = f"Download here: /private/files/{blob.name}/invoice.pdf\nThanks"

		with storage_v2_enabled():
			rewritten = rewrite_text_urls_for_email(text)

		self.assertNotEqual(rewritten, text)
		match = re.search(r"(?P<url>\S*/private/files/\S+)", rewritten)
		blob_name, filename, expires, signature = self.parse_signed(match.group("url"))
		self.assertEqual(blob_name, blob.name)
		self.assertEqual(filename, "invoice.pdf")
		self.assertTrue(verify_signature(blob_name, filename, expires, signature))
		self.assertTrue(rewritten.startswith("Download here: " + get_url()))
		self.assertTrue(rewritten.endswith("\nThanks"))

	def test_seam_text_part_contains_signed_url(self):
		"""An explicit text_content passed to set_html is signed as well."""
		import email as email_lib

		from frappe.email.email_body import get_email

		blob = self.make_blob()
		message = f'<p><a href="/private/files/{blob.name}/invoice.pdf">the invoice</a></p>'
		text = f"see /private/files/{blob.name}/invoice.pdf"

		with storage_v2_enabled():
			emailobj = get_email(
				recipients=["test_rewrite@example.com"],
				sender="test_rewrite@example.com",
				subject="Test Subject",
				content=message,
				text_content=text,
				email_account=frappe._dict(name="Stub Email Account"),
			)
			raw = emailobj.as_string()

		msg = email_lib.message_from_string(raw)
		text_part = next(
			part.get_payload(decode=True).decode("utf-8")
			for part in msg.walk()
			if part.get_content_type() == "text/plain"
		)
		match = re.search(r"(?P<url>\S*/private/files/\S+)", text_part)
		self.assertIsNotNone(match)
		blob_name, filename, expires, signature = self.parse_signed(match.group("url"))
		self.assertEqual(blob_name, blob.name)
		self.assertTrue(verify_signature(blob_name, filename, expires, signature))

	def test_seam_full_message_contains_signed_url(self):
		"""A fully built MIME message carries the signed URL in its html part."""
		from frappe.email.email_body import get_email

		blob = self.make_blob()
		message = f'<p><a href="/private/files/{blob.name}/invoice.pdf">the invoice</a></p>'

		with storage_v2_enabled():
			# builds the message only; nothing is sent
			emailobj = get_email(
				recipients=["test_rewrite@example.com"],
				sender="test_rewrite@example.com",
				subject="Test Subject",
				content=message,
				email_account=frappe._dict(name="Stub Email Account"),
			)
			raw = emailobj.as_string()

		import email as email_lib

		msg = email_lib.message_from_string(raw)
		html_part = next(
			part.get_payload(decode=True).decode("utf-8")
			for part in msg.walk()
			if part.get_content_type() == "text/html"
		)
		match = SIGNED_BLOB_URL.search(html_part)
		self.assertIsNotNone(match)
		blob_name, filename, expires, signature = self.parse_signed(match.group("url"))
		self.assertEqual(blob_name, blob.name)
		self.assertTrue(verify_signature(blob_name, filename, expires, signature))

	def test_rewriter_setup_failure_returns_original_html(self):
		"""A failure before any match (site URL lookup) never blocks sending."""
		blob = self.make_blob()
		html = f'<a href="/private/files/{blob.name}/a.txt">a</a>'

		with (
			storage_v2_enabled(),
			patch("frappe.storage.email.get_url", side_effect=Exception("boom")),
		):
			self.assertEqual(rewrite_urls_for_email(html), html)

	def test_rewriter_setup_failure_returns_original_text(self):
		"""Same guard on the plain-text body."""
		blob = self.make_blob()
		text = f"see /private/files/{blob.name}/a.txt"

		with (
			storage_v2_enabled(),
			patch("frappe.storage.email.get_url", side_effect=Exception("boom")),
		):
			self.assertEqual(rewrite_text_urls_for_email(text), text)

	def test_text_match_failure_leaves_that_url_unsigned(self):
		"""A per-match failure keeps the original URL, the rest of the text sends."""
		blob = self.make_blob()
		text = f"see /private/files/{blob.name}/a.txt now"

		with (
			storage_v2_enabled(),
			patch("frappe.storage.url.make_signature", side_effect=Exception("boom")),
		):
			self.assertEqual(rewrite_text_urls_for_email(text), text)
