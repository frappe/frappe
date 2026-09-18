# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import base64
import os
import time

# imports - third party imports
import requests

# imports - module imports
import frappe
from frappe.core.doctype.access_log.access_log import make_access_log
from frappe.core.doctype.data_import.data_import import export_csv
from frappe.core.doctype.user.user import generate_keys
from frappe.deferred_insert import save_to_db as flush_deferred_inserts

# imports - standard imports
from frappe.tests import IntegrationTestCase
from frappe.tests.utils.test_capabilities import TestService, requires_test_service
from frappe.utils import cstr, get_site_url


class TestAccessLog(IntegrationTestCase):
	@staticmethod
	def _start_fresh_database_write():
		frappe.db.rollback()
		if frappe.db.db_type == "sqlite":
			# Make the first operation a write so SQLite can wait for its single
			# writer slot before later validation reads create a stale snapshot.
			frappe.db.sql("DELETE FROM `tabAccess Log` WHERE 1 = 0")

	@classmethod
	def _flush_deferred_access_logs(cls):
		cls._start_fresh_database_write()
		flush_deferred_inserts(doctype="Access Log")
		# Publish records drained from Redis before polling from a fresh snapshot.
		frappe.db.commit()  # nosemgrep

	@classmethod
	def _wait_for_access_log(cls, filters, timeout=5):
		deadline = time.monotonic() + timeout
		while True:
			# The web request's after-response callback can enqueue the log just
			# after the client receives the response. Drain Redis on every retry so
			# tests without a worker cannot miss that late item.
			cls._flush_deferred_access_logs()
			# Start each lookup in a fresh transaction so commits from a worker (if
			# one is running) become visible too.
			frappe.db.rollback()
			if access_log_name := frappe.db.exists("Access Log", filters):
				return access_log_name
			if time.monotonic() >= deadline:
				return None
			time.sleep(0.1)

	def setUp(self):
		# generate keys for current user to send requests for the following tests
		generate_keys(frappe.session.user)
		# The external web process must be able to read these API credentials.
		frappe.db.commit()  # nosemgrep
		generated_secret = frappe.utils.password.get_decrypted_password(
			"User", frappe.session.user, fieldname="api_secret"
		)
		api_key = frappe.db.get_value("User", "Administrator", "api_key")
		self.header = {"Authorization": f"token {api_key}:{generated_secret}"}

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
			"project": [],
		}

		self.test_doctype = "File"
		self.test_document = "Test Document"
		self.test_report_name = "General Ledger"
		self.test_file_type = "CSV"
		self.test_method = "Test Method"
		self.file_name = frappe.utils.random_string(10) + ".txt"
		self.test_content = frappe.utils.random_string(1024)

	def test_make_full_access_log(self):
		self.maxDiff = None

		# test if all fields maintain data: html page and filters are converted?
		make_access_log(
			doctype=self.test_doctype,
			document=self.test_document,
			report_name=self.test_report_name,
			page=self.test_html_template,
			file_type=self.test_file_type,
			method=self.test_method,
			filters=self.test_filters,
		)

		last_doc = frappe.get_last_doc("Access Log")
		self.assertEqual(last_doc.filters, cstr(self.test_filters))
		self.assertEqual(self.test_doctype, last_doc.export_from)
		self.assertEqual(self.test_document, last_doc.reference_document)

	def test_make_export_log(self):
		# export data and delete temp file generated on disk
		export_csv(self.test_doctype, self.file_name)
		os.remove(self.file_name)

		# test if the exported data is logged
		last_doc = frappe.get_last_doc("Access Log")
		self.assertEqual(self.test_doctype, last_doc.export_from)

	@requires_test_service(TestService.WEB_SERVER)
	def test_private_file_download(self):
		# create new private file
		new_private_file = frappe.get_doc(
			{
				"doctype": self.test_doctype,
				"file_name": self.file_name,
				"content": base64.b64encode(self.test_content.encode("utf-8")),
				"is_private": 1,
			}
		)
		new_private_file.insert()
		# The web server has a separate database connection and can only see a
		# committed fixture. Committing also releases SQLite's writer lock.
		frappe.db.commit()  # nosemgrep
		access_log_filters = {
			"export_from": new_private_file.doctype,
			"reference_document": new_private_file.name,
		}

		try:
			with requests.post(
				get_site_url(frappe.local.site) + new_private_file.file_url,
				headers=self.header,
				timeout=30,
			) as response:
				self.assertTrue(response.ok)

			access_log_name = self._wait_for_access_log(access_log_filters)
			self.assertTrue(access_log_name)
			access_log = frappe.get_doc("Access Log", access_log_name)
			self.assertEqual(new_private_file.doctype, access_log.export_from)
			self.assertEqual(new_private_file.name, access_log.reference_document)
		finally:
			try:
				# Drain an item queued before a request or assertion failed.
				self._flush_deferred_access_logs()
			finally:
				self._start_fresh_database_write()
				frappe.db.delete("Access Log", access_log_filters)
				new_private_file.delete()
				# This fixture was published for the web process, so persist its cleanup too.
				frappe.db.commit()  # nosemgrep

	def tearDown(self):
		pass
