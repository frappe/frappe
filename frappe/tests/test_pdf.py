# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest

import frappe.utils.pdf as pdfgen
import frappe, io, six
from PyPDF2 import PdfFileReader

#class TestPdfBorders(unittest.TestCase):
class TestPdf(unittest.TestCase):
	@property
	def html(self):
		return """<style>
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
			</div>"""

	def runTest(self):
		self.test_read_options_from_html()

	def test_read_options_from_html(self):
		_, html_options = pdfgen.read_options_from_html(self.html)
		self.assertTrue(html_options['margin-top'] == '0')
		self.assertTrue(html_options['margin-left'] == '10')
		self.assertTrue(html_options['margin-right'] == '0')

	def test_pdf_encryption(self):
		password = "qwe"
		pdf = pdfgen.get_pdf(self.html, options={"password": password})
		reader = PdfFileReader(io.BytesIO(pdf))
		self.assertTrue(reader.isEncrypted)
		if six.PY2:
			password = frappe.safe_encode(password)
		self.assertTrue(reader.decrypt(password))