from frappe.gettext.extractors.javascript import extract_javascript
from frappe.tests import IntegrationTestCase


class TestJavaScript(IntegrationTestCase):
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

	def test_html_attribute_inside_template_literal(self):
		"""Test extraction from HTML attributes within template literals (Issue #36496)"""
		# Single line with HTML attribute
		code = '`<input placeholder="${__("Search or type a command")}" />`'
		result = next(extract_javascript(code))
		self.assertEqual(result[2], "Search or type a command")

		# Multiple attributes
		code = '`<input type="text" placeholder="${__("Enter name")}" value="${__("Default")}" />`'
		results = list(extract_javascript(code))
		self.assertEqual(len(results), 2)
		self.assertEqual(results[0][2], "Enter name")
		self.assertEqual(results[1][2], "Default")

	def test_multiline_template_literal_lineno(self):
		"""Test correct line numbers for multi-line template literals"""
		code = """let html = `<div class="test">
    <input placeholder="${__("Enter text")}" />
    <button>${__("Submit")}</button>
</div>`;"""
		results = list(extract_javascript(code))
		self.assertEqual(len(results), 2)
		# First message on line 2, second on line 3
		self.assertEqual(results[0][0], 2)
		self.assertEqual(results[1][0], 3)

	def test_multiline_expression_lineno(self):
		"""Test correct line numbers for multi-line ${...} expressions (barredterra's case)"""
		code = """let x = `
<input
placeholder="${
	__("Search or type a command")
}"
/>`;"""
		results = list(extract_javascript(code))
		self.assertEqual(len(results), 1)
		# Message should be reported on line 4 where __() appears
		self.assertEqual(results[0][0], 4)

	def test_lineno_offset(self):
		"""Test that lineno parameter correctly offsets line numbers"""
		code = """
let x = "not important";
let html = `<div>
    ${__("Message")}
</div>`;
"""
		results = list(extract_javascript(code, lineno=100))
		# Message is on line 4 of the code, + 100 offset - 1 = line 103
		self.assertEqual(results[0][0], 103)

	def test_backslash_escape_handling(self):
		"""Test correct handling of backslash escapes in strings"""
		# Double backslash (literal backslash)
		code = r'`${__("Test with \\ backslash")}`'
		result = next(extract_javascript(code))
		self.assertIn("backslash", result[2])

		# Escaped quote
		code = r'`${__("Test with \" quote")}`'
		result = next(extract_javascript(code))
		self.assertIn("quote", result[2])
