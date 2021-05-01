# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest
import frappe

from frappe.utils import evaluate_filters, money_in_words, scrub_urls, get_url
from frappe.utils import validate_url, validate_email_address
from frappe.utils import ceil, floor

from PIL import Image
from frappe.utils.image import strip_exif_data
import io

class TestFilters(unittest.TestCase):
	def test_simple_dict(self):
		self.assertTrue(evaluate_filters({'doctype': 'User', 'status': 'Open'}, {'status': 'Open'}))
		self.assertFalse(evaluate_filters({'doctype': 'User', 'status': 'Open'}, {'status': 'Closed'}))

	def test_multiple_dict(self):
		self.assertTrue(evaluate_filters({'doctype': 'User', 'status': 'Open', 'name': 'Test 1'},
			{'status': 'Open', 'name':'Test 1'}))
		self.assertFalse(evaluate_filters({'doctype': 'User', 'status': 'Open', 'name': 'Test 1'},
			{'status': 'Closed', 'name': 'Test 1'}))

	def test_list_filters(self):
		self.assertTrue(evaluate_filters({'doctype': 'User', 'status': 'Open', 'name': 'Test 1'},
			[{'status': 'Open'}, {'name':'Test 1'}]))
		self.assertFalse(evaluate_filters({'doctype': 'User', 'status': 'Open', 'name': 'Test 1'},
			[{'status': 'Open'}, {'name':'Test 2'}]))

	def test_list_filters_as_list(self):
		self.assertTrue(evaluate_filters({'doctype': 'User', 'status': 'Open', 'name': 'Test 1'},
			[['status', '=', 'Open'], ['name', '=', 'Test 1']]))
		self.assertFalse(evaluate_filters({'doctype': 'User', 'status': 'Open', 'name': 'Test 1'},
			[['status', '=', 'Open'], ['name', '=', 'Test 2']]))

	def test_lt_gt(self):
		self.assertTrue(evaluate_filters({'doctype': 'User', 'status': 'Open', 'age': 20},
			{'status': 'Open', 'age': ('>', 10)}))
		self.assertFalse(evaluate_filters({'doctype': 'User', 'status': 'Open', 'age': 20},
			{'status': 'Open', 'age': ('>', 30)}))

class TestMoney(unittest.TestCase):
	def test_money_in_words(self):
		nums_bhd = [
			(5000, "BHD Five Thousand only."), (5000.0, "BHD Five Thousand only."),
			(0.1, "One Hundred Fils only."), (0, "BHD Zero only."), ("Fail", "")
		]

		nums_ngn = [
			(5000, "NGN Five Thousand only."), (5000.0, "NGN Five Thousand only."),
			(0.1, "Ten Kobo only."), (0, "NGN Zero only."), ("Fail", "")
		]

		for num in nums_bhd:
			self.assertEqual(
				money_in_words(num[0], "BHD"), 
				num[1], 
				"{0} is not the same as {1}".format(money_in_words(num[0], "BHD"), num[1])
			)

		for num in nums_ngn:
			self.assertEqual(
				money_in_words(num[0], "NGN"), num[1], 
				"{0} is not the same as {1}".format(money_in_words(num[0], "NGN"), num[1])
			)

class TestDataManipulation(unittest.TestCase):
	def test_scrub_urls(self):
		html = '''
			<p>You have a new message from: <b>John</b></p>
			<p>Hey, wassup!</p>
			<div class="more-info">
				<a href="http://test.com">Test link 1</a>
				<a href="/about">Test link 2</a>
				<a href="login">Test link 3</a>
				<img src="/assets/frappe/test.jpg">
			</div>
			<div style="background-image: url('/assets/frappe/bg.jpg')">
				Please mail us at <a href="mailto:test@example.com">email</a>
			</div>
		'''

		html = scrub_urls(html)
		url = get_url()

		self.assertTrue('<a href="http://test.com">Test link 1</a>' in html)
		self.assertTrue('<a href="{0}/about">Test link 2</a>'.format(url) in html)
		self.assertTrue('<a href="{0}/login">Test link 3</a>'.format(url) in html)
		self.assertTrue('<img src="{0}/assets/frappe/test.jpg">'.format(url) in html)
		self.assertTrue('style="background-image: url(\'{0}/assets/frappe/bg.jpg\') !important"'.format(url) in html)
		self.assertTrue('<a href="mailto:test@example.com">email</a>' in html)

class TestMathUtils(unittest.TestCase):
	def test_floor(self):
		from decimal import Decimal
		self.assertEqual(floor(2),              2)
		self.assertEqual(floor(12.32904),       12)
		self.assertEqual(floor(22.7330),        22)
		self.assertEqual(floor('24.7'),         24)
		self.assertEqual(floor('26.7'),         26)
		self.assertEqual(floor(Decimal(29.45)), 29)

	def test_ceil(self):
		from decimal import Decimal
		self.assertEqual(ceil(2),               2)
		self.assertEqual(ceil(12.32904),        13)
		self.assertEqual(ceil(22.7330),         23)
		self.assertEqual(ceil('24.7'),          25)
		self.assertEqual(ceil('26.7'),          27)
		self.assertEqual(ceil(Decimal(29.45)),  30)

class TestHTMLUtils(unittest.TestCase):
	def test_clean_email_html(self):
		from frappe.utils.html_utils import clean_email_html
		sample = '''<script>a=b</script><h1>Hello</h1><p>Para</p>'''
		clean = clean_email_html(sample)
		self.assertFalse('<script>' in clean)
		self.assertTrue('<h1>Hello</h1>' in clean)

		sample = '''<style>body { font-family: Arial }</style><h1>Hello</h1><p>Para</p>'''
		clean = clean_email_html(sample)
		self.assertFalse('<style>' in clean)
		self.assertTrue('<h1>Hello</h1>' in clean)

		sample = '''<h1>Hello</h1><p>Para</p><a href="http://test.com">text</a>'''
		clean = clean_email_html(sample)
		self.assertTrue('<h1>Hello</h1>' in clean)
		self.assertTrue('<a href="http://test.com">text</a>' in clean)

class TestValidationUtils(unittest.TestCase):
	def test_valid_url(self):
		# Edge cases
		self.assertFalse(validate_url(''))
		self.assertFalse(validate_url(None))

		# Valid URLs
		self.assertTrue(validate_url('https://google.com'))
		self.assertTrue(validate_url('http://frappe.io', throw=True))
		
		# Invalid URLs without throw
		self.assertFalse(validate_url('google.io'))
		self.assertFalse(validate_url('google.io'))

		# Invalid URL with throw
		self.assertRaises(frappe.ValidationError, validate_url, 'frappe', throw=True)

		# Scheme validation
		self.assertFalse(validate_url('https://google.com', valid_schemes='http'))
		self.assertTrue(validate_url('ftp://frappe.cloud', valid_schemes=['https', 'ftp']))
		self.assertFalse(validate_url('bolo://frappe.io', valid_schemes=("http", "https", "ftp", "ftps")))
		self.assertRaises(
			frappe.ValidationError, 
			validate_url, 
			'gopher://frappe.io', 
			valid_schemes='https',
			throw=True
		)

	def test_valid_email(self):
		# Edge cases
		self.assertFalse(validate_email_address(''))
		self.assertFalse(validate_email_address(None))

		# Valid addresses
		self.assertTrue(validate_email_address('someone@frappe.com'))
		self.assertTrue(validate_email_address('someone@frappe.com, anyone@frappe.io'))
		
		# Invalid address
		self.assertFalse(validate_email_address('someone'))
		self.assertFalse(validate_email_address('someone@----.com'))

		# Invalid with throw
		self.assertRaises(
			frappe.InvalidEmailAddressError, 
			validate_email_address, 
			'someone.com', 
			throw=True
		)

class TestImage(unittest.TestCase):
	def test_strip_exif_data(self):
		original_image = Image.open("../apps/frappe/frappe/tests/data/exif_sample_image.jpg")
		original_image_content = io.open("../apps/frappe/frappe/tests/data/exif_sample_image.jpg", mode='rb').read()

		new_image_content = strip_exif_data(original_image_content, "image/jpeg")
		new_image = Image.open(io.BytesIO(new_image_content))

		self.assertEqual(new_image._getexif(), None)
		self.assertNotEqual(original_image._getexif(), new_image._getexif())