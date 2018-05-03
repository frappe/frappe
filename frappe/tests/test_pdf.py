# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest

from frappe.utils.pdf import read_options_from_html

#class TestPdfBorders(unittest.TestCase):
class TestPdfBorders(unittest.TestCase):
    def test_pdf_borders(self):
        html = """
			<style>
            .print-format {
             margin-top: 0mm;
             margin-left: 10mm;
             margin-right: 0mm;
            }
            </style>
            <p>This is a test html snippet</p>
			<div class="more-info">
				<a href="http://test.com">Test link 1</a>
				<a href="/about">Test link 2</a>
				<a href="login">Test link 3</a>
				<img src="/assets/frappe/test.jpg">
			</div>
			<div style="background-image: url('/assets/frappe/bg.jpg')">
				Please mail us at <a href="mailto:test@example.com">email</a>
			</div>
		"""

        html, html_options = read_options_from_html(html)
        self.assertTrue(html_options['margin-top'] == '0')
        self.assertTrue(html_options['margin-left'] == '10')
        self.assertTrue(html_options['margin-right'] == '0')

# allows to run $ bench execute frappe.tests.test_pdf.run_tests
def run_tests():
    t = TestPdfBorders("test_pdf_borders")
    t.test_pdf_borders()
    return
