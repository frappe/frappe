# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import unittest

from frappe.utils import evaluate_filters, money_in_words, scrub_urls, get_url
from frappe.utils import ceil, floor
from frappe.utils.data import cast

from datetime import datetime, timedelta, date

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
				money_in_words(num[0], "BHD"), num[1], "{0} is not the same as {1}".
					format(money_in_words(num[0], "BHD"), num[1])
			)

		for num in nums_ngn:
			self.assertEqual(
				money_in_words(num[0], "NGN"), num[1], "{0} is not the same as {1}".
					format(money_in_words(num[0], "NGN"), num[1])
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

class TestFieldCasting(unittest.TestCase):
	def test_str_types(self):
		STR_TYPES = (
			"Data", "Text", "Small Text", "Long Text", "Text Editor", "Select", "Link", "Dynamic Link"
		)
		for fieldtype in STR_TYPES:
			self.assertIsInstance(cast(fieldtype, value=None), str)
			self.assertIsInstance(cast(fieldtype, value="12-12-2021"), str)
			self.assertIsInstance(cast(fieldtype, value=""), str)
			self.assertIsInstance(cast(fieldtype, value=[]), str)
			self.assertIsInstance(cast(fieldtype, value=set()), str)

	def test_float_types(self):
		FLOAT_TYPES = ("Currency", "Float", "Percent")
		for fieldtype in FLOAT_TYPES:
			self.assertIsInstance(cast(fieldtype, value=None), float)
			self.assertIsInstance(cast(fieldtype, value=1.12), float)
			self.assertIsInstance(cast(fieldtype, value=112), float)

	def test_int_types(self):
		INT_TYPES = ("Int", "Check")

		for fieldtype in INT_TYPES:
			self.assertIsInstance(cast(fieldtype, value=None), int)
			self.assertIsInstance(cast(fieldtype, value=1.12), int)
			self.assertIsInstance(cast(fieldtype, value=112), int)

	def test_datetime_types(self):
		self.assertIsInstance(cast("Datetime", value=None), datetime)
		self.assertIsInstance(cast("Datetime", value="12-2-22"), datetime)

	def test_date_types(self):
		self.assertIsInstance(cast("Date", value=None), date)
		self.assertIsInstance(cast("Date", value="12-12-2021"), date)

	def test_time_types(self):
		self.assertIsInstance(cast("Time", value=None), timedelta)
		self.assertIsInstance(cast("Time", value="12:03:34"), timedelta)

class TestMathUtils(unittest.TestCase):
	def test_floor(self):
		from decimal import Decimal
		self.assertEqual(floor(2),              2 )
		self.assertEqual(floor(12.32904),       12)
		self.assertEqual(floor(22.7330),        22)
		self.assertEqual(floor('24.7'),         24)
		self.assertEqual(floor('26.7'),         26)
		self.assertEqual(floor(Decimal(29.45)), 29)

	def test_ceil(self):
		from decimal import Decimal
		self.assertEqual(ceil(2),               2 )
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
