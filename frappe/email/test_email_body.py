# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import frappe, unittest, os, base64
from frappe.email.email_body import (replace_filename_with_cid,
	get_email, inline_style_in_html, get_header)

class TestEmailBody(unittest.TestCase):
	def setUp(self):
		email_html = '''
<div>
	<h3>Hey John Doe!</h3>
	<p>This is embedded image you asked for</p>
	<img embed="assets/frappe/images/favicon.png" />
</div>
'''
		email_text = '''
Hey John Doe!
This is the text version of this email
'''

		img_path = os.path.abspath('assets/frappe/images/favicon.png')
		with open(img_path) as f:
			img_content = f.read()
			img_base64 = base64.b64encode(img_content)

		# email body keeps 76 characters on one line
		self.img_base64 = fixed_column_width(img_base64, 76)

		self.email_string = get_email(
			recipients=['test@example.com'],
			sender='me@example.com',
			subject='Test Subject',
			content=email_html,
			text_content=email_text
		).as_string()


	def test_image(self):
		img_signature = '''
Content-Type: image/png
MIME-Version: 1.0
Content-Transfer-Encoding: base64
Content-Disposition: inline; filename="favicon.png"
'''

		self.assertTrue(img_signature in self.email_string)
		self.assertTrue(self.img_base64 in self.email_string)


	def test_text_content(self):
		text_content = '''
Content-Type: text/plain; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable


Hey John Doe!
This is the text version of this email
'''
		self.assertTrue(text_content in self.email_string)


	def test_email_content(self):
		html_head = '''
Content-Type: text/html; charset="utf-8"
MIME-Version: 1.0
Content-Transfer-Encoding: quoted-printable

<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.=
w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns=3D"http://www.w3.org/1999/xhtml">
'''

		html = '''<h3>Hey John Doe!</h3>'''

		self.assertTrue(html_head in self.email_string)
		self.assertTrue(html in self.email_string)


	def test_replace_filename_with_cid(self):
		original_message = '''
			<div>
				<img embed="assets/frappe/images/favicon.png" alt="test" />
				<img embed="notexists.jpg" />
			</div>
		'''
		message, inline_images = replace_filename_with_cid(original_message)

		processed_message = '''
			<div>
				<img src="cid:{0}" alt="test" />
				<img  />
			</div>
		'''.format(inline_images[0].get('content_id'))
		self.assertEquals(message, processed_message)

	def test_inline_styling(self):
		html = '''
<h3>Hi John</h3>
<p>This is a test email</p>
'''
		transformed_html = '''
<h3>Hi John</h3>
<p style="margin:1em 0 !important">This is a test email</p>
'''
		self.assertTrue(transformed_html in inline_style_in_html(html))

	def test_email_header(self):
		email_html = '''
<h3>Hey John Doe!</h3>
<p>This is embedded image you asked for</p>
'''
		email_string = get_email(
			recipients=['test@example.com'],
			sender='me@example.com',
			subject='Test Subject',
			content=email_html,
			header=['Email Title', 'green']
		).as_string()

		self.assertTrue('''<span class=3D"indicator indicator-green" style=3D"background-color:#98=
d85b; border-radius:8px; display:inline-block; height:8px; margin-right:5px=
; width:8px" bgcolor=3D"#98d85b" height=3D"8" width=3D"8"></span>''' in email_string)
		self.assertTrue('<span>Email Title</span>' in email_string)

	def test_get_email_header(self):
		html = get_header(['This is test', 'orange'])
		self.assertTrue('<span class="indicator indicator-orange"></span>' in html)
		self.assertTrue('<span>This is test</span>' in html)

		html = get_header(['This is another test'])
		self.assertTrue('<span>This is another test</span>' in html)

		html = get_header('This is string')
		self.assertTrue('<span>This is string</span>' in html)


def fixed_column_width(string, chunk_size):
	parts = [string[0+i:chunk_size+i] for i in range(0, len(string), chunk_size)]
	return '\n'.join(parts)