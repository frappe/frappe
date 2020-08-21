#  -*- coding: utf-8 -*-

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe

class TestData(unittest.TestCase):
	def test_rounded_using_flt(self):
		# Test if rounding result is on par with mysql rounding
		# using Round Halfs to nearest Even
		from frappe.utils import flt

		dataset = [(34.5, 0), (-34.5, 0),
			(3.45, 1), (-3.45, 1),
			(0.345, 2), (-0.345, 2),
			(0.0345, 3), (-0.0345, 3)]

		for data in dataset:
			py_rounding = flt(data[0], data[1])
			db_rounding = frappe.db.sql("""select ROUND(CONVERT({0}, DOUBLE),{1})""".format(data[0], data[1]))[0][0]
			self.assertEqual(py_rounding, db_rounding)
