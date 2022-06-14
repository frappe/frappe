# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import io
import json
import unittest
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from unittest.mock import patch

import pytz
from PIL import Image

import frappe
from frappe.utils import (
	ceil,
	evaluate_filters,
	floor,
	format_timedelta,
	get_url,
	money_in_words,
	parse_timedelta,
	scrub_urls,
	validate_email_address,
	validate_url,
)
from frappe.utils.data import (
	add_to_date,
	cast,
	get_first_day_of_week,
	get_time,
	get_timedelta,
	getdate,
	now_datetime,
	nowtime,
	validate_python_code,
)
from frappe.utils.dateutils import get_dates_from_timegrain
from frappe.utils.image import strip_exif_data
from frappe.utils.response import json_handler


class TestFilters(unittest.TestCase):
	def test_simple_dict(self):
		self.assertTrue(evaluate_filters({"doctype": "User", "status": "Open"}, {"status": "Open"}))
		self.assertFalse(evaluate_filters({"doctype": "User", "status": "Open"}, {"status": "Closed"}))

	def test_multiple_dict(self):
		self.assertTrue(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "name": "Test 1"}, {"status": "Open", "name": "Test 1"}
			)
		)
		self.assertFalse(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "name": "Test 1"}, {"status": "Closed", "name": "Test 1"}
			)
		)

	def test_list_filters(self):
		self.assertTrue(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "name": "Test 1"},
				[{"status": "Open"}, {"name": "Test 1"}],
			)
		)
		self.assertFalse(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "name": "Test 1"},
				[{"status": "Open"}, {"name": "Test 2"}],
			)
		)

	def test_list_filters_as_list(self):
		self.assertTrue(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "name": "Test 1"},
				[["status", "=", "Open"], ["name", "=", "Test 1"]],
			)
		)
		self.assertFalse(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "name": "Test 1"},
				[["status", "=", "Open"], ["name", "=", "Test 2"]],
			)
		)

	def test_lt_gt(self):
		self.assertTrue(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "age": 20}, {"status": "Open", "age": (">", 10)}
			)
		)
		self.assertFalse(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "age": 20}, {"status": "Open", "age": (">", 30)}
			)
		)


class TestMoney(unittest.TestCase):
	def test_money_in_words(self):
		nums_bhd = [
			(5000, "BHD Five Thousand only."),
			(5000.0, "BHD Five Thousand only."),
			(0.1, "One Hundred Fils only."),
			(0, "BHD Zero only."),
			("Fail", ""),
		]

		nums_ngn = [
			(5000, "NGN Five Thousand only."),
			(5000.0, "NGN Five Thousand only."),
			(0.1, "Ten Kobo only."),
			(0, "NGN Zero only."),
			("Fail", ""),
		]

		for num in nums_bhd:
			self.assertEqual(
				money_in_words(num[0], "BHD"),
				num[1],
				"{0} is not the same as {1}".format(money_in_words(num[0], "BHD"), num[1]),
			)

		for num in nums_ngn:
			self.assertEqual(
				money_in_words(num[0], "NGN"),
				num[1],
				"{0} is not the same as {1}".format(money_in_words(num[0], "NGN"), num[1]),
			)


class TestDataManipulation(unittest.TestCase):
	def test_scrub_urls(self):
		html = """
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
		"""

		html = scrub_urls(html)
		url = get_url()

		self.assertTrue('<a href="http://test.com">Test link 1</a>' in html)
		self.assertTrue('<a href="{0}/about">Test link 2</a>'.format(url) in html)
		self.assertTrue('<a href="{0}/login">Test link 3</a>'.format(url) in html)
		self.assertTrue('<img src="{0}/assets/frappe/test.jpg">'.format(url) in html)
		self.assertTrue(
			"style=\"background-image: url('{0}/assets/frappe/bg.jpg') !important\"".format(url) in html
		)
		self.assertTrue('<a href="mailto:test@example.com">email</a>' in html)


class TestFieldCasting(unittest.TestCase):
	def test_str_types(self):
		STR_TYPES = (
			"Data",
			"Text",
			"Small Text",
			"Long Text",
			"Text Editor",
			"Select",
			"Link",
			"Dynamic Link",
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

		self.assertEqual(floor(2), 2)
		self.assertEqual(floor(12.32904), 12)
		self.assertEqual(floor(22.7330), 22)
		self.assertEqual(floor("24.7"), 24)
		self.assertEqual(floor("26.7"), 26)
		self.assertEqual(floor(Decimal(29.45)), 29)

	def test_ceil(self):
		from decimal import Decimal

		self.assertEqual(ceil(2), 2)
		self.assertEqual(ceil(12.32904), 13)
		self.assertEqual(ceil(22.7330), 23)
		self.assertEqual(ceil("24.7"), 25)
		self.assertEqual(ceil("26.7"), 27)
		self.assertEqual(ceil(Decimal(29.45)), 30)


class TestHTMLUtils(unittest.TestCase):
	def test_clean_email_html(self):
		from frappe.utils.html_utils import clean_email_html

		sample = """<script>a=b</script><h1>Hello</h1><p>Para</p>"""
		clean = clean_email_html(sample)
		self.assertFalse("<script>" in clean)
		self.assertTrue("<h1>Hello</h1>" in clean)

		sample = """<style>body { font-family: Arial }</style><h1>Hello</h1><p>Para</p>"""
		clean = clean_email_html(sample)
		self.assertFalse("<style>" in clean)
		self.assertTrue("<h1>Hello</h1>" in clean)

		sample = """<h1>Hello</h1><p>Para</p><a href="http://test.com">text</a>"""
		clean = clean_email_html(sample)
		self.assertTrue("<h1>Hello</h1>" in clean)
		self.assertTrue('<a href="http://test.com">text</a>' in clean)


class TestValidationUtils(unittest.TestCase):
	def test_valid_url(self):
		# Edge cases
		self.assertFalse(validate_url(""))
		self.assertFalse(validate_url(None))

		# Valid URLs
		self.assertTrue(validate_url("https://google.com"))
		self.assertTrue(validate_url("http://frappe.io", throw=True))

		# Invalid URLs without throw
		self.assertFalse(validate_url("google.io"))
		self.assertFalse(validate_url("google.io"))

		# Invalid URL with throw
		self.assertRaises(frappe.ValidationError, validate_url, "frappe", throw=True)

		# Scheme validation
		self.assertFalse(validate_url("https://google.com", valid_schemes="http"))
		self.assertTrue(validate_url("ftp://frappe.cloud", valid_schemes=["https", "ftp"]))
		self.assertFalse(
			validate_url("bolo://frappe.io", valid_schemes=("http", "https", "ftp", "ftps"))
		)
		self.assertRaises(
			frappe.ValidationError, validate_url, "gopher://frappe.io", valid_schemes="https", throw=True
		)

	def test_valid_email(self):
		# Edge cases
		self.assertFalse(validate_email_address(""))
		self.assertFalse(validate_email_address(None))

		# Valid addresses
		self.assertTrue(validate_email_address("someone@frappe.com"))
		self.assertTrue(validate_email_address("someone@frappe.com, anyone@frappe.io"))

		# Invalid address
		self.assertFalse(validate_email_address("someone"))
		self.assertFalse(validate_email_address("someone@----.com"))

		# Invalid with throw
		self.assertRaises(
			frappe.InvalidEmailAddressError, validate_email_address, "someone.com", throw=True
		)


class TestImage(unittest.TestCase):
	def test_strip_exif_data(self):
		original_image = Image.open("../apps/frappe/frappe/tests/data/exif_sample_image.jpg")
		original_image_content = io.open(
			"../apps/frappe/frappe/tests/data/exif_sample_image.jpg", mode="rb"
		).read()

		new_image_content = strip_exif_data(original_image_content, "image/jpeg")
		new_image = Image.open(io.BytesIO(new_image_content))

		self.assertEqual(new_image._getexif(), None)
		self.assertNotEqual(original_image._getexif(), new_image._getexif())


class TestPythonExpressions(unittest.TestCase):
	def test_validation_for_good_python_expression(self):
		valid_expressions = [
			"foo == bar",
			"foo == 42",
			"password != 'hunter2'",
			"complex != comparison and more_complex == condition",
			"escaped_values == 'str with newline\\n'",
			"check_box_field",
		]
		for expr in valid_expressions:
			try:
				validate_python_code(expr)
			except Exception as e:
				self.fail(f"Invalid error thrown for valid expression: {expr}: {str(e)}")

	def test_validation_for_bad_python_expression(self):
		invalid_expressions = [
			"these_are && js_conditions",
			"more || js_conditions",
			"curly_quotes_bad == “const”",
			"oops = forgot_equals",
		]
		for expr in invalid_expressions:
			self.assertRaises(frappe.ValidationError, validate_python_code, expr)


class TestDateUtils(unittest.TestCase):
	def test_first_day_of_week(self):
		# Monday as start of the week
		with patch.object(frappe.utils.data, "get_first_day_of_the_week", return_value="Monday"):
			self.assertEqual(
				frappe.utils.get_first_day_of_week("2020-12-25"), frappe.utils.getdate("2020-12-21")
			)
			self.assertEqual(
				frappe.utils.get_first_day_of_week("2020-12-20"), frappe.utils.getdate("2020-12-14")
			)

		# Sunday as start of the week
		self.assertEqual(
			frappe.utils.get_first_day_of_week("2020-12-25"), frappe.utils.getdate("2020-12-20")
		)
		self.assertEqual(
			frappe.utils.get_first_day_of_week("2020-12-21"), frappe.utils.getdate("2020-12-20")
		)

	def test_last_day_of_week(self):
		self.assertEqual(
			frappe.utils.get_last_day_of_week("2020-12-24"), frappe.utils.getdate("2020-12-26")
		)
		self.assertEqual(
			frappe.utils.get_last_day_of_week("2020-12-28"), frappe.utils.getdate("2021-01-02")
		)

	def test_get_time(self):
		datetime_input = now_datetime()
		timedelta_input = get_timedelta()
		time_input = nowtime()

		self.assertIsInstance(get_time(datetime_input), time)
		self.assertIsInstance(get_time(timedelta_input), time)
		self.assertIsInstance(get_time(time_input), time)
		self.assertIsInstance(get_time("100:2:12"), time)
		self.assertIsInstance(get_time(str(datetime_input)), time)
		self.assertIsInstance(get_time(str(timedelta_input)), time)
		self.assertIsInstance(get_time(str(time_input)), time)

	def test_get_timedelta(self):
		datetime_input = now_datetime()
		timedelta_input = get_timedelta()
		time_input = nowtime()

		self.assertIsInstance(get_timedelta(), timedelta)
		self.assertIsInstance(get_timedelta("100:2:12"), timedelta)
		self.assertIsInstance(get_timedelta("17:21:00"), timedelta)
		self.assertIsInstance(get_timedelta("2012-01-19 17:21:00"), timedelta)
		self.assertIsInstance(get_timedelta(str(datetime_input)), timedelta)
		self.assertIsInstance(get_timedelta(str(timedelta_input)), timedelta)
		self.assertIsInstance(get_timedelta(str(time_input)), timedelta)

	def test_date_from_timegrain(self):
		start_date = getdate("2021-01-01")

		daily = get_dates_from_timegrain(start_date, add_to_date(start_date, days=6), "Daily")
		self.assertEqual(len(daily), 7)
		for idx, d in enumerate(daily):
			self.assertEqual(d, add_to_date(start_date, days=idx))

		start = get_first_day_of_week(start_date)
		end = add_to_date(add_to_date(start, weeks=52), days=-1)
		weekly = get_dates_from_timegrain(start, end, "Weekly")
		self.assertEqual(len(weekly), 52)
		for idx, d in enumerate(weekly, start=1):
			self.assertEqual(d, add_to_date(start, days=7 * idx - 1))

		quarterly = get_dates_from_timegrain(start_date, add_to_date(start_date, months=5), "Quarterly")
		self.assertEqual(len(quarterly), 2)
		for idx, d in enumerate(quarterly, start=1):
			self.assertEqual(d, add_to_date(start_date, months=idx * 3, days=-1))

		yearly = get_dates_from_timegrain(start_date, add_to_date(start_date, years=2), "Yearly")
		self.assertEqual(len(yearly), 3)
		for idx, d in enumerate(yearly, start=1):
			self.assertEqual(d, add_to_date(start_date, years=idx, days=-1))


class TestResponse(unittest.TestCase):
	def test_json_handler(self):
		class TEST(Enum):
			ABC = "!@)@)!"
			BCE = "ENJD"

		GOOD_OBJECT = {
			"time_types": [
				date(year=2020, month=12, day=2),
				datetime(
					year=2020, month=12, day=2, hour=23, minute=23, second=23, microsecond=23, tzinfo=pytz.utc
				),
				time(hour=23, minute=23, second=23, microsecond=23, tzinfo=pytz.utc),
				timedelta(days=10, hours=12, minutes=120, seconds=10),
			],
			"float": [
				Decimal(29.21),
			],
			"doc": [
				frappe.get_doc("System Settings"),
			],
			"iter": [
				{1, 2, 3},
				(1, 2, 3),
				"abcdef",
			],
			"string": "abcdef",
		}

		BAD_OBJECT = {"Enum": TEST}

		processed_object = json.loads(json.dumps(GOOD_OBJECT, default=json_handler))

		self.assertTrue(all([isinstance(x, str) for x in processed_object["time_types"]]))
		self.assertTrue(all([isinstance(x, float) for x in processed_object["float"]]))
		self.assertTrue(all([isinstance(x, (list, str)) for x in processed_object["iter"]]))
		self.assertIsInstance(processed_object["string"], str)
		with self.assertRaises(TypeError):
			json.dumps(BAD_OBJECT, default=json_handler)


class TestTimeDeltaUtils(unittest.TestCase):
	def test_format_timedelta(self):
		self.assertEqual(format_timedelta(timedelta(seconds=0)), "0:00:00")
		self.assertEqual(format_timedelta(timedelta(hours=10)), "10:00:00")
		self.assertEqual(format_timedelta(timedelta(hours=100)), "100:00:00")
		self.assertEqual(format_timedelta(timedelta(seconds=100, microseconds=129)), "0:01:40.000129")
		self.assertEqual(
			format_timedelta(timedelta(seconds=100, microseconds=12212199129)), "3:25:12.199129"
		)

	def test_parse_timedelta(self):
		self.assertEqual(parse_timedelta("0:0:0"), timedelta(seconds=0))
		self.assertEqual(parse_timedelta("10:0:0"), timedelta(hours=10))
		self.assertEqual(
			parse_timedelta("7 days, 0:32:18.192221"), timedelta(days=7, seconds=1938, microseconds=192221)
		)
		self.assertEqual(parse_timedelta("7 days, 0:32:18"), timedelta(days=7, seconds=1938))


class TestXlsxUtils(unittest.TestCase):
	def test_unescape(self):
		from frappe.utils.xlsxutils import handle_html

		val = handle_html("<p>html data &gt;</p>")
		self.assertIn("html data >", val)
		self.assertEqual("abc", handle_html("abc"))
