# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import datetime
import unittest

import frappe
from frappe.utils import (
	format_datetime,
	format_time,
	formatdate,
	get_datetime,
	get_time,
	get_user_date_format,
	get_user_time_format,
	getdate,
)

test_date_obj = datetime.datetime.now()
test_date = test_date_obj.strftime("%Y-%m-%d")
test_time = test_date_obj.strftime("%H:%M:%S.%f")
test_datetime = test_date_obj.strftime("%Y-%m-%d %H:%M:%S.%f")
test_date_formats = {
	"yyyy-mm-dd": test_date_obj.strftime("%Y-%m-%d"),
	"dd-mm-yyyy": test_date_obj.strftime("%d-%m-%Y"),
	"dd/mm/yyyy": test_date_obj.strftime("%d/%m/%Y"),
	"dd.mm.yyyy": test_date_obj.strftime("%d.%m.%Y"),
	"mm/dd/yyyy": test_date_obj.strftime("%m/%d/%Y"),
	"mm-dd-yyyy": test_date_obj.strftime("%m-%d-%Y"),
}
test_time_formats = {
	"HH:mm:ss": test_date_obj.strftime("%H:%M:%S"),
	"HH:mm": test_date_obj.strftime("%H:%M"),
}


class TestFmtDatetime(unittest.TestCase):
	"""Tests date, time and datetime formatters and some associated
	utility functions. These rely on the system-wide date and time
	formats.
	"""

	# Set up and tidy up routines

	def setUp(self):
		# create test domain
		self.pre_test_date_format = frappe.db.get_default("date_format")
		self.pre_test_time_format = frappe.db.get_default("time_format")

	def tearDown(self):
		frappe.db.set_default("date_format", self.pre_test_date_format)
		frappe.db.set_default("time_format", self.pre_test_time_format)
		frappe.local.user_date_format = None
		frappe.local.user_time_format = None
		frappe.db.rollback()

	# Test utility functions

	def test_set_default_date_format(self):
		frappe.db.set_default("date_format", "ZYX321")
		self.assertEqual(frappe.db.get_default("date_format"), "ZYX321")

	def test_set_default_time_format(self):
		frappe.db.set_default("time_format", "XYZ123")
		self.assertEqual(frappe.db.get_default("time_format"), "XYZ123")

	def test_get_functions(self):
		# Test round-trip through getdate, get_datetime and get_time
		self.assertEqual(test_date_obj, get_datetime(test_datetime))
		self.assertEqual(test_date_obj.date(), getdate(test_date))
		self.assertEqual(test_date_obj.time(), get_time(test_time))

	# Test date formatters

	def test_formatdate_forced(self):
		# Test with forced date formats
		self.assertEqual(formatdate(test_date, "dd-yyyy-mm"), test_date_obj.strftime("%d-%Y-%m"))
		self.assertEqual(formatdate(test_date, "dd-yyyy-MM"), test_date_obj.strftime("%d-%Y-%m"))

	def test_formatdate_forced_broken_locale(self):
		# Test with forced date formats
		lang = frappe.local.lang
		# Force fallback from Babel
		try:
			frappe.local.lang = "FAKE"
			self.assertEqual(formatdate(test_date, "dd-yyyy-mm"), test_date_obj.strftime("%d-%Y-%m"))
			self.assertEqual(formatdate(test_date, "dd-yyyy-MM"), test_date_obj.strftime("%d-%Y-%m"))
		finally:
			frappe.local.lang = lang

	def test_format_date(self):
		# Test formatdate with various default date formats set
		for fmt, valid_fmt in test_date_formats.items():
			frappe.db.set_default("date_format", fmt)
			frappe.local.user_date_format = None
			self.assertEqual(get_user_date_format(), fmt)
			self.assertEqual(formatdate(test_date), valid_fmt)

	# Test time formatters
	def test_format_time_forced(self):
		# Test with forced time formats
		self.assertEqual(format_time(test_time, "ss:mm:HH"), test_date_obj.strftime("%S:%M:%H"))

	def test_format_time(self):
		# Test format_time with various default time formats set
		for fmt, valid_fmt in test_time_formats.items():
			frappe.db.set_default("time_format", fmt)
			frappe.local.user_time_format = None
			self.assertEqual(get_user_time_format(), fmt)
			self.assertEqual(format_time(test_time), valid_fmt)

	# Test datetime formatters

	def test_format_datetime_forced(self):
		# Test with forced date formats
		self.assertEqual(
			format_datetime(test_datetime, "dd-yyyy-MM ss:mm:HH"),
			test_date_obj.strftime("%d-%Y-%m %S:%M:%H"),
		)

	def test_format_datetime(self):
		# Test formatdate with various default date formats set
		for date_fmt, valid_date in test_date_formats.items():
			frappe.db.set_default("date_format", date_fmt)
			frappe.local.user_date_format = None
			for time_fmt, valid_time in test_time_formats.items():
				frappe.db.set_default("time_format", time_fmt)
				frappe.local.user_time_format = None
				valid_fmt = valid_date + " " + valid_time
				self.assertEqual(format_datetime(test_datetime), valid_fmt)
