# Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
from __future__ import unicode_literals

import unittest
from frappe.email.email_body import replace_filename_with_cid

class TestEmailBody(unittest.TestCase):
	def test_replace_filename_with_cid(self):
		original_message = '''
			<div>
				<img embed="test.jpg" alt="test" />
			</div>
		'''
		processed_message = '''
			<div>
				<img src="cid:abcdefghij" alt="test" />
			</div>
		'''
		message = replace_filename_with_cid(original_message, 'test.jpg', 'abcdefghij')

		self.assertEquals(message, processed_message)
