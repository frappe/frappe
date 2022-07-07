# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import base64
import os
import unittest

from six import PY3

from frappe import safe_decode
from frappe.email.email_body import (
	get_email,
	get_header,
	inline_style_in_html,
	replace_filename_with_cid,
)
from frappe.email.queue import get_email_queue, prepare_message
from frappe.email.receive import Email


class TestEmailBody(unittest.TestCase):
	def setUp(self):
		email_html = """
<div>
	<h3>Hey John Doe!</h3>
	<p>This is embedded image you asked for</p>
	<img embed="assets/frappe/images/frappe-favicon.svg" />
</div>
"""
		email_text = """
Hey John Doe!
This is the text version of this email
"""

		img_path = os.path.abspath("assets/frappe/images/frappe-favicon.svg")
		with open(img_path, "rb") as f:
			img_content = f.read()
			img_base64 = base64.b64encode(img_content).decode()

		# email body keeps 76 characters on one line
		self.img_base64 = fixed_column_width(img_base64, 76)

		self.email_string = (
			get_email(
				recipients=["test@example.com"],
				sender="me@example.com",
				subject="Test Subject",
				content=email_html,
				text_content=email_text,
			)
			.as_string()
			.replace("\r\n", "\n")
		)

	def test_prepare_message_returns_already_encoded_string(self):

		if PY3:
			uni_chr1 = chr(40960)
			uni_chr2 = chr(1972)
		else:
			uni_chr1 = unichr(40960)
			uni_chr2 = unichr(1972)

		email = get_email_queue(
			recipients=["test@example.com"],
			sender="me@example.com",
			subject="Test Subject",
			content="<h1>" + uni_chr1 + "abcd" + uni_chr2 + "</h1>",
			formatted="<h1>" + uni_chr1 + "abcd" + uni_chr2 + "</h1>",
			text_content="whatever",
		)
		result = prepare_message(email=email, recipient="test@test.com", recipients_list=[])
		self.assertTrue(b"<h1>=EA=80=80abcd=DE=B4</h1>" in result)

	def test_prepare_message_returns_cr_lf(self):
		email = get_email_queue(
			recipients=["test@example.com"],
			sender="me@example.com",
			subject="Test Subject",
			content="<h1>\n this is a test of newlines\n" + "</h1>",
			formatted="<h1>\n this is a test of newlines\n" + "</h1>",
			text_content="whatever",
		)
		result = safe_decode(prepare_message(email=email, recipient="test@test.com", recipients_list=[]))
		if PY3:
			self.assertTrue(result.count("\n") == result.count("\r"))
		else:
			self.assertTrue(True)

	def test_image(self):
		img_signature = """
Content-Type: image/svg+xml
MIME-Version: 1.0
Content-Transfer-Encoding: base64
Content-Disposition: inline; filename="frappe-favicon.svg"
"""
		self.assertTrue(img_signature in self.email_string)
		self.assertTrue(self.img_base64 in self.email_string)

	def test_text_content(self):
		text_content = """
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable


Hey John Doe!
This is the text version of this email
"""
		self.assertTrue(text_content in self.email_string)

	def test_email_content(self):
		html_head = """
Content-Type: text/html; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.=
w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns=3D"http://www.w3.org/1999/xhtml">
"""

		html = """<h3>Hey John Doe!</h3>"""

		self.assertTrue(html_head in self.email_string)
		self.assertTrue(html in self.email_string)

	def test_replace_filename_with_cid(self):
		original_message = """
			<div>
				<img embed="assets/frappe/images/frappe-favicon.svg" alt="test" />
				<img embed="notexists.jpg" />
			</div>
		"""
		message, inline_images = replace_filename_with_cid(original_message)

		processed_message = """
			<div>
				<img src="cid:{0}" alt="test" />
				<img  />
			</div>
		""".format(
			inline_images[0].get("content_id")
		)
		self.assertEqual(message, processed_message)

	def test_inline_styling(self):
		html = """
<h3>Hi John</h3>
<p>This is a test email</p>
"""
		transformed_html = """
<h3>Hi John</h3>
<p style="margin:1em 0 !important">This is a test email</p>
"""
		self.assertTrue(transformed_html in inline_style_in_html(html))

	def test_email_header(self):
		email_html = """
<h3>Hey John Doe!</h3>
<p>This is embedded image you asked for</p>
"""
		email_string = get_email(
			recipients=["test@example.com"],
			sender="me@example.com",
			subject="Test Subject\u2028, with line break, \nand Line feed \rand carriage return.",
			content=email_html,
			header=["Email Title", "green"],
		).as_string()
		# REDESIGN-TODO: Add style for indicators in email
		self.assertTrue("""<span class=3D"indicator indicator-green"></span>""" in email_string)
		self.assertTrue("<span>Email Title</span>" in email_string)
		self.assertIn(
			"Subject: Test Subject, with line break, and Line feed and carriage return.", email_string
		)

	def test_get_email_header(self):
		html = get_header(["This is test", "orange"])
		self.assertTrue('<span class="indicator indicator-orange"></span>' in html)
		self.assertTrue("<span>This is test</span>" in html)

		html = get_header(["This is another test"])
		self.assertTrue("<span>This is another test</span>" in html)

		html = get_header("This is string")
		self.assertTrue("<span>This is string</span>" in html)

	def test_8bit_utf_8_decoding(self):
		text_content_bytes = b"\xed\x95\x9c\xea\xb8\x80\xe1\xa5\xa1\xe2\x95\xa5\xe0\xba\xaa\xe0\xa4\x8f"
		text_content = text_content_bytes.decode("utf-8")

		content_bytes = (
			b"""MIME-Version: 1.0
Content-Type: text/plain; charset=utf-8
Content-Disposition: inline
Content-Transfer-Encoding: 8bit
From: test1_@erpnext.com
Reply-To: test2_@erpnext.com
"""
			+ text_content_bytes
		)

		mail = Email(content_bytes)
		self.assertEqual(mail.text_content, text_content)


def fixed_column_width(string, chunk_size):
	parts = [string[0 + i : chunk_size + i] for i in range(0, len(string), chunk_size)]
	return "\n".join(parts)
