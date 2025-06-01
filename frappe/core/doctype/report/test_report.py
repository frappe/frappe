# Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import os
import textwrap

import nts
from nts.core.doctype.user_permission.test_user_permission import create_user
from nts.custom.doctype.customize_form.customize_form import reset_customization
from nts.desk.query_report import add_total_row, run, save_report
from nts.desk.reportview import delete_report
from nts.desk.reportview import save_report as _save_report
from nts.tests.utils import ntsTestCase

test_records = nts.get_test_records("Report")
test_dependencies = ["User"]


class TestReport(ntsTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		cls.enable_safe_exec()
		return super().setUpClass()

	def test_report_builder(self):
		if nts.db.exists("Report", "User Activity Report"):
			nts.delete_doc("Report", "User Activity Report")

		with open(os.path.join(os.path.dirname(__file__), "user_activity_report.json")) as f:
			nts.get_doc(json.loads(f.read())).insert()

		report = nts.get_doc("Report", "User Activity Report")
		columns, data = report.get_data()
		self.assertEqual(columns[0].get("label"), "ID")
		self.assertEqual(columns[1].get("label"), "User Type")
		self.assertTrue("Administrator" in [d[0] for d in data])

	def test_query_report(self):
		report = nts.get_doc("Report", "Permitted Documents For User")
		columns, data = report.get_data(filters={"user": "Administrator", "doctype": "DocType"})
		self.assertEqual(columns[0].get("label"), "Name")
		self.assertEqual(columns[1].get("label"), "Module")
		self.assertTrue("User" in [d.get("name") for d in data])

	def test_save_or_delete_report(self):
		"""Test for validations when editing / deleting report of type Report Builder"""

		try:
			report = nts.get_doc(
				{
					"doctype": "Report",
					"ref_doctype": "User",
					"report_name": "Test Delete Report",
					"report_type": "Report Builder",
					"is_standard": "No",
				}
			).insert()

			# Check for PermissionError
			create_user("test_report_owner@example.com", "Website Manager")
			nts.set_user("test_report_owner@example.com")
			self.assertRaises(nts.PermissionError, delete_report, report.name)

			# Check for Report Type
			nts.set_user("Administrator")
			report.db_set("report_type", "Custom Report")
			self.assertRaisesRegex(
				nts.ValidationError,
				"Only reports of type Report Builder can be deleted",
				delete_report,
				report.name,
			)

			# Check if creating and deleting works with proper validations
			nts.set_user("test@example.com")
			report_name = _save_report(
				"Dummy Report",
				"User",
				json.dumps(
					[
						{
							"fieldname": "email",
							"fieldtype": "Data",
							"label": "Email",
							"insert_after_index": 0,
							"link_field": "name",
							"doctype": "User",
							"options": "Email",
							"width": 100,
							"id": "email",
							"name": "Email",
						}
					]
				),
			)

			doc = nts.get_doc("Report", report_name)
			delete_report(doc.name)

		finally:
			nts.set_user("Administrator")
			nts.db.rollback()

	def test_custom_report(self):
		reset_customization("User")
		custom_report_name = save_report(
			"Permitted Documents For User",
			"Permitted Documents For User Custom",
			json.dumps(
				[
					{
						"fieldname": "email",
						"fieldtype": "Data",
						"label": "Email",
						"insert_after_index": 0,
						"link_field": "name",
						"doctype": "User",
						"options": "Email",
						"width": 100,
						"id": "email",
						"name": "Email",
					}
				]
			),
			json.dumps({"user": "Administrator", "doctype": "User"}),
		)
		custom_report = nts.get_doc("Report", custom_report_name)
		columns, result = custom_report.run_query_report(user=nts.session.user)

		self.assertListEqual(["email"], [column.get("fieldname") for column in columns])
		admin_dict = nts.core.utils.find(result, lambda d: d["name"] == "Administrator")
		self.assertDictEqual(
			{
				"name": "Administrator",
				"user_type": "System User",
				"email": "admin@example.com",
			},
			admin_dict,
		)

	def test_report_with_custom_column(self):
		reset_customization("User")
		response = run(
			"Permitted Documents For User",
			filters={"user": "Administrator", "doctype": "User"},
			custom_columns=[
				{
					"fieldname": "email",
					"fieldtype": "Data",
					"label": "Email",
					"insert_after_index": 0,
					"link_field": "name",
					"doctype": "User",
					"options": "Email",
					"width": 100,
					"id": "email",
					"name": "Email",
				}
			],
		)
		result = response.get("result")
		columns = response.get("columns")
		self.assertListEqual(
			["name", "email", "user_type"],
			[column.get("fieldname") for column in columns],
		)
		admin_dict = nts.core.utils.find(result, lambda d: d["name"] == "Administrator")
		self.assertDictEqual(
			{
				"name": "Administrator",
				"user_type": "System User",
				"email": "admin@example.com",
			},
			admin_dict,
		)

	def test_report_permissions(self):
		nts.set_user("test@example.com")
		nts.db.delete("Has Role", {"parent": nts.session.user, "role": "Test Has Role"})
		nts.db.commit()
		if not nts.db.exists("Role", "Test Has Role"):
			nts.get_doc({"doctype": "Role", "role_name": "Test Has Role"}).insert(ignore_permissions=True)

		if not nts.db.exists("Report", "Test Report"):
			report = nts.get_doc(
				{
					"doctype": "Report",
					"ref_doctype": "User",
					"report_name": "Test Report",
					"report_type": "Query Report",
					"is_standard": "No",
					"roles": [{"role": "Test Has Role"}],
				}
			).insert(ignore_permissions=True)
		else:
			report = nts.get_doc("Report", "Test Report")

		self.assertNotEqual(report.is_permitted(), True)
		nts.set_user("Administrator")

	def test_report_custom_permissions(self):
		nts.set_user("test@example.com")
		nts.db.delete("Custom Role", {"report": "Test Custom Role Report"})
		nts.db.commit()  # nosemgrep
		if not nts.db.exists("Report", "Test Custom Role Report"):
			report = nts.get_doc(
				{
					"doctype": "Report",
					"ref_doctype": "User",
					"report_name": "Test Custom Role Report",
					"report_type": "Query Report",
					"is_standard": "No",
					"roles": [{"role": "_Test Role"}, {"role": "System Manager"}],
				}
			).insert(ignore_permissions=True)
		else:
			report = nts.get_doc("Report", "Test Custom Role Report")

		self.assertEqual(report.is_permitted(), True)

		nts.get_doc(
			{
				"doctype": "Custom Role",
				"report": "Test Custom Role Report",
				"roles": [{"role": "_Test Role 2"}],
				"ref_doctype": "User",
			}
		).insert(ignore_permissions=True)

		self.assertNotEqual(report.is_permitted(), True)
		nts.set_user("Administrator")

	# test for the `_format` method if report data doesn't have sort_by parameter
	def test_format_method(self):
		if nts.db.exists("Report", "User Activity Report Without Sort"):
			nts.delete_doc("Report", "User Activity Report Without Sort")
		with open(os.path.join(os.path.dirname(__file__), "user_activity_report_without_sort.json")) as f:
			nts.get_doc(json.loads(f.read())).insert()

		report = nts.get_doc("Report", "User Activity Report Without Sort")
		columns, data = report.get_data()

		self.assertEqual(columns[0].get("label"), "ID")
		self.assertEqual(columns[1].get("label"), "User Type")
		self.assertTrue("Administrator" in [d[0] for d in data])
		nts.delete_doc("Report", "User Activity Report Without Sort")

	def test_non_standard_script_report(self):
		report_name = "Test Non Standard Script Report"
		if not nts.db.exists("Report", report_name):
			report = nts.get_doc(
				{
					"doctype": "Report",
					"ref_doctype": "User",
					"report_name": report_name,
					"report_type": "Script Report",
					"is_standard": "No",
				}
			).insert(ignore_permissions=True)
		else:
			report = nts.get_doc("Report", report_name)

		report.report_script = """
totals = {}
for user in nts.get_all('User', fields = ['name', 'user_type', 'creation']):
    if not user.user_type in totals:
        totals[user.user_type] = 0
    totals[user.user_type] = totals[user.user_type] + 1

data = [
    [
        {'fieldname': 'type', 'label': 'Type'},
        {'fieldname': 'value', 'label': 'Value'}
    ],
    [
        {"type":key, "value": value} for key, value in totals.items()
    ]
]
"""
		report.save()
		data = report.get_data()

		# check columns
		self.assertEqual(data[0][0]["label"], "Type")

		# check values
		self.assertTrue("System User" in [d.get("type") for d in data[1]])

	def test_script_report_with_columns(self):
		report_name = "Test Script Report With Columns"

		if nts.db.exists("Report", report_name):
			nts.delete_doc("Report", report_name)

		report = nts.get_doc(
			{
				"doctype": "Report",
				"ref_doctype": "User",
				"report_name": report_name,
				"report_type": "Script Report",
				"is_standard": "No",
				"columns": [
					dict(fieldname="type", label="Type", fieldtype="Data"),
					dict(fieldname="value", label="Value", fieldtype="Int"),
				],
			}
		).insert(ignore_permissions=True)

		report.report_script = """
totals = {}
for user in nts.get_all('User', fields = ['name', 'user_type', 'creation']):
    if not user.user_type in totals:
        totals[user.user_type] = 0
    totals[user.user_type] = totals[user.user_type] + 1

result = [
        {"type":key, "value": value} for key, value in totals.items()
    ]
"""

		report.save()
		data = report.get_data()

		# check columns
		self.assertEqual(data[0][0]["label"], "Type")

		# check values
		self.assertTrue("System User" in [d.get("type") for d in data[1]])

	def test_toggle_disabled(self):
		"""Make sure that authorization is respected."""
		# Assuming that there will be reports in the system.
		reports = nts.get_all(doctype="Report", limit=1)
		report_name = reports[0]["name"]
		doc = nts.get_doc("Report", report_name)
		status = doc.disabled

		# User has write permission on reports and should pass through
		nts.set_user("test@example.com")
		doc.toggle_disable(not status)
		doc.reload()
		self.assertNotEqual(status, doc.disabled)

		# User has no write permission on reports, permission error is expected.
		nts.set_user("test1@example.com")
		doc = nts.get_doc("Report", report_name)
		with self.assertRaises(nts.exceptions.ValidationError):
			doc.toggle_disable(1)

		# Set user back to administrator
		nts.set_user("Administrator")

	def test_add_total_row_for_tree_reports(self):
		report_settings = {"tree": True, "parent_field": "parent_value"}

		columns = [
			{
				"fieldname": "parent_column",
				"label": "Parent Column",
				"fieldtype": "Data",
				"width": 10,
			},
			{
				"fieldname": "column_1",
				"label": "Column 1",
				"fieldtype": "Float",
				"width": 10,
			},
			{
				"fieldname": "column_2",
				"label": "Column 2",
				"fieldtype": "Float",
				"width": 10,
			},
		]

		result = [
			{"parent_column": "Parent 1", "column_1": 200, "column_2": 150.50},
			{
				"parent_column": "Child 1",
				"column_1": 100,
				"column_2": 75.25,
				"parent_value": "Parent 1",
			},
			{
				"parent_column": "Child 2",
				"column_1": 100,
				"column_2": 75.25,
				"parent_value": "Parent 1",
			},
		]

		result = add_total_row(
			result,
			columns,
			meta=None,
			is_tree=report_settings["tree"],
			parent_field=report_settings["parent_field"],
		)
		self.assertEqual(result[-1][0], "Total")
		self.assertEqual(result[-1][1], 200)
		self.assertEqual(result[-1][2], 150.50)

	def test_cte_in_query_report(self):
		cte_query = textwrap.dedent(
			"""
            with enabled_users as (
                select name
                from `tabUser`
                where enabled = 1
            )
            select * from enabled_users;
        """
		)

		report = nts.get_doc(
			{
				"doctype": "Report",
				"ref_doctype": "User",
				"report_name": "Enabled Users List",
				"report_type": "Query Report",
				"is_standard": "No",
				"query": cte_query,
			}
		).insert()

		if nts.db.db_type == "mariadb":
			col, rows = report.execute_query_report(filters={})
			self.assertEqual(col[0], "name")
			self.assertGreaterEqual(len(rows), 1)
		elif nts.db.db_type == "postgres":
			self.assertRaises(nts.PermissionError, report.execute_query_report, filters={})
