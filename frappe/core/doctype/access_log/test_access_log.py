# Copyright (c) 2019, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import base64
import os
import time

# imports - third party imports
import requests

# imports - module imports
import frappe
from frappe.core.doctype.access_log.access_log import AccessLog, make_access_log
from frappe.core.doctype.data_import.data_import import export_csv
from frappe.core.doctype.user.user import generate_keys
from frappe.deferred_insert import save_to_db as flush_deferred_inserts

# imports - standard imports
from frappe.tests import IntegrationTestCase
from frappe.tests.utils.test_capabilities import TestService, requires_test_service
from frappe.utils import cstr, get_site_url
from frappe.utils.logging import ensure_log_table, get_log_db, is_log_doctype


class TestAccessLog(IntegrationTestCase):
	@staticmethod
	def _start_fresh_database_write():
		frappe.db.rollback()

	@classmethod
	def _flush_deferred_access_logs(cls):
		cls._start_fresh_database_write()
		flush_deferred_inserts(doctype="Access Log")

	@classmethod
	def _wait_for_access_log(cls, filters, timeout=5):
		"""Poll the log database until the Access Log for `filters` shows up.

		Access Log rows live in the site's SQLite log database, so the lookup goes to that
		connection -- `frappe.db.exists` would ask the primary database, which holds no table
		for a virtual DocType. The log connection commits every write as it happens, so a row
		written by another process is visible without a transaction boundary here.
		"""
		ensure_log_table("Access Log")
		deadline = time.monotonic() + timeout
		while True:
			# The web request's after-response callback can enqueue the log just
			# after the client receives the response. Drain Redis on every retry so
			# tests without a worker cannot miss that late item.
			cls._flush_deferred_access_logs()
			if access_log_name := get_log_db().exists("Access Log", filters):
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

	def test_logs_are_stored_in_the_log_database(self):
		ensure_log_table("Access Log")
		log_db = get_log_db()
		self.assertTrue(is_log_doctype("Access Log"))
		self.assertTrue(frappe.get_meta("Access Log").is_virtual)

		before = log_db.count("Access Log")
		make_access_log(doctype=self.test_doctype, document=self.test_document)
		self._flush_deferred_access_logs()

		self.assertEqual(log_db.count("Access Log"), before + 1)

		name = frappe.get_last_doc("Access Log").name
		self.addCleanup(self._delete_log, name)
		self.assertEqual(log_db.get_value("Access Log", name, "export_from"), self.test_doctype)

		# `db_insert` has to stamp these itself: `make_access_log` calls it directly rather than
		# going through `insert`, and a NULL `creation` would hide the row from retention.
		row = log_db.get_value("Access Log", name, ["creation", "owner"], as_dict=True)
		self.assertTrue(row.creation)
		self.assertEqual(row.owner, frappe.session.user)

	def test_list_and_count_read_the_log_database(self):
		ensure_log_table("Access Log")
		make_access_log(doctype=self.test_doctype, document=self.test_document)
		self._flush_deferred_access_logs()

		name = frappe.get_last_doc("Access Log").name
		self.addCleanup(self._delete_log, name)

		listed = frappe.get_all("Access Log", filters={"name": name}, fields=["name", "export_from"])
		self.assertEqual(len(listed), 1)
		self.assertEqual(listed[0].export_from, self.test_doctype)
		self.assertEqual(
			frappe.get_all("Access Log", filters={"name": name}, pluck="export_from"), [self.test_doctype]
		)

		# The User form's "Logs" dashboard badge counts through this path.
		from frappe.desk.notifications import get_doc_count

		self.assertGreaterEqual(get_doc_count("Access Log", {"user": frappe.session.user}), 1)

	def test_track_seen_is_recorded_in_the_log_database(self):
		"""`track_seen` is declared on this DocType, so opening the form must record the reader.

		`Document.add_seen` writes `_seen` through `frappe.db.set_value`, which would target the
		primary database -- where this DocType has no table at all.
		"""
		ensure_log_table("Access Log")
		log_db = get_log_db()
		make_access_log(doctype=self.test_doctype, document=self.test_document)
		self._flush_deferred_access_logs()

		name = frappe.get_last_doc("Access Log").name
		self.addCleanup(self._delete_log, name)

		doc = frappe.get_doc("Access Log", name)
		doc.add_seen("Administrator")
		self.assertEqual(frappe.parse_json(log_db.get_value("Access Log", name, "_seen")), ["Administrator"])

		# a second reader is appended, and the same reader is not recorded twice
		doc = frappe.get_doc("Access Log", name)
		doc.add_seen("Guest")
		doc.add_seen("Guest")
		self.assertEqual(
			frappe.parse_json(log_db.get_value("Access Log", name, "_seen")), ["Administrator", "Guest"]
		)

	def test_clear_old_logs(self):
		ensure_log_table("Access Log")
		log_db = get_log_db()
		make_access_log(doctype=self.test_doctype, document=self.test_document)
		self._flush_deferred_access_logs()

		name = frappe.get_last_doc("Access Log").name
		self.addCleanup(self._delete_log, name)
		log_db.sql(
			"UPDATE `tabAccess Log` SET creation = %(creation)s WHERE name = %(name)s",
			{"creation": "2020-01-01 00:00:00.000000", "name": name},
		)
		log_db.commit()

		AccessLog.clear_old_logs(days=30)

		self.assertFalse(log_db.exists("Access Log", name))

	def test_hash_collision_is_retried(self):
		"""Access Log is named by hash, so a collision has to get a fresh name, not an error."""
		ensure_log_table("Access Log")
		log_db = get_log_db()

		first = frappe.get_doc({"doctype": "Access Log", "user": frappe.session.user})
		first.db_insert()
		self.addCleanup(self._delete_log, first.name)

		clash = frappe.get_doc({"doctype": "Access Log", "user": frappe.session.user})
		clash.name = first.name
		clash.db_insert()
		self.addCleanup(self._delete_log, clash.name)

		self.assertNotEqual(clash.name, first.name)
		self.assertTrue(log_db.exists("Access Log", clash.name))

	@staticmethod
	def _delete_log(name):
		log_db = get_log_db()
		log_db.delete("Access Log", {"name": name})
		log_db.commit()

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
				log_db = get_log_db()
				log_db.delete("Access Log", access_log_filters)
				log_db.commit()
				new_private_file.delete()
				# This fixture was published for the web process, so persist its cleanup too.
				frappe.db.commit()  # nosemgrep

	def tearDown(self):
		pass
