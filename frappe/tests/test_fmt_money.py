# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import flt, cstr, fmt_money, number_format_to_float
import unittest

test_amount = (1, 10 , 100, 1000, 10000, 100000, 1000000, 10000000, 100000000, 1000000000)
formatted_amount = {
	"#,###.##": 	["1.00", "10.00", "100.00", "1,000.00", "10,000.00", "100,000.00", "1,000,000.00",
						"10,000,000.00", "100,000,000.00", "1,000,000,000.00"],
	"#,##,###.##": 	["1.00", "10.00", "100.00", "1,000.00", "10,000.00", "1,00,000.00", "10,00,000.00",
						"1,00,00,000.00", "10,00,00,000.00", "1,00,00,00,000.00"],
	"#.###,##": 	["-1,00", "-10,00", "-100,00", "-1.000,00", "-10.000,00", "-100.000,00", "-1.000.000,00",
						"-10.000.000,00", "-100.000.000,00", "-1.000.000.000,00"],
	"#,###":		["1", "10", "100", "1,000", "10,000", "100,000", "1,000,000", "10,000,000",
						"100,000,000", "1,000,000,000"],
	"#'###.##":		["1.0000", "10.0000", "100.0000", "1'000.0000", "10'000.0000", "100'000.0000",
						"1'000'000.0000", "10'000'000.0000", "100'000'000.0000", "1'000'000'000.0000"]
}

class TestFmtMoney(unittest.TestCase):
	def test_number_format_conversion(self):
		for number_format in formatted_amount.keys():
			frappe.db.set_default("number_format", number_format)
			if number_format == "#'###.##":
				frappe.db.set_default("currency_precision", "4")
			else:
				frappe.db.set_default("currency_precision", "")

			for i in xrange(10):
				if number_format == "#.###,##":
					amount = -test_amount[i]
				elif number_format == "#,###":
					amount = test_amount[i]+0.3
				else:
					amount = test_amount[i]
				fmtd_amount = fmt_money(amount)
				self.assertEquals(fmtd_amount, formatted_amount[number_format][i])
				if number_format != "#,###":
					self.assertEquals(number_format_to_float(fmtd_amount, number_format), amount)

			frappe.db.set_default("currency_precision", "")

if __name__=="__main__":
	frappe.connect()
	unittest.main()