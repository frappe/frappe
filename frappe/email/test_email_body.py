# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import frappe, unittest, os, base64
from frappe.email.email_body import replace_filename_with_cid, get_email

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


def fixed_column_width(string, chunk_size):
	parts = [string[0+i:chunk_size+i] for i in range(0, len(string), chunk_size)]
	return '\n'.join(parts)