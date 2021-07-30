# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import os
import unittest
from random import choices
from unittest.mock import patch

import frappe
import frappe.translate
from frappe import _
from frappe.translate import get_language, get_parent_language
from frappe.utils import set_request

dirname = os.path.dirname(__file__)
translation_string_file = os.path.join(dirname, 'translation_test_file.txt')
first_lang, second_lang, third_lang, fourth_lang, fifth_lang = choices(
	frappe.get_all("Language", pluck="name"), k=5
)

class TestTranslate(unittest.TestCase):
	guest_sessions_required = [
		"test_guest_request_language_resolution_with_cookie",
		"test_guest_request_language_resolution_with_request_header"
	]

	def setUp(self):
		if self._testMethodName in self.guest_sessions_required:
			frappe.set_user("Guest")

	def tearDown(self):
		frappe.form_dict.pop("_lang", None)
		if self._testMethodName in self.guest_sessions_required:
			frappe.set_user("Administrator")

	def test_extract_message_from_file(self):
		data = frappe.translate.get_messages_from_file(translation_string_file)
		self.assertListEqual(data, expected_output)

	def test_translation_with_context(self):
		try:
			frappe.local.lang = 'fr'
			self.assertEqual(_('Change'), 'Changement')
			self.assertEqual(_('Change', context='Coins'), 'la monnaie')
		finally:
			frappe.local.lang = 'en'

	def test_request_language_resolution_with_form_dict(self):
		"""Test for frappe.translate.get_language

		Case 1: frappe.form_dict._lang is set
		"""

		frappe.form_dict._lang = first_lang

		with patch.object(frappe.translate, "get_preferred_language_cookie", return_value=second_lang):
			return_val = get_language()

		self.assertIn(return_val, [first_lang, get_parent_language(first_lang)])

	def test_request_language_resolution_with_cookie(self):
		"""Test for frappe.translate.get_language

		Case 2: frappe.form_dict._lang is not set, but preferred_language cookie is
		"""

		with patch.object(frappe.translate, "get_preferred_language_cookie", return_value=second_lang):
			set_request(method="POST", path="/", headers=[("Accept-Language", third_lang)])
			return_val = get_language()

		self.assertNotIn(return_val, [second_lang, get_parent_language(second_lang)])

	def test_guest_request_language_resolution_with_cookie(self):
		"""Test for frappe.translate.get_language

		Case 3: frappe.form_dict._lang is not set, but preferred_language cookie is [Guest User]
		"""

		with patch.object(frappe.translate, "get_preferred_language_cookie", return_value=second_lang):
			set_request(method="POST", path="/", headers=[("Accept-Language", third_lang)])
			return_val = get_language()

		self.assertIn(return_val, [second_lang, get_parent_language(second_lang)])


	def test_guest_request_language_resolution_with_request_header(self):
		"""Test for frappe.translate.get_language

		Case 4: frappe.form_dict._lang & preferred_language cookie is not set, but Accept-Language header is [Guest User]
		"""

		set_request(method="POST", path="/", headers=[("Accept-Language", third_lang)])
		return_val = get_language()
		self.assertIn(return_val, [third_lang, get_parent_language(third_lang)])

	def test_request_language_resolution_with_request_header(self):
		"""Test for frappe.translate.get_language

		Case 5: frappe.form_dict._lang & preferred_language cookie is not set, but Accept-Language header is
		"""

		set_request(method="POST", path="/", headers=[("Accept-Language", third_lang)])
		return_val = get_language()
		self.assertNotIn(return_val, [third_lang, get_parent_language(third_lang)])


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

