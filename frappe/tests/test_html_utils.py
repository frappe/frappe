# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE


import itertools
import unittest

from frappe.utils.html_utils import has_html_tags, sanitize_html

# Fragments chosen for the boundaries between "looks like a tag" and "is a tag".
FRAGMENTS = (
	"<b>",
	"</b>",
	"<br/>",
	"<!-- c -->",
	"text",
	"<3",
	"a<b",
	"x>y",
	"&lt;",
	"<!doctype html>",
	'<p class="a">',
	"<",
	">",
	"</ p>",
	"<_x>",
	"<1a>",
)


class TestHasHtmlTags(unittest.TestCase):
	def test_matches_beautifulsoup(self):
		"""Every combination must agree with the bs4 expression this replaced."""
		from bs4 import BeautifulSoup

		for length in (1, 2, 3):
			for combination in itertools.product(FRAGMENTS, repeat=length):
				html = "".join(combination)
				with self.subTest(html=html):
					expected = bool(BeautifulSoup(html, "html.parser").find())
					self.assertEqual(has_html_tags(html), expected)

	def test_tags_are_detected(self):
		for html in ("<br>", "<BR/>", "<div>x</div>", '<p class="a">x', "text<b>bold</b>"):
			with self.subTest(html=html):
				self.assertTrue(has_html_tags(html))

	def test_text_that_only_looks_like_html(self):
		for html in ("", "plain text", "a < b and c > d", "<3 love", "<div", "&lt;b&gt;", "x</p>"):
			with self.subTest(html=html):
				self.assertFalse(has_html_tags(html))

	def test_markdown_comment_marker_is_not_a_tag(self):
		"""`_sanitize_content` skips markdown values, and relies on this distinction."""
		self.assertFalse(has_html_tags("<!-- markdown -->\n# Heading\n\nBody text."))
		self.assertTrue(has_html_tags("<!-- markdown -->\n<b>bold</b>"))

	def test_sanitize_html_passes_through_plain_text(self):
		"""The early-out `has_html_tags` guards must not alter tag-free content."""
		for html in ("plain text", "a < b and c > d", "<!-- markdown -->\n# Heading"):
			with self.subTest(html=html):
				self.assertEqual(sanitize_html(html), html)

	def test_sanitize_html_still_strips_scripts(self):
		self.assertNotIn("<script>", sanitize_html("<div><script>alert(1)</script>ok</div>"))
