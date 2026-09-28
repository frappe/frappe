from frappe.gettext.extractors.javascript import extract_javascript
from frappe.tests.utils import FrappeTestCase


class TestJavaScript(FrappeTestCase):
	def test_extract_javascript(self):
		code = "let test = `<p>${__('Test')}</p>`;"
		self.assertEqual(
			next(extract_javascript(code)),
			(1, "__", "Test"),
		)

		code = "let test = `<p>${__('Test', null, 'Context')}</p>`;"
		self.assertEqual(
			next(extract_javascript(code)),
			(1, "__", ("Test", None, "Context")),
		)

	def test_extract_javascript_from_template_literal_attribute(self):
		code = "let test = `<button title=\"${__('In attribute')}\">${__('In text')}</button>`;"
		self.assertEqual(
			list(extract_javascript(code)),
			[(1, "__", "In attribute"), (1, "__", "In text")],
		)

	def test_extract_javascript_template_literal_multiline_line_numbers(self):
		code = "let test = `\n<button title=\"${__('In attribute')}\">\n  ${__('In text')}\n</button>\n`;"
		self.assertEqual(
			list(extract_javascript(code)),
			[(2, "__", "In attribute"), (3, "__", "In text")],
		)

	def test_extract_javascript_nested_calls(self):
		code = "__('Open {0}', [__('Email Inbox')]);"
		self.assertEqual(
			list(extract_javascript(code)),
			[(1, "__", "Email Inbox"), (1, "__", "Open {0}")],
		)

		code = "__('{0} of {1}', [__('Sales Invoice'), __('Customer')], 'Breadcrumb');"
		self.assertEqual(
			list(extract_javascript(code)),
			[
				(1, "__", "Sales Invoice"),
				(1, "__", "Customer"),
				(1, "__", ("{0} of {1}", None, "Breadcrumb")),
			],
		)

		code = "__('{0}: Other permission rules may also apply', [frappe.bold(__('Note'))]);"
		self.assertEqual(
			list(extract_javascript(code)),
			[(1, "__", "Note"), (1, "__", "{0}: Other permission rules may also apply")],
		)
