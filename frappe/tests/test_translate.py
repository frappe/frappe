# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import os
import textwrap
from random import choices
from unittest.mock import patch

import frappe
import frappe.translate
from frappe import _, _lt
from frappe.gettext.extractors.javascript import extract_javascript
from frappe.tests import IntegrationTestCase
from frappe.translate import (
	MERGED_TRANSLATION_KEY,
	USER_TRANSLATION_KEY,
	clear_cache,
	extract_messages_from_javascript_code,
	extract_messages_from_python_code,
	get_language,
	get_messages_for_app,
	get_parent_language,
	get_translation_dict_from_file,
)
from frappe.utils import get_bench_path, set_request

dirname = os.path.dirname(__file__)
translation_string_file = os.path.abspath(os.path.join(dirname, "translation_test_file.txt"))
first_lang, second_lang, third_lang, fourth_lang, fifth_lang = choices(
	# skip "en*" since it is a default language
	frappe.get_all("Language", pluck="name", filters=[["name", "not like", "en%"], ["enabled", "=", 1]]),
	k=5,
)


_lazy_translations = _lt("Communication")


class TestTranslate(IntegrationTestCase):
	guest_sessions_required = (
		"test_guest_request_language_resolution_with_cookie",
		"test_guest_request_language_resolution_with_request_header",
	)

	def setUp(self):
		if self._testMethodName in self.guest_sessions_required:
			frappe.set_user("Guest")

	def tearDown(self):
		frappe.form_dict.pop("_lang", None)
		if self._testMethodName in self.guest_sessions_required:
			frappe.set_user("Administrator")
		frappe.local.lang = "en"

	def test_clear_cache(self):
		_("Trigger caching")

		self.assertIsNotNone(frappe.cache.hget(USER_TRANSLATION_KEY, frappe.local.lang))
		self.assertIsNotNone(frappe.cache.hget(MERGED_TRANSLATION_KEY, frappe.local.lang))

		clear_cache()

		self.assertIsNone(frappe.cache.hget(USER_TRANSLATION_KEY, frappe.local.lang))
		self.assertIsNone(frappe.cache.hget(MERGED_TRANSLATION_KEY, frappe.local.lang))

	def test_extract_message_from_file(self):
		data = frappe.translate.get_messages_from_file(translation_string_file)
		bench_path = get_bench_path()
		file_path = frappe.get_app_path("frappe", "tests", "translation_test_file.txt")
		exp_filename = os.path.relpath(file_path, bench_path)

		self.assertEqual(
			len(data),
			len(expected_output),
			msg=f"Mismatched output:\nExpected: {expected_output}\nFound: {data}",
		)

		for extracted, expected in zip(data, expected_output, strict=False):
			ext_filename, ext_message, ext_context, ext_line = extracted
			exp_message, exp_context, exp_line = expected
			self.assertEqual(ext_filename, exp_filename)
			self.assertEqual(ext_message, exp_message)
			self.assertEqual(ext_context, exp_context)
			self.assertEqual(ext_line, exp_line)

	def test_read_language_variant(self):
		self.assertEqual(_("Mobile No"), "Mobile No")
		try:
			frappe.local.lang = "pt-BR"
			self.assertEqual(_("Mobile No"), "Telefone Celular")
			frappe.local.lang = "pt"
			self.assertEqual(_("Mobile No"), "Nr. de Telemóvel")
		finally:
			frappe.local.lang = "en"
			self.assertEqual(_("Mobile No"), "Mobile No")

	def test_translation_with_context(self):
		t1 = frappe.new_doc("Translation")
		t1.language = "fr"
		t1.source_text = "Change"
		t1.translated_text = "Changement"
		t1.save()

		t2 = frappe.new_doc("Translation")
		t2.language = "fr"
		t2.source_text = "Change"
		t2.translated_text = "la monnaie"
		t2.context = "Coins"
		t2.save()

		frappe.local.lang = "fr"
		self.assertEqual(_("Change"), "Changement")
		self.assertEqual(_("Change", context="Coins"), "la monnaie")

		t1.delete()
		t2.delete()

	def test_lazy_translations(self):
		frappe.local.lang = "de"
		eager_translation = _("Communication")
		self.assertEqual(str(_lazy_translations), eager_translation)
		self.assertRaises(NotImplementedError, lambda: _lazy_translations == "blah")

		# auto casts when added or radded
		self.assertEqual(_lazy_translations + "A", eager_translation + "A")
		x = _lazy_translations
		x += "A"
		self.assertEqual(x, eager_translation + "A")

		# f string usually auto-casts
		self.assertEqual(f"{_lazy_translations}", eager_translation)

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

		with patch.object(frappe.translate, "get_preferred_language_cookie", return_value="fr"):
			set_request(method="POST", path="/", headers=[("Accept-Language", "hr")])
			return_val = get_language()
			# system default language
			self.assertEqual(return_val, "en")
			self.assertNotIn(return_val, [second_lang, get_parent_language(second_lang)])

	def test_guest_request_language_resolution_with_cookie(self):
		"""Test for frappe.translate.get_language

		Case 3: frappe.form_dict._lang is not set, but preferred_language cookie is [Guest User]
		"""

		with patch.object(frappe.translate, "get_preferred_language_cookie", return_value=second_lang):
			set_request(method="POST", path="/", headers=[("Accept-Language", third_lang)])
			return_val = get_language()

		self.assertIn(return_val, [second_lang, get_parent_language(second_lang)])

	def test_global_translations(self):
		""" """
		site = frappe.local.site
		frappe.destroy()
		_("this shouldn't break")
		frappe.init(site)
		frappe.connect()

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

	def test_load_all_translate_files(self):
		"""Load all CSV files to ensure they have correct format"""
		verify_translation_files("frappe")

	def test_python_extractor(self):
		code = textwrap.dedent(
			"""
			frappe._("attr")
			_("name")
			frappe._("attr with", context="attr context")
			_("name with", context="name context")
			_("broken on",
				context="new line")
			__("This wont be captured")
			__init__("This shouldn't too")
			_(
				"broken on separate line",
				)
			_(not_a_string)
			_(not_a_string, context="wat")
			_lt("Communication")
		"""
		)
		expected_output = [
			(2, "attr", None),
			(3, "name", None),
			(4, "attr with", "attr context"),
			(5, "name with", "name context"),
			(6, "broken on", "new line"),
			(10, "broken on separate line", None),
			(15, "Communication", None),
		]

		output = extract_messages_from_python_code(code)
		self.assertEqual(len(expected_output), len(output))
		for expected, actual in zip(expected_output, output, strict=False):
			with self.subTest():
				self.assertEqual(expected, actual)

	def test_js_extractor(self):
		code = textwrap.dedent(
			"""
			__("attr")
			__("attr with", null, "context")
			__("attr with", ["format", "replacements"], "context")
			__("attr with", ["format", "replacements"])
			__(
				"Long JS string with", [
					"format", "replacements"
				],
				"JS context on newline"
			)
			__(
				"Long JS string with formats only {0}", [
					"format", "replacements"
				],
			)
			_(`template strings not supported yet`)
		"""
		)
		expected_output = [
			(2, "attr", None),
			(3, "attr with", "context"),
			(4, "attr with", "context"),
			(5, "attr with", None),
			(6, "Long JS string with", "JS context on newline"),
			(12, "Long JS string with formats only {0}", None),
		]

		output = extract_messages_from_javascript_code(code)

		self.assertEqual(len(expected_output), len(output))
		for expected, actual in zip(expected_output, output, strict=False):
			with self.subTest():
				self.assertEqual(expected, actual)

	def test_js_parser_arg_capturing(self):
		"""Get non-flattened args in correct order so 3rd arg if present is always context."""

		def get_args(code):
			*__, args = next(extract_javascript(code))
			return args

		args = get_args("""__("attr with", ["format", "replacements"], "context")""")
		self.assertEqual(args, ("attr with", None, "context"))

		args = get_args("""__("attr with", ["format", "replacements"])""")
		self.assertEqual(args, "attr with")

		args = get_args("""__("attr with", null, "context")""")
		self.assertEqual(args, ("attr with", None, "context"))

		args = get_args(
			"""__(
				"Multiline translation with format replacements and context {0} {1}",
				[
					"format",
					call("replacements", {
						"key": "value"
					}),
				],
				"context"
			)"""
		)
		self.assertEqual(
			args, ("Multiline translation with format replacements and context {0} {1}", None, "context")
		)

		args = get_args(
			"""__(
				"Multiline translation with format replacements and no context {0} {1}",
				[
					"format",
					call("replacements", {
						"key": "value"
					}),
				],
			)"""
		)
		self.assertEqual(
			args, ("Multiline translation with format replacements and no context {0} {1}", None)
		)


def verify_translation_files(app):
	"""Function to verify translation file syntax in app."""
	# Do not remove/rename this, other apps depend on it to test their translations

	from pathlib import Path

	translations_dir = Path(frappe.get_app_path(app)) / "translations"

	for file in translations_dir.glob("*.csv"):
		lang = file.stem  # basename of file = lang
		get_translation_dict_from_file(file, lang, app, throw=True)

	get_messages_for_app(app)


expected_output = [
	("Warning: Unable to find {0} in any table related to {1}", "This is some context", 2),
	("Warning: Unable to find {0} in any table related to {1}", None, 4),
	("You don't have any messages yet.", None, 6),
	("Submit", "Some DocType", 8),
	("Warning: Unable to find {0} in any table related to {1}", "This is some context", 15),
	("Submit", "Some DocType", 17),
	("You don't have any messages yet.", None, 19),
	("You don't have any messages yet.", None, 21),
	("Long string that needs its own line because of black formatting.", None, 24),
	("Long string with", "context", 28),
	("Long string with", "context on newline", 32),
]
