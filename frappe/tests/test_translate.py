# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest, os
import frappe.translate
from frappe import _

dirname = os.path.dirname(__file__)
translation_string_file = os.path.join(dirname, 'translation_test_file.txt')

class TestTranslate(unittest.TestCase):
	def test_extract_message_from_file(self):
		data = frappe.translate.get_messages_from_file(translation_string_file)
		self.assertListEqual(data, expected_output)

	def test_translation_with_context(self):
		frappe.local.lang = 'fr'
		self.assertEqual(_('Change'), 'Changement')
		self.assertEqual(_('Change', context='Coins'), 'la monnaie')
		frappe.local.lang = 'en'

expected_output = [
	('apps/frappe/frappe/tests/translation_test_file.txt', 'Warning: Unable to find {0} in any table related to {1}', 'This is some context', 2),
	('apps/frappe/frappe/tests/translation_test_file.txt', 'Warning: Unable to find {0} in any table related to {1}', None, 4),
	('apps/frappe/frappe/tests/translation_test_file.txt', "You don't have any messages yet.", None, 6),
	('apps/frappe/frappe/tests/translation_test_file.txt', 'Submit', 'Some DocType', 8),
	('apps/frappe/frappe/tests/translation_test_file.txt', 'Warning: Unable to find {0} in any table related to {1}', 'This is some context', 15),
	('apps/frappe/frappe/tests/translation_test_file.txt', 'Submit', 'Some DocType', 17),
	('apps/frappe/frappe/tests/translation_test_file.txt', "You don't have any messages yet.", None, 19),
	('apps/frappe/frappe/tests/translation_test_file.txt', "You don't have any messages yet.", None, 21)
]

