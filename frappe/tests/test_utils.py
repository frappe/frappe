# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import io
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
from enum import Enum
from io import StringIO
from mimetypes import guess_type
from unittest.mock import patch

from hypothesis import given
from hypothesis import strategies as st
from PIL import Image

import frappe
from frappe.installer import parse_app_name
from frappe.model.document import Document
from frappe.tests import IntegrationTestCase, MockedRequestTestCase
from frappe.tests.utils import toggle_test_mode
from frappe.utils import (
	ceil,
	dict_to_str,
	execute_in_shell,
	floor,
	flt,
	format_timedelta,
	get_bench_path,
	get_file_timestamp,
	get_gravatar,
	get_site_info,
	get_sites,
	get_url,
	money_in_words,
	parse_and_map_trackers_from_url,
	parse_timedelta,
	random_string,
	remove_blanks,
	safe_json_loads,
	scrub_urls,
	validate_email_address,
	validate_name,
	validate_phone_number_with_country_code,
	validate_url,
)
from frappe.utils.change_log import (
	get_source_url,
	parse_github_url,
)
from frappe.utils.data import (
	add_to_date,
	add_trackers_to_url,
	add_years,
	cast,
	cint,
	cstr,
	duration_to_seconds,
	evaluate_filters,
	expand_relative_urls,
	get_datetime,
	get_first_day_of_week,
	get_time,
	get_timedelta,
	get_timespan_date_range,
	get_url_to_form,
	get_year_ending,
	getdate,
	is_invalid_date_string,
	map_trackers,
	now_datetime,
	nowtime,
	pretty_date,
	rounded,
	sha256_hash,
	to_timedelta,
	validate_python_code,
)
from frappe.utils.dateutils import get_dates_from_timegrain
from frappe.utils.diff import _get_value_from_version, get_version_diff, version_query
from frappe.utils.identicon import Identicon
from frappe.utils.image import optimize_image, strip_exif_data
from frappe.utils.make_random import can_make, get_random, how_many
from frappe.utils.response import json_handler
from frappe.utils.synchronization import LockTimeoutError, filelock


class Capturing(list):
	# ref: https://stackoverflow.com/a/16571630/10309266
	def __enter__(self):
		self._stdout = sys.stdout
		sys.stdout = self._stringio = StringIO()
		return self

	def __exit__(self, *args):
		self.extend(self._stringio.getvalue().splitlines())
		del self._stringio
		sys.stdout = self._stdout


class TestFilters(IntegrationTestCase):
	def test_simple_dict(self):
		self.assertTrue(evaluate_filters({"doctype": "User", "status": "Open"}, {"status": "Open"}))
		self.assertFalse(evaluate_filters({"doctype": "User", "status": "Open"}, {"status": "Closed"}))

	def test_multiple_dict(self):
		self.assertTrue(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "name": "Test 1"},
				{"status": "Open", "name": "Test 1"},
			)
		)
		self.assertFalse(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "name": "Test 1"},
				{"status": "Closed", "name": "Test 1"},
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
				{"doctype": "User", "status": "Open", "age": 20},
				{"status": "Open", "age": (">", 10)},
			)
		)
		self.assertFalse(
			evaluate_filters(
				{"doctype": "User", "status": "Open", "age": 20},
				{"status": "Open", "age": (">", 30)},
			)
		)

	def test_date_time(self):
		# date fields
		self.assertTrue(
			evaluate_filters(
				{"doctype": "User", "birth_date": "2023-02-28"},
				[("User", "birth_date", ">", "01-04-2022")],
			)
		)
		self.assertFalse(
			evaluate_filters(
				{"doctype": "User", "birth_date": "2023-02-28"},
				[("User", "birth_date", "<", "28-02-2023")],
			)
		)

		# datetime fields
		self.assertTrue(
			evaluate_filters(
				{"doctype": "User", "last_active": "2023-02-28 15:14:56"},
				[("User", "last_active", ">", "01-04-2022 00:00:00")],
			)
		)
		self.assertFalse(
			evaluate_filters(
				{"doctype": "User", "last_active": "2023-02-28 15:14:56"},
				[("User", "last_active", "<", "28-02-2023 00:00:00")],
			)
		)

	def test_filter_evaluation(self):
		doc = {
			"doctype": "User",
			"username": "test_abc",
			"prefix": "startswith",
			"suffix": "endswith",
			"empty": None,
			"number": 0,
		}

		test_cases = [
			([["username", "like", "test"]], True),
			([["username", "like", "user1"]], False),
			([["username", "not like", "test"]], False),
			([["username", "not like", "user1"]], True),
			([["prefix", "like", "start%"]], True),
			([["prefix", "not like", "end%"]], True),
			([["suffix", "like", "%with"]], True),
			([["suffix", "not like", "%end"]], True),
			([["suffix", "is", "set"]], True),
			([["suffix", "is", "not set"]], False),
			([["empty", "is", "set"]], False),
			([["empty", "is", "not set"]], True),
			([["number", "is", "set"]], True),
		]

		for filter, expected_result in test_cases:
			self.assertEqual(evaluate_filters(doc, filter), expected_result, msg=f"{filter}")

	def test_timespan(self):
		doc = {
			"doctype": "User",
			"last_password_reset_date": getdate(),
		}
		self.assertTrue(evaluate_filters(doc, [("last_password_reset_date", "Timespan", "today")]))
		self.assertFalse(evaluate_filters(doc, [("last_password_reset_date", "Timespan", "last year")]))

		doc = {
			"doctype": "User",
			"last_password_reset_date": None,
		}
		self.assertFalse(evaluate_filters(doc, [("last_password_reset_date", "Timespan", "today")]))


class TestMoney(IntegrationTestCase):
	def test_money_in_words(self):
		test_cases = {
			"BHD": [
				(5000, "BHD Five Thousand only."),
				(5000.0, "BHD Five Thousand only."),
				(0.1, "One Hundred Fils only."),
				(0, "BHD Zero only."),
				("Fail", ""),
			],
			"NGN": [
				(5000, "NGN Five Thousand only."),
				(5000.0, "NGN Five Thousand only."),
				(0.1, "Ten Kobo only."),
				(0, "NGN Zero only."),
				("Fail", ""),
			],
			"MRO": [
				(5000, "MRO Five Thousand only."),
				(5000.0, "MRO Five Thousand only."),
				(1.4, "MRO One and Two Khoums only."),
				(0.2, "One Khoums only."),
				(0, "MRO Zero only."),
				("Fail", ""),
			],
		}

		for currency, cases in test_cases.items():
			for money, expected_words in cases:
				words = money_in_words(money, currency)
				self.assertEqual(
					words,
					expected_words,
					f"{words} is not the same as {expected_words}",
				)

	def test_money_in_words_without_fraction(self):
		# VND doesn't have fractions
		words = money_in_words("42.01", "VND")
		self.assertEqual(words, "VND Forty Two only.")


class TestDataManipulation(IntegrationTestCase):
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
		self.assertTrue(f'<a href="{url}/about">Test link 2</a>' in html)
		self.assertTrue(f'<a href="{url}/login">Test link 3</a>' in html)
		self.assertTrue(f'<img src="{url}/assets/frappe/test.jpg">' in html)
		self.assertTrue(f"style=\"background-image: url('{url}/assets/frappe/bg.jpg') !important\"" in html)
		self.assertTrue('<a href="mailto:test@example.com">email</a>' in html)


class TestFieldCasting(IntegrationTestCase):
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


class TestMathUtils(IntegrationTestCase):
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


class TestHTMLUtils(IntegrationTestCase):
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

	def test_sanitize_html(self):
		from frappe.utils.html_utils import sanitize_html

		clean = sanitize_html("<ol data-list='ordered' unknown_attr='xyz'></ol>")
		self.assertIn("ordered", clean)
		self.assertNotIn("xyz", clean)


class TestValidationUtils(IntegrationTestCase):
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
		self.assertFalse(validate_url("bolo://frappe.io", valid_schemes=("http", "https", "ftp", "ftps")))
		self.assertRaises(
			frappe.ValidationError,
			validate_url,
			"gopher://frappe.io",
			valid_schemes="https",
			throw=True,
		)

	def test_valid_email(self):
		# Edge cases
		self.assertFalse(validate_email_address(""))
		self.assertFalse(validate_email_address(None))

		# Valid addresses
		self.assertTrue(validate_email_address("someone@frappe.com"))
		self.assertTrue(validate_email_address("someone@frappe.com, anyone@frappe.io"))
		self.assertTrue(validate_email_address("test%201@frappe.com"))

		# Invalid address
		self.assertFalse(validate_email_address("someone"))
		self.assertFalse(validate_email_address("someone@----.com"))
		self.assertFalse(validate_email_address("test 1@frappe.com"))
		self.assertFalse(validate_email_address("test@example.com test2@example.com,undisclosed-recipient"))

		# Invalid with throw
		self.assertRaises(
			frappe.InvalidEmailAddressError,
			validate_email_address,
			"someone.com",
			throw=True,
		)

		self.assertEqual(validate_email_address("Some%20One@frappe.com"), "Some%20One@frappe.com")
		self.assertEqual(
			validate_email_address("erp+Job%20Applicant=JA00004@frappe.com"),
			"erp+Job%20Applicant=JA00004@frappe.com",
		)

	def test_valid_phone(self):
		valid_phones = ["+91 1234567890", ""]

		for phone in valid_phones:
			validate_phone_number_with_country_code(phone, "field")
		self.assertRaises(
			frappe.InvalidPhoneNumberError,
			validate_phone_number_with_country_code,
			"+420 1234567890",
			"field",
		)

	def test_validate_name(self):
		valid_names = ["", "abc", "asd a13", "asd-asd"]
		for name in valid_names:
			validate_name(name, True)

		invalid_names = ["asd$wat", "asasd/ads"]
		for name in invalid_names:
			self.assertRaises(frappe.InvalidNameError, validate_name, name, True)


class TestImage(IntegrationTestCase):
	def test_strip_exif_data(self):
		original_image = Image.open(frappe.get_app_path("frappe", "tests", "data", "exif_sample_image.jpg"))
		original_image_content = open(
			frappe.get_app_path("frappe", "tests", "data", "exif_sample_image.jpg"),
			mode="rb",
		).read()

		new_image_content = strip_exif_data(original_image_content, "image/jpeg")
		new_image = Image.open(io.BytesIO(new_image_content))

		self.assertEqual(new_image._getexif(), None)
		self.assertNotEqual(original_image._getexif(), new_image._getexif())

	def test_optimize_image(self):
		image_file_path = frappe.get_app_path("frappe", "tests", "data", "sample_image_for_optimization.jpg")
		content_type = guess_type(image_file_path)[0]
		original_content = open(image_file_path, mode="rb").read()

		optimized_content = optimize_image(original_content, content_type, max_width=500, max_height=500)
		optimized_image = Image.open(io.BytesIO(optimized_content))
		width, height = optimized_image.size

		self.assertLessEqual(width, 500)
		self.assertLessEqual(height, 500)
		self.assertLess(len(optimized_content), len(original_content))


class TestPythonExpressions(IntegrationTestCase):
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
				self.fail(f"Invalid error thrown for valid expression: {expr}: {e!s}")

	def test_validation_for_bad_python_expression(self):
		invalid_expressions = [
			"these_are && js_conditions",
			"more || js_conditions",
			"curly_quotes_bad == “const”",
			"oops = forgot_equals",
		]
		for expr in invalid_expressions:
			self.assertRaises(frappe.ValidationError, validate_python_code, expr)


class TestDiffUtils(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.doc = frappe.get_doc(doctype="Client Script", dt="Client Script", name="test_client_script")
		cls.doc.insert()
		cls.doc.script = "2;"
		cls.doc.save(ignore_version=False)
		cls.doc.script = "42;"
		cls.doc.save(ignore_version=False)

		cls.versions = version_query(
			doctype="Version",
			txt="",
			searchfield="name",
			start=0,
			page_len=20,
			filters={"ref_doctype": cls.doc.doctype, "docname": cls.doc.name},
		)

	@classmethod
	def tearDownClass(cls):
		cls.doc.delete()

	def test_version_query(self):
		self.assertGreaterEqual(len(self.versions), 2)

	def test_get_field_value_from_version(self):
		latest_version = self.versions[0][0]
		self.assertEqual("42;", _get_value_from_version(latest_version, fieldname="script")[0])
		old_version = self.versions[1][0]
		self.assertEqual("2;", _get_value_from_version(old_version, fieldname="script")[0])

	def test_get_version_diff(self):
		old_version = self.versions[1][0]
		latest_version = self.versions[0][0]

		diff = get_version_diff(old_version, latest_version)
		self.assertIn("-2;", diff)
		self.assertIn("+42;", diff)


class TestDateUtils(IntegrationTestCase):
	def test_first_day_of_week(self):
		# Monday as start of the week
		with patch.object(frappe.utils.data, "get_first_day_of_the_week", return_value="Monday"):
			self.assertEqual(
				frappe.utils.get_first_day_of_week("2020-12-25"),
				frappe.utils.getdate("2020-12-21"),
			)
			self.assertEqual(
				frappe.utils.get_first_day_of_week("2020-12-20"),
				frappe.utils.getdate("2020-12-14"),
			)

		# Sunday as start of the week
		self.assertEqual(
			frappe.utils.get_first_day_of_week("2020-12-25"),
			frappe.utils.getdate("2020-12-20"),
		)
		self.assertEqual(
			frappe.utils.get_first_day_of_week("2020-12-21"),
			frappe.utils.getdate("2020-12-20"),
		)

	def test_last_day_of_week(self):
		self.assertEqual(
			frappe.utils.get_last_day_of_week("2020-12-24"),
			frappe.utils.getdate("2020-12-26"),
		)
		self.assertEqual(
			frappe.utils.get_last_day_of_week("2020-12-28"),
			frappe.utils.getdate("2021-01-02"),
		)

	def test_is_last_day_of_the_month(self):
		self.assertEqual(frappe.utils.is_last_day_of_the_month("2020-12-24"), False)
		self.assertEqual(frappe.utils.is_last_day_of_the_month("2020-12-31"), True)

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
		self.assertIsInstance(get_timedelta(get_timedelta("100:2:12")), timedelta)

	def test_to_timedelta(self):
		self.assertEqual(to_timedelta("00:00:01"), timedelta(seconds=1))
		self.assertEqual(to_timedelta("10:00:01"), timedelta(seconds=1, hours=10))
		self.assertEqual(to_timedelta(time(hour=2)), timedelta(hours=2))

	def test_add_date_utils(self):
		self.assertEqual(add_years(datetime(2020, 1, 1), 1), datetime(2021, 1, 1))

	def test_duration_to_sec(self):
		self.assertEqual(duration_to_seconds("3h 34m 45s"), 12885)
		self.assertEqual(duration_to_seconds("1h"), 3600)
		self.assertEqual(duration_to_seconds("110m"), 110 * 60)
		self.assertEqual(duration_to_seconds("110m"), 110 * 60)

	def test_get_timespan_date_range(self):
		supported_timespans = [
			"last week",
			"last month",
			"last quarter",
			"last 6 months",
			"last year",
			"yesterday",
			"today",
			"tomorrow",
			"this week",
			"this month",
			"this quarter",
			"this year",
			"next week",
			"next month",
			"next quarter",
			"next 6 months",
			"next year",
		]

		for ts in supported_timespans:
			res = get_timespan_date_range(ts)
			self.assertEqual(len(res), 2)

			# Manual type checking eh?
			self.assertIsInstance(res[0], date)
			self.assertIsInstance(res[1], date)

	def test_timesmap_utils(self):
		self.assertEqual(get_year_ending(date(2021, 1, 1)), date(2021, 12, 31))
		self.assertEqual(get_year_ending(date(2021, 1, 31)), date(2021, 12, 31))

	@given(st.datetimes())
	def test_get_datetime(self, original):
		if is_invalid_date_string(str(original)):
			return
		parsed = get_datetime(str(original))
		self.assertEqual(parsed, original)

	@given(st.datetimes(timezones=st.timezones()))
	def test_get_datetime_tz_aware(self, original):
		if is_invalid_date_string(str(original)):
			return
		parsed = get_datetime(str(original))
		self.assertEqual(parsed, original)

	def test_pretty_date(self):
		from frappe import _

		now = get_datetime()

		test_cases = {
			now: _("1 second ago"),
			add_to_date(now, minutes=-1): _("1 minute ago"),
			add_to_date(now, minutes=-3): _("3 minutes ago"),
			add_to_date(now, hours=-1): _("1 hour ago"),
			add_to_date(now, hours=-2): _("2 hours ago"),
			add_to_date(now, days=-1): _("1 day ago"),
			add_to_date(now, days=-5): _("5 days ago"),
			add_to_date(now, days=-8): _("1 week ago"),
			add_to_date(now, days=-14): _("2 weeks ago"),
			add_to_date(now, days=-32): _("1 month ago"),
			add_to_date(now, days=-32 * 2): _("2 months ago"),
			add_to_date(now, years=-1, days=-5): _("1 year ago"),
			add_to_date(now, years=-2, days=-10): _("2 years ago"),
		}

		for dt, exp_message in test_cases.items():
			self.assertEqual(pretty_date(dt), exp_message)

		self.assertEqual(pretty_date(add_to_date(now, days=-5), mini=True), "5d")

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


class TestResponse(IntegrationTestCase):
	def test_json_handler(self):
		class TEST(Enum):
			ABC = "!@)@)!"
			BCE = "ENJD"

		GOOD_OBJECT = {
			"time_types": [
				date(year=2020, month=12, day=2),
				datetime(
					year=2020,
					month=12,
					day=2,
					hour=23,
					minute=23,
					second=23,
					microsecond=23,
					tzinfo=timezone.utc,
				),
				time(hour=23, minute=23, second=23, microsecond=23, tzinfo=timezone.utc),
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
		self.assertTrue(all([isinstance(x, list | str) for x in processed_object["iter"]]))
		self.assertIsInstance(processed_object["string"], str)
		with self.assertRaises(TypeError):
			json.dumps(BAD_OBJECT, default=json_handler)


class TestTimeDeltaUtils(IntegrationTestCase):
	def test_format_timedelta(self):
		self.assertEqual(format_timedelta(timedelta(seconds=0)), "0:00:00")
		self.assertEqual(format_timedelta(timedelta(hours=10)), "10:00:00")
		self.assertEqual(format_timedelta(timedelta(hours=100)), "100:00:00")
		self.assertEqual(format_timedelta(timedelta(seconds=100, microseconds=129)), "0:01:40.000129")
		self.assertEqual(
			format_timedelta(timedelta(seconds=100, microseconds=12212199129)),
			"3:25:12.199129",
		)

	def test_parse_timedelta(self):
		self.assertEqual(parse_timedelta("0:0:0"), timedelta(seconds=0))
		self.assertEqual(parse_timedelta("10:0:0"), timedelta(hours=10))
		self.assertEqual(
			parse_timedelta("7 days, 0:32:18.192221"),
			timedelta(days=7, seconds=1938, microseconds=192221),
		)
		self.assertEqual(parse_timedelta("7 days, 0:32:18"), timedelta(days=7, seconds=1938))


class TestXlsxUtils(IntegrationTestCase):
	def test_unescape(self):
		from frappe.utils.xlsxutils import handle_html

		val = handle_html("<p>html data &gt;</p>")
		self.assertIn("html data >", val)
		self.assertEqual("abc", handle_html("abc"))


class TestLinkTitle(IntegrationTestCase):
	def test_link_title_doctypes_in_boot_info(self):
		"""
		Test that doctypes are added to link_title_map in boot_info
		"""
		custom_doctype = frappe.get_doc(
			{
				"doctype": "DocType",
				"module": "Core",
				"custom": 1,
				"fields": [
					{
						"label": "Test Field",
						"fieldname": "test_title_field",
						"fieldtype": "Data",
					}
				],
				"show_title_field_in_link": 1,
				"title_field": "test_title_field",
				"permissions": [{"role": "System Manager", "read": 1}],
				"name": "Test Custom Doctype for Link Title",
			}
		)
		custom_doctype.insert()

		prop_setter = frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doc_type": "User",
				"property": "show_title_field_in_link",
				"property_type": "Check",
				"doctype_or_field": "DocType",
				"value": "1",
			}
		).insert()

		from frappe.boot import get_link_title_doctypes

		link_title_doctypes = get_link_title_doctypes()
		self.assertTrue("User" in link_title_doctypes)
		self.assertTrue("Test Custom Doctype for Link Title" in link_title_doctypes)

		prop_setter.delete()
		custom_doctype.delete()

	def test_link_titles_on_getdoc(self):
		"""
		Test that link titles are added to the doctype on getdoc
		"""
		prop_setter = frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doc_type": "User",
				"property": "show_title_field_in_link",
				"property_type": "Check",
				"doctype_or_field": "DocType",
				"value": "1",
			}
		).insert()

		user = frappe.get_doc(
			{
				"doctype": "User",
				"user_type": "Website User",
				"email": "test_user_for_link_title@example.com",
				"send_welcome_email": 0,
				"first_name": "Test User for Link Title",
			}
		).insert(ignore_permissions=True)

		todo = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "test-link-title-on-getdoc",
				"allocated_to": user.name,
			}
		).insert()

		from frappe.desk.form.load import getdoc

		getdoc("ToDo", todo.name)
		link_titles = frappe.local.response["_link_titles"]

		self.assertTrue(f"{user.doctype}::{user.name}" in link_titles)
		self.assertEqual(link_titles[f"{user.doctype}::{user.name}"], user.full_name)

		todo.delete()
		user.delete()
		prop_setter.delete()


class TestAppParser(MockedRequestTestCase):
	def test_app_name_parser(self):
		self.responses.add(
			"HEAD",
			"https://api.github.com/repos/frappe/healthcare",
			status=200,
			json={},
		)
		bench_path = get_bench_path()
		frappe_app = os.path.join(bench_path, "apps", "frappe")
		self.assertEqual("frappe", parse_app_name(frappe_app))
		self.assertEqual("healthcare", parse_app_name("healthcare"))
		self.assertEqual("healthcare", parse_app_name("https://github.com/frappe/healthcare.git"))
		self.assertEqual("healthcare", parse_app_name("git@github.com:frappe/healthcare.git"))
		self.assertEqual("healthcare", parse_app_name("frappe/healthcare@develop"))


class TestIntrospectionMagic(IntegrationTestCase):
	"""Test utils that inspect live objects"""

	def test_get_newargs(self):
		# `kwargs` is just convention any **varname should work.
		def f(a, b=2, **args):
			pass

		safe_kwargs = {"company": "Wind Power", "b": 1}
		self.assertEqual(frappe.get_newargs(f, safe_kwargs), safe_kwargs)

		unsafe_args = dict(safe_kwargs)
		unsafe_args.update({"ignore_permissions": True, "flags": {"ignore_mandatory": True}})
		self.assertEqual(frappe.get_newargs(f, unsafe_args), safe_kwargs)

	def test_strip_off_kwargs_when_not_supported(self):
		def f(a, b=2):
			pass

		args = {"company": "Wind Power", "b": 1}
		self.assertEqual(frappe.get_newargs(f, args), {"b": 1})

		# No args
		self.assertEqual(frappe.get_newargs(lambda: None, args), {})


class TestMakeRandom(IntegrationTestCase):
	def test_get_random(self):
		self.assertIsInstance(get_random("DocType", doc=True), Document)
		self.assertIsInstance(get_random("DocType"), str)

	def test_can_make(self):
		self.assertIsInstance(can_make("User"), bool)

	def test_how_many(self):
		self.assertIsInstance(how_many("User"), int)


class TestLazyLoader(IntegrationTestCase):
	def test_lazy_import_module(self):
		from frappe.utils.lazy_loader import lazy_import

		with Capturing() as output:
			ls = lazy_import("frappe.tests.data.load_sleep")
		self.assertEqual(output, [])

		with Capturing() as output:
			ls.time
		self.assertEqual(["Module `frappe.tests.data.load_sleep` loaded"], output)


class TestIdenticon(IntegrationTestCase):
	def test_get_gravatar(self):
		# developers@frappe.io has a gravatar linked so str URL will be returned
		toggle_test_mode(False)
		gravatar_url = get_gravatar("developers@frappe.io")
		toggle_test_mode(True)
		self.assertIsInstance(gravatar_url, str)
		self.assertTrue(gravatar_url.startswith("http"))

		# random email will require Identicon to be generated, which will be a base64 string
		gravatar_url = get_gravatar(f"developers{random_string(6)}@frappe.io")
		self.assertIsInstance(gravatar_url, str)
		self.assertTrue(gravatar_url.startswith("data:image/png;base64,"))

	def test_generate_identicon(self):
		identicon = Identicon(random_string(6))
		with patch.object(identicon.image, "show") as show:
			identicon.generate()
			show.assert_called_once()

		identicon_bs64 = identicon.base64()
		self.assertIsInstance(identicon_bs64, str)
		self.assertTrue(identicon_bs64.startswith("data:image/png;base64,"))


class TestContainerUtils(IntegrationTestCase):
	def test_dict_to_str(self):
		self.assertEqual(dict_to_str({"a": "b"}), "a=b")

	def test_remove_blanks(self):
		a = {"asd": "", "b": None, "c": "d"}
		remove_blanks(a)
		self.assertEqual(len(a), 1)
		self.assertEqual(a["c"], "d")


class TestLocks(IntegrationTestCase):
	def test_locktimeout(self):
		lock_name = "test_lock"
		with filelock(lock_name):
			with self.assertRaises(LockTimeoutError):
				with filelock(lock_name, timeout=1):
					self.fail("Locks not working")

	def test_global_lock(self):
		lock_name = "test_global"
		with filelock(lock_name, is_global=True):
			with self.assertRaises(LockTimeoutError):
				with filelock(lock_name, timeout=1, is_global=True):
					self.fail("Global locks not working")


class TestMiscUtils(IntegrationTestCase):
	def test_get_file_timestamp(self):
		self.assertIsInstance(get_file_timestamp(__file__), str)

	def test_execute_in_shell(self):
		err, out = execute_in_shell("ls")
		self.assertIn("apps", cstr(out))

	def test_get_all_sites(self):
		self.assertIn(frappe.local.site, get_sites())

	def test_get_site_info(self):
		info = get_site_info()

		installed_apps = [app["app_name"] for app in info["installed_apps"]]
		self.assertIn("frappe", installed_apps)
		self.assertGreaterEqual(len(info["users"]), 1)

	def test_get_url_to_form(self):
		self.assertTrue(get_url_to_form("System Settings").endswith("/app/system-settings"))
		self.assertTrue(get_url_to_form("User", "Test User").endswith("/app/user/Test%20User"))

	def test_safe_json_load(self):
		self.assertEqual(safe_json_loads("{}"), {})
		self.assertEqual(safe_json_loads("{ /}"), "{ /}")
		self.assertEqual(safe_json_loads("12"), 12)  # this is a quirk

	def test_url_expansion(self):
		unchanged_links = [
			"<a href='tel:12345432'>My Phone</a>)",
			"<a href='mailto:hello@example.com'>My Email</a>)",
			"<a href='data:hello@example.com'>Data</a>)",
		]
		for link in unchanged_links:
			self.assertEqual(link, expand_relative_urls(link))

		site = get_url()

		transforms = [("<a href='/about'>About</a>)", f"<a href='{site}/about'>About</a>)")]
		for input, output in transforms:
			self.assertEqual(output, expand_relative_urls(input))


class TestTypingValidations(IntegrationTestCase):
	ERR_REGEX = "^Argument '.*' should be of type '.*' but got '.*' instead.$"

	def test_validate_whitelisted_api(self):
		@frappe.whitelist()
		def simple(string: str, number: int):
			return

		@frappe.whitelist()
		def varkw(string: str, **kwargs):
			return

		test_cases = [
			(simple, (object(), object()), {}),
			(varkw, (object(),), {"xyz": object()}),
		]

		for fn, args, kwargs in test_cases:
			with self.assertRaisesRegex(frappe.FrappeTypeError, self.ERR_REGEX):
				fn(*args, **kwargs)

	def test_validate_whitelisted_doc_method(self):
		report = frappe.get_last_doc("Report")

		with self.assertRaisesRegex(frappe.FrappeTypeError, self.ERR_REGEX):
			report.toggle_disable(["disable"])

		current_value = report.disabled
		changed_value = not current_value

		report.toggle_disable(changed_value)
		report.toggle_disable(current_value)


class TestTBSanitization(IntegrationTestCase):
	def test_traceback_sanitzation(self):
		try:
			password = "42"  # noqa: F841
			args = {"password": "42", "pwd": "42", "safe": "safe_value"}
			args = frappe._dict({"password": "42", "pwd": "42", "safe": "safe_value"})  # noqa: F841
			raise Exception
		except Exception:
			traceback = frappe.get_traceback(with_context=True)
			self.assertNotIn("42", traceback)
			self.assertIn("********", traceback)
			self.assertIn("password =", traceback)
			self.assertIn("safe_value", traceback)


class TestRounding(IntegrationTestCase):
	@IntegrationTestCase.change_settings("System Settings", {"rounding_method": "Commercial Rounding"})
	def test_normal_rounding(self):
		self.assertEqual(flt("what"), 0)

		self.assertEqual(flt("0.5", 0), 1)
		self.assertEqual(flt("0.3"), 0.3)

		self.assertEqual(flt("1.5", 0), 2)

		# positive rounding to integers
		self.assertEqual(flt(0.4, 0), 0)
		self.assertEqual(flt(0.5, 0), 1)
		self.assertEqual(flt(1.455, 0), 1)
		self.assertEqual(flt(1.5, 0), 2)

		# negative rounding to integers
		self.assertEqual(flt(-0.5, 0), -1)
		self.assertEqual(flt(-1.5, 0), -2)

		# negative precision i.e. round to nearest 10th
		self.assertEqual(flt(123, -1), 120)
		self.assertEqual(flt(125, -1), 130)
		self.assertEqual(flt(134.45, -1), 130)
		self.assertEqual(flt(135, -1), 140)

		# positive multiple digit rounding
		self.assertEqual(flt(1.25, 1), 1.3)
		self.assertEqual(flt(0.15, 1), 0.2)

		# negative multiple digit rounding
		self.assertEqual(flt(-1.25, 1), -1.3)
		self.assertEqual(flt(-0.15, 1), -0.2)

	def test_normal_rounding_as_argument(self):
		rounding_method = "Commercial Rounding"

		self.assertEqual(flt("0.5", 0, rounding_method=rounding_method), 1)
		self.assertEqual(flt("0.3", rounding_method=rounding_method), 0.3)

		self.assertEqual(flt("1.5", 0, rounding_method=rounding_method), 2)

		# positive rounding to integers
		self.assertEqual(flt(0.4, 0, rounding_method=rounding_method), 0)
		self.assertEqual(flt(0.5, 0, rounding_method=rounding_method), 1)
		self.assertEqual(flt(1.455, 0, rounding_method=rounding_method), 1)
		self.assertEqual(flt(1.5, 0, rounding_method=rounding_method), 2)

		# negative rounding to integers
		self.assertEqual(flt(-0.5, 0, rounding_method=rounding_method), -1)
		self.assertEqual(flt(-1.5, 0, rounding_method=rounding_method), -2)

		# negative precision i.e. round to nearest 10th
		self.assertEqual(flt(123, -1, rounding_method=rounding_method), 120)
		self.assertEqual(flt(125, -1, rounding_method=rounding_method), 130)
		self.assertEqual(flt(134.45, -1, rounding_method=rounding_method), 130)
		self.assertEqual(flt(135, -1, rounding_method=rounding_method), 140)

		# positive multiple digit rounding
		self.assertEqual(flt(1.25, 1, rounding_method=rounding_method), 1.3)
		self.assertEqual(flt(0.15, 1, rounding_method=rounding_method), 0.2)
		self.assertEqual(flt(2.675, 2, rounding_method=rounding_method), 2.68)

		# negative multiple digit rounding
		self.assertEqual(flt(-1.25, 1, rounding_method=rounding_method), -1.3)
		self.assertEqual(flt(-0.15, 1, rounding_method=rounding_method), -0.2)

		# Nearest number and not even (the default behaviour)
		self.assertEqual(flt(0.5, 0, rounding_method=rounding_method), 1)
		self.assertEqual(flt(1.5, 0, rounding_method=rounding_method), 2)
		self.assertEqual(flt(2.5, 0, rounding_method=rounding_method), 3)
		self.assertEqual(flt(3.5, 0, rounding_method=rounding_method), 4)

		self.assertEqual(flt(0.05, 1, rounding_method=rounding_method), 0.1)
		self.assertEqual(flt(1.15, 1, rounding_method=rounding_method), 1.2)
		self.assertEqual(flt(2.25, 1, rounding_method=rounding_method), 2.3)
		self.assertEqual(flt(3.35, 1, rounding_method=rounding_method), 3.4)

	@IntegrationTestCase.change_settings("System Settings", {"rounding_method": "Commercial Rounding"})
	@given(
		st.decimals(min_value=-1e8, max_value=1e8),
		st.integers(min_value=-2, max_value=4),
	)
	def test_normal_rounding_property(self, number, precision):
		with localcontext() as ctx:
			ctx.rounding = ROUND_HALF_UP
			self.assertEqual(Decimal(str(flt(float(number), precision))), round(number, precision))

	def test_bankers_rounding(self):
		rounding_method = "Banker's Rounding"

		self.assertEqual(rounded(0, 0, rounding_method=rounding_method), 0)
		self.assertEqual(rounded(5.551115123125783e-17, 2, rounding_method=rounding_method), 0.0)

		self.assertEqual(flt("0.5", 0, rounding_method=rounding_method), 0)
		self.assertEqual(flt("0.3", rounding_method=rounding_method), 0.3)

		self.assertEqual(flt("1.5", 0, rounding_method=rounding_method), 2)

		# positive rounding to integers
		self.assertEqual(flt(0.4, 0, rounding_method=rounding_method), 0)
		self.assertEqual(flt(0.5, 0, rounding_method=rounding_method), 0)
		self.assertEqual(flt(1.455, 0, rounding_method=rounding_method), 1)
		self.assertEqual(flt(1.5, 0, rounding_method=rounding_method), 2)

		# negative rounding to integers
		self.assertEqual(flt(-0.5, 0, rounding_method=rounding_method), 0)
		self.assertEqual(flt(-1.5, 0, rounding_method=rounding_method), -2)

		# negative precision i.e. round to nearest 10th
		self.assertEqual(flt(123, -1, rounding_method=rounding_method), 120)
		self.assertEqual(flt(125, -1, rounding_method=rounding_method), 120)
		self.assertEqual(flt(134.45, -1, rounding_method=rounding_method), 130)
		self.assertEqual(flt(135, -1, rounding_method=rounding_method), 140)

		# positive multiple digit rounding
		self.assertEqual(flt(1.25, 1, rounding_method=rounding_method), 1.2)
		self.assertEqual(flt(0.15, 1, rounding_method=rounding_method), 0.2)
		self.assertEqual(flt(2.675, 2, rounding_method=rounding_method), 2.68)
		self.assertEqual(flt(-2.675, 2, rounding_method=rounding_method), -2.68)

		# negative multiple digit rounding
		self.assertEqual(flt(-1.25, 1, rounding_method=rounding_method), -1.2)
		self.assertEqual(flt(-0.15, 1, rounding_method=rounding_method), -0.2)

		# Nearest number and not even (the default behaviour)
		self.assertEqual(flt(0.5, 0, rounding_method=rounding_method), 0)
		self.assertEqual(flt(1.5, 0, rounding_method=rounding_method), 2)
		self.assertEqual(flt(2.5, 0, rounding_method=rounding_method), 2)
		self.assertEqual(flt(3.5, 0, rounding_method=rounding_method), 4)

		self.assertEqual(flt(0.05, 1, rounding_method=rounding_method), 0.0)
		self.assertEqual(flt(1.15, 1, rounding_method=rounding_method), 1.2)
		self.assertEqual(flt(2.25, 1, rounding_method=rounding_method), 2.2)
		self.assertEqual(flt(3.35, 1, rounding_method=rounding_method), 3.4)

		self.assertEqual(flt(-0.5, 0, rounding_method=rounding_method), 0)
		self.assertEqual(flt(-1.5, 0, rounding_method=rounding_method), -2)
		self.assertEqual(flt(-2.5, 0, rounding_method=rounding_method), -2)
		self.assertEqual(flt(-3.5, 0, rounding_method=rounding_method), -4)

		self.assertEqual(flt(-0.05, 1, rounding_method=rounding_method), 0.0)
		self.assertEqual(flt(-1.15, 1, rounding_method=rounding_method), -1.2)
		self.assertEqual(flt(-2.25, 1, rounding_method=rounding_method), -2.2)
		self.assertEqual(flt(-3.35, 1, rounding_method=rounding_method), -3.4)

	@IntegrationTestCase.change_settings("System Settings", {"rounding_method": "Banker's Rounding"})
	@given(
		st.decimals(min_value=-1e8, max_value=1e8),
		st.integers(min_value=-2, max_value=4),
	)
	def test_bankers_rounding_property(self, number, precision):
		self.assertEqual(Decimal(str(flt(float(number), precision))), round(number, precision))

	def test_default_rounding(self):
		self.assertEqual(frappe.get_system_settings("rounding_method"), "Banker's Rounding")

	@given(
		st.floats(min_value=-(2**32) - 1, max_value=2**32 + 1),
		st.integers(min_value=-(2**63) - 1, max_value=2**63 + 1),
	)
	def test_cint(self, floating_point, integer):
		self.assertEqual(cint(integer), integer)
		self.assertEqual(cint(str(integer)), integer)
		self.assertEqual(cint(str(floating_point)), int(floating_point))


class TestArgumentTypingValidations(IntegrationTestCase):
	def test_validate_argument_types(self):
		from unittest.mock import AsyncMock, MagicMock, Mock

		from frappe.core.doctype.doctype.doctype import DocType
		from frappe.utils.typing_validations import (
			FrappeTypeError,
			validate_argument_types,
		)

		@validate_argument_types
		def test_simple_types(a: int, b: float, c: bool):
			return a, b, c

		@validate_argument_types
		def test_sequence(a: str, b: list[dict] | None = None, c: dict[str, int] | None = None):
			return a, b, c

		@validate_argument_types
		def test_doctypes(a: DocType | dict):
			return a

		@validate_argument_types
		def test_mocks(a: str):
			return a

		self.assertEqual(test_simple_types(True, 2.0, True), (1, 2.0, True))
		self.assertEqual(test_simple_types(1, 2, 1), (1, 2.0, True))
		self.assertEqual(test_simple_types(1.0, 2, 1), (1, 2.0, True))
		self.assertEqual(test_simple_types(1, 2, "1"), (1, 2.0, True))
		with self.assertRaises(FrappeTypeError):
			test_simple_types(1, 2, "a")
		with self.assertRaises(FrappeTypeError):
			test_simple_types(1, 2, None)

		self.assertEqual(test_sequence("a", [{"a": 1}], {"a": 1}), ("a", [{"a": 1}], {"a": 1}))
		self.assertEqual(test_sequence("a", None, None), ("a", None, None))
		self.assertEqual(test_sequence("a", [{"a": 1}], None), ("a", [{"a": 1}], None))
		self.assertEqual(test_sequence("a", None, {"a": 1}), ("a", None, {"a": 1}))
		self.assertEqual(test_sequence("a", [{"a": 1}], {"a": "1.0"}), ("a", [{"a": 1}], {"a": 1}))
		with self.assertRaises(FrappeTypeError):
			test_sequence("a", [{"a": 1}], True)

		doctype = frappe.get_last_doc("DocType")
		self.assertEqual(test_doctypes(doctype), doctype)
		self.assertEqual(test_doctypes(doctype.as_dict()), doctype.as_dict())
		with self.assertRaises(FrappeTypeError):
			test_doctypes("a")

		self.assertEqual(test_mocks("Hello World"), "Hello World")
		for obj in (AsyncMock, MagicMock, Mock):
			obj_instance = obj()
			self.assertEqual(test_mocks(obj_instance), obj_instance)
		with self.assertRaises(FrappeTypeError):
			test_mocks(1)


class TestChangeLog(IntegrationTestCase):
	def test_get_remote_url(self):
		self.assertIsInstance(get_source_url("frappe"), str)

	def test_parse_github_url(self):
		# using erpnext as repo in order to be different from the owner
		owner, repo = parse_github_url("https://github.com/frappe/erpnext.git")
		self.assertEqual(owner, "frappe")
		self.assertEqual(repo, "erpnext")

		owner, repo = parse_github_url("https://github.com/frappe/erpnext")
		self.assertEqual(owner, "frappe")
		self.assertEqual(repo, "erpnext")

		owner, repo = parse_github_url("git@github.com:frappe/erpnext.git")
		self.assertEqual(owner, "frappe")
		self.assertEqual(repo, "erpnext")

		owner, repo = parse_github_url("https://gitlab.com/gitlab-org/gitlab")
		self.assertIsNone(owner)
		self.assertIsNone(repo)

		self.assertRaises(ValueError, parse_github_url, remote_url=None)


class TestCrypto(IntegrationTestCase):
	def test_hashing(self):
		self.assertEqual(sha256_hash(""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
		self.assertEqual(
			sha256_hash(b"The quick brown fox jumps over the lazy dog"),
			"d7a8fbb307d7809469ca9abcb0082e4f8d5651e46d3cdb762d02d0bf37c9e592",
		)


class TestURLTrackers(IntegrationTestCase):
	def test_add_trackers_to_url(self):
		url = "https://example.com"
		source = "test_source"
		campaign = "test_campaign"
		medium = "test_medium"
		content = "test_content"

		with patch("frappe.db.get_value") as mock_get_value:
			mock_get_value.side_effect = lambda *args: args[1]  # Return unslugged input value
			result = add_trackers_to_url(url, source, campaign, medium, content)

		expected = "https://example.com?utm_source=test_source&utm_medium=test_medium&utm_campaign=test_campaign&utm_content=test_content"
		self.assertEqual(result, expected)

	def test_parse_and_map_trackers_from_url(self):
		url = "https://example.com?utm_source=test_source&utm_medium=test_medium&utm_campaign=test_campaign&utm_content=test_content"

		with patch("frappe.db.get_value") as mock_get_value:
			mock_get_value.return_value = None  # Simulate no existing records
			result = parse_and_map_trackers_from_url(url)

		expected = {
			"utm_source": "test_source",
			"utm_medium": "test_medium",
			"utm_campaign": "test_campaign",
			"utm_content": "test_content",
		}
		self.assertEqual(result, expected)

	def test_map_trackers(self):
		url_trackers = {
			"utm_source": "test_source",
			"utm_medium": "test_medium",
			"utm_campaign": "test_campaign",
			"utm_content": "test_content",
		}

		result = map_trackers(url_trackers, create=True)

		expected = {
			"utm_source": frappe.get_doc("UTM Source", "test_source"),
			"utm_medium": frappe.get_doc("UTM Medium", "test_medium"),
			"utm_campaign": frappe.get_doc("UTM Campaign", "test_campaign"),
			"utm_content": "test_content",
		}
		self.assertDocumentEqual(result["utm_source"], expected["utm_source"])
		self.assertDocumentEqual(result["utm_medium"], expected["utm_medium"])
		self.assertDocumentEqual(result["utm_campaign"], expected["utm_campaign"])
		self.assertEqual(result["utm_content"], expected["utm_content"])
