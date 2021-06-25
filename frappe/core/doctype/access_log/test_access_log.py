# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and Contributors
# See license.txt

# imports - standard imports
import unittest
import base64
import os

# imports - module imports
import frappe
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.utils import cstr, get_site_url
from frappe.core.doctype.data_import.data_import import export_csv
from frappe.core.doctype.user.user import generate_keys

# imports - third party imports
import requests


class TestAccessLog(unittest.TestCase):
	def setUp(self):
		# generate keys for current user to send requests for the following tests
		generate_keys(frappe.session.user)
		frappe.db.commit()
		generated_secret = frappe.utils.password.get_decrypted_password("User",
			frappe.session.user, fieldname='api_secret')
		api_key = frappe.db.get_value("User", "Administrator", "api_key")
		self.header = {"Authorization": "token {}:{}".format(api_key, generated_secret)}

		self.test_html_template = """
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
		self.test_filters = {
			"from_date": "2019-06-30",
			"to_date": "2019-07-31",
			"party": [],
			"group_by": "Group by Voucher (Consolidated)",
			"cost_center": [],
			"project": []
		}

		self.test_doctype = 'File'
		self.test_document = 'Test Document'
		self.test_report_name = 'General Ledger'
		self.test_file_type = 'CSV'
		self.test_method = 'Test Method'
		self.file_name = frappe.utils.random_string(10) + '.txt'
		self.test_content = frappe.utils.random_string(1024)


	def test_make_full_access_log(self):
		self.maxDiff = None

		# test if all fields maintain data: html page and filters are converted?
		make_access_log(doctype=self.test_doctype,
			document=self.test_document,
			report_name=self.test_report_name,
			page=self.test_html_template,
			file_type=self.test_file_type,
			method=self.test_method,
			filters=self.test_filters)

		last_doc = frappe.get_last_doc('Access Log')
		self.assertEqual(last_doc.filters, cstr(self.test_filters))
		self.assertEqual(self.test_doctype, last_doc.export_from)
		self.assertEqual(self.test_document, last_doc.reference_document)


	def test_make_export_log(self):
		# export data and delete temp file generated on disk
		export_csv(self.test_doctype, self.file_name)
		os.remove(self.file_name)

		# test if the exported data is logged
		last_doc = frappe.get_last_doc('Access Log')
		self.assertEqual(self.test_doctype, last_doc.export_from)


	def test_private_file_download(self):
		# create new private file
		new_private_file = frappe.get_doc({
			'doctype': self.test_doctype,
			'file_name': self.file_name,
			'content': base64.b64encode(self.test_content.encode('utf-8')),
			'is_private': 1,
		})
		new_private_file.insert()

		# access the created file
		private_file_link = get_site_url(frappe.local.site) + new_private_file.file_url

		try:
			request = requests.post(private_file_link, headers=self.header)
			last_doc = frappe.get_last_doc('Access Log')

			if request.ok:
				# check for the access log of downloaded file
				self.assertEqual(new_private_file.doctype, last_doc.export_from)
				self.assertEqual(new_private_file.name, last_doc.reference_document)

		except requests.ConnectionError:
			pass

		# cleanup
		new_private_file.delete()


	def tearDown(self):
		pass
