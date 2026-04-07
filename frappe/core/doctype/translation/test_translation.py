# Copyright (c) 2015, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe import _
from frappe.tests.utils import FrappeTestCase


class TestTranslation(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Translation")

	def tearDown(self):
		frappe.local.lang = "en"
		from frappe.translate import clear_cache

		clear_cache()

	def test_doctype(self):
		doctype = "Translation"
		meta = frappe.get_meta(doctype)
		source_string = meta.get_label("translated_text")

		for lang in ["de", "bs", "zh", "hr", "en", "sv"]:
			frappe.local.lang = lang
			original_translation = _(source_string, context=doctype)
			new_translation = f"{original_translation} Customized"

			docname = create_translation(lang, source_string, new_translation, context=doctype)
			self.assertEqual(_(source_string, context=doctype), new_translation)

			frappe.delete_doc(doctype, docname)
			self.assertEqual(_(source_string, context=doctype), original_translation)

	def test_parent_language(self):
		data = {
			"Test Data": {
				"es": "datos de prueba",
				"es-MX": "pruebas de datos",
			},
			"Test Spanish": {
				"es": "prueba de español",
			},
		}

		for source_string, translations in data.items():
			for lang, translation in translations.items():
				create_translation(lang, source_string, translation)

		frappe.local.lang = "es"

		self.assertEqual(_("Test Data"), data["Test Data"]["es"])

		self.assertEqual(_("Test Spanish"), data["Test Spanish"]["es"])

		frappe.local.lang = "es-MX"

		# different translation for es-MX
		self.assertEqual(_("Test Data"), data["Test Data"]["es-MX"])

		# from spanish (general)
		self.assertEqual(_("Test Spanish"), data["Test Spanish"]["es"])

	def test_multi_language_translations(self):
		source = "User"
		self.assertNotEqual(_(source, lang="de"), _(source, lang="es"))

	def test_html_content_translation(self):
		source = """
			To add dynamic subject, use jinja tags like
			<div><pre><code>{{ doc.name }} Billed</code></pre></div>
		""".strip()
		target = """
			Um einen dynamischen Betreff hinzuzufügen, verwenden Sie Jinja-Tags wie
			<div><pre><code>{{ doc.name }} Abgerechnet</code></pre></div>
		""".strip()

		frappe.local.lang = "de"

		self.assertEqual(_(source), source)

		create_translation("de", source, target)

		self.assertEqual(_(source), target)

	def test_translated_html_is_sanitized(self):
		source = "Translation with HTML"
		target = """
			<span style="color:red" onclick="alert('xss')">Hallo</span>
			<script>alert("xss")</script>
			<iframe src="https://example.com"></iframe>
			<div>Ok</div>
		""".strip()

		docname = create_translation("de", source, target)
		translated_text = frappe.db.get_value("Translation", docname, "translated_text")

		self.assertIn('<span style="color:red;">Hallo</span>', translated_text)
		self.assertIn("<div>Ok</div>", translated_text)
		self.assertNotIn("onclick", translated_text)
		self.assertIn('&lt;script&gt;alert("xss")&lt;/script&gt;', translated_text)
		self.assertIn('&lt;iframe src="https://example.com"&gt;&lt;/iframe&gt;', translated_text)

		frappe.local.lang = "de"
		self.assertEqual(_(source), translated_text)

	def test_plain_text_translation_with_angle_brackets_is_unchanged(self):
		source = "Comparison"
		target = "1 < 2 and 3 > 2"

		docname = create_translation("de", source, target)

		self.assertEqual(frappe.db.get_value("Translation", docname, "translated_text"), target)

	def test_html_message_translations(self):
		"""Test fallback for messages w/ HTML Tags"""
		message = "Hide descendant records of <b>For Value</b>."
		translated_message = "隐藏下层节点<b>值</b>"
		create_translation("zh", message, translated_message)
		self.assertEqual(_(message, lang="zh"), translated_message)


def create_translation(lang, source_string, new_translation, context=None) -> str:
	doc = frappe.new_doc("Translation")
	doc.language = lang
	doc.source_text = source_string
	doc.translated_text = new_translation
	doc.context = context
	doc.save()

	return doc.name
