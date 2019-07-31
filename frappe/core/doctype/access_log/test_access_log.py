# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

# import frappe
import unittest
from frappe.core.doctype.access_log.access_log import make_access_log


class TestAccessLog(unittest.TestCase):
    def test_make_backup_download_log(self):
        self.assertTrue(make_access_log(backup=True))

    def test_make_pdf_log(self):
        html_temp = """
			<!DOCTYPE html>
			<html>
			<head>
			<style>
			table {
			font-family: arial, sans-serif;
			border-collapse: collapse;
			width: 100%;
			}

			td, th {
			border: 1px solid #dddddd;
			text-align: left;
			padding: 8px;
			}

			tr:nth-child(even) {
			background-color: #dddddd;
			}
			</style>
			</head>
			<body>

			<h2>HTML Table</h2>

			<table>
			<tr>
				<th>Company</th>
				<th>Contact</th>
				<th>Country</th>
			</tr>
			<tr>
				<td>Alfreds Futterkiste</td>
				<td>Maria Anders</td>
				<td>Germany</td>
			</tr>
			<tr>
				<td>Centro comercial Moctezuma</td>
				<td>Francisco Chang</td>
				<td>Mexico</td>
			</tr>
			<tr>
				<td>Ernst Handel</td>
				<td>Roland Mendel</td>
				<td>Austria</td>
			</tr>
			<tr>
				<td>Island Trading</td>
				<td>Helen Bennett</td>
				<td>UK</td>
			</tr>
			<tr>
				<td>Laughing Bacchus Winecellars</td>
				<td>Yoshi Tannamuri</td>
				<td>Canada</td>
			</tr>
			<tr>
				<td>Magazzini Alimentari Riuniti</td>
				<td>Giovanni Rovelli</td>
				<td>Italy</td>
			</tr>
			</table>

			</body>
			</html>
		"""
        self.assertTrue(make_access_log(doctype='Test DocType',
                                        document='Test Document', page=html_temp))

	def test_make_report_print_log(self):
		erpnext_fields = {"from_date": "2019-06-30", "to_date": "2019-07-31", "party": [],
							"group_by": "Group by Voucher (Consolidated)", "cost_center": [], "project": []}

		self.assertTrue(make_access_log(
			report_name='General Ledger', _filters=erpnext_fields))
