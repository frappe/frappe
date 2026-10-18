# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.desk.reportview import (
	_reorder_by_visible_names,
	append_totals_row,
	delete_bulk,
	export_query,
	extract_fieldnames,
	get,
	get_field_info,
	get_filter_dashboard_data,
	get_stats,
)
from frappe.tests import IntegrationTestCase
from frappe.utils.logging import get_log_db


class TestReportview(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		previous_form_dict = frappe.local.form_dict
		self.addCleanup(setattr, frappe.local, "form_dict", previous_form_dict)

	def test_get_field_info_translates_field_labels(self):
		doctype = "Translation"
		translations = {
			"Created On": "Translated Created On",
			"Translated Text": "Translated Field Label",
		}
		for source, translated in translations.items():
			frappe.get_doc(
				{
					"doctype": "Translation",
					"language": "de",
					"source_text": source,
					"translated_text": translated,
					"context": doctype,
				}
			).insert()

		frappe.local.lang = "de"
		try:
			field_info = get_field_info(["creation", "translated_text"], doctype)
		finally:
			frappe.local.lang = "en"

		self.assertEqual(
			[field["label"] for field in field_info],
			["Translated Created On", "Translated Field Label"],
		)

	def test_get_accepts_native_filters_and_fields(self):
		# native dict/list payloads (JSON request body) instead of JSON strings
		frappe.local.form_dict = frappe._dict(
			doctype="ToDo",
			filters={"status": "Open"},
			fields=["name", "status"],
		)
		result = get()
		self.assertIn("keys", result)
		self.assertIn("values", result)

	def test_get_stats_accepts_native(self):
		# stats as native list (L738) and filters as native list (L740)
		out = get_stats(stats=["_user_tags"], doctype="ToDo", filters=[["ToDo", "status", "=", "Open"]])
		self.assertIsInstance(out, dict)

	def test_get_filter_dashboard_data_accepts_native(self):
		out = get_filter_dashboard_data(
			stats=[{"name": "status", "type": "Select"}], doctype="ToDo", filters=[]
		)
		self.assertIsInstance(out, dict)

	def test_export_query_with_totals_and_translate(self):
		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			file_format_type="CSV",
			fields=("name", "module", "issingle"),
			filters={"issingle": 1, "module": "Core"},
			add_totals_row=1,
			translate_values=1,
		)
		export_query()
		self.assertTrue(frappe.response["filename"].endswith(".csv"))
		self.assertEqual(frappe.response["type"], "binary")

	def test_append_totals_row_uses_min_and_max_for_min_and_max_aggregates(self):
		fields = [
			"`tabToDo`.`status`",
			{"SUM": "`tabToDo`.`idx`", "as": "_aggregate_column"},
			{"MIN": "`tabToDo`.`idx`", "as": "_aggregate_column_1"},
			"max(`tabToDo`.`idx`) as _aggregate_column_2",
		]
		data = [("Open", 10, 3, 10), ("Closed", 20, 1, 20), ("Cancelled", None, None, None)]

		totals = append_totals_row(data, fields)[-1]

		self.assertEqual(totals, ["Total", 30, 1, 20])

	def test_csv(self):
		from csv import QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC, DictReader
		from io import StringIO

		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			file_format_type="CSV",
			fields=("name", "module", "issingle"),
			filters={"issingle": 1, "module": "Core"},
		)

		for delimiter in (",", ";", "\t", "|"):
			frappe.local.form_dict.csv_delimiter = delimiter
			for quoting in (QUOTE_ALL, QUOTE_MINIMAL, QUOTE_NONE, QUOTE_NONNUMERIC):
				frappe.local.form_dict.csv_quoting = quoting

				export_query()

				self.assertTrue(frappe.response["filename"].endswith(".csv"))
				self.assertEqual(frappe.response["type"], "binary")
				with StringIO(frappe.response["filecontent"].decode("utf-8")) as result:
					reader = DictReader(result, delimiter=delimiter, quoting=quoting)
					for row in reader:
						self.assertEqual(int(row["Is Single"]), 1)
						self.assertEqual(row["Module"], "Core")

	def exported_rows(self):
		from csv import reader
		from io import StringIO

		return list(reader(StringIO(frappe.response["filecontent"].decode("utf-8"))))

	def make_exporter(self, if_owner=0):
		"""A user whose only export permission on ToDo comes from a test role."""
		from frappe.permissions import update_permission_property

		update_permission_property("ToDo", "All", 0, "export", 1)
		update_permission_property("ToDo", "All", 0, "if_owner", if_owner)
		frappe.clear_cache(doctype="ToDo")
		self.addCleanup(frappe.clear_cache, doctype="ToDo")
		frappe.get_doc(doctype="Role", role_name="_Test Exporter").insert(ignore_if_duplicate=True)
		return create_user("exporter@example.com", "_Test Exporter").name

	def export_grouped_status(self, names):
		frappe.local.form_dict = frappe._dict(
			doctype="ToDo",
			file_format_type="CSV",
			fields=json.dumps(["status", {"COUNT": "name", "as": "count"}]),
			filters=json.dumps([["name", "in", names]]),
			group_by="status",
			order_by="status asc",
		)
		export_query()

	def test_export_has_only_the_requested_columns(self):
		with self.set_user(self.make_exporter()):
			self.assertTrue(frappe.permissions.can_export("ToDo"))
			todo = self.make_todo("Plain export")
			frappe.local.form_dict = frappe._dict(
				doctype="ToDo",
				file_format_type="CSV",
				fields=json.dumps(["name", "description"]),
				filters=json.dumps([["name", "=", todo.name]]),
			)
			export_query()
			self.assertEqual(len(self.exported_rows()[0]), 3)

	def test_grouped_export_has_no_owner_column(self):
		with self.set_user(self.make_exporter()):
			todos = [self.make_todo(f"Grouped export {i}") for i in range(3)]
			frappe.db.set_value("ToDo", todos[0].name, "status", "Closed")
			self.export_grouped_status([todo.name for todo in todos])
			header, *rows = self.exported_rows()
			self.assertEqual(len(header), 3)
			self.assertEqual({row[1]: int(row[2]) for row in rows}, {"Closed": 1, "Open": 2})

	def test_owner_only_export_checks_rows_but_leaves_out_the_owner(self):
		with self.set_user(self.make_exporter(if_owner=1)):
			self.assertFalse(frappe.permissions.can_export("ToDo"))
			todo = self.make_todo("Own export")
			frappe.local.form_dict = frappe._dict(
				doctype="ToDo",
				file_format_type="CSV",
				fields=json.dumps(["name", "description"]),
				filters=json.dumps([["name", "=", todo.name]]),
			)
			export_query()
			self.assertEqual(len(self.exported_rows()[0]), 3)

			others = [self.make_todo(f"Own grouped export {i}") for i in range(2)]
			frappe.db.set_value("ToDo", others[0].name, "status", "Closed")
			self.export_grouped_status([todo.name, *(other.name for other in others)])
			header, *rows = self.exported_rows()
			self.assertEqual(len(header), 3)
			self.assertEqual({row[1]: int(row[2]) for row in rows}, {"Closed": 1, "Open": 2})

	def test_reorder_by_visible_names(self):
		fields = ["`tabDocType`.`name`", "`tabDocType`.`module`"]
		ret = [
			("DocType", "Core"),
			("DocField", "Core"),
			("Report", "Core"),
		]
		# Reorder — server-order was DocType, DocField, Report; client shows Report first.
		reordered = _reorder_by_visible_names(ret, fields, "DocType", ["Report", "DocType"])
		self.assertEqual(reordered, [("Report", "Core"), ("DocType", "Core")])

		# When name column can't be located, fall back to ret unchanged.
		fields_without_name = ["`tabDocType`.`module`"]
		ret_no_name = [("Core",), ("Website",)]
		unchanged = _reorder_by_visible_names(ret_no_name, fields_without_name, "DocType", ["x"])
		self.assertEqual(unchanged, ret_no_name)

	def test_reorder_by_visible_names_keeps_duplicate_name_child_rows(self):
		fields = ["`tabDocType`.`name`", "`tabDocField`.`fieldname`"]
		ret = [
			("DocType", "module"),
			("DocType", "istable"),
			("DocField", "label"),
		]
		visible_names = ["DocType", "DocType", "DocField"]
		reordered = _reorder_by_visible_names(ret, fields, "DocType", visible_names)
		self.assertEqual(
			reordered,
			[("DocType", "module"), ("DocType", "istable"), ("DocField", "label")],
		)

	def test_export_query_preserves_visible_names_order(self):
		from csv import DictReader
		from io import StringIO

		# Pick three known DocTypes and request them in a non-alphabetical order.
		desired_order = ["Report", "DocType", "DocField"]
		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			file_format_type="CSV",
			fields=("`tabDocType`.`name`", "`tabDocType`.`module`"),
			filters={"name": ("in", desired_order)},
			order_by="`tabDocType`.`name` asc",  # would otherwise sort alphabetically
			visible_names=json.dumps(desired_order),
		)
		export_query()
		with StringIO(frappe.response["filecontent"].decode("utf-8")) as buf:
			rows = list(DictReader(buf))
		names_in_export = [row["ID"] for row in rows if row.get("ID") in desired_order]
		self.assertEqual(names_in_export, desired_order)

	def test_export_query_keeps_distinct_child_rows(self):
		from csv import reader
		from io import StringIO

		members = ["test_rv_a@example.com", "test_rv_b@example.com", "test_rv_c@example.com"]
		for email in members:
			create_user(email)
		exporter = create_user("test_rv_export@example.com")

		group = frappe.get_doc(
			{
				"doctype": "User Group",
				"name": "Report Export Child Rows",
				"user_group_members": [{"user": email} for email in members],
			}
		).insert()
		self.addCleanup(group.delete)

		with self.set_user(exporter.name):
			frappe.local.form_dict = frappe._dict(
				doctype="User Group",
				file_format_type="CSV",
				fields=["`tabUser Group`.`name`", "`tabUser Group Member`.`user`"],
				filters={"name": group.name},
				# client sends the parent name once per visible child row
				visible_names=json.dumps([group.name] * len(members)),
			)
			export_query()

		with StringIO(frappe.response["filecontent"].decode("utf-8")) as buf:
			rows = list(reader(buf))[1:]

		exported_members = [cell for row in rows for cell in row if cell in set(members)]
		self.assertEqual(sorted(exported_members), sorted(members))

	def test_extract_fieldname(self):
		self.assertEqual(
			extract_fieldnames("count(distinct `tabPhoto`.name) as total_count")[0], "tabPhoto.name"
		)

		self.assertEqual(extract_fieldnames("owner")[0], "owner")
		self.assertEqual(extract_fieldnames("from")[0], "from")

		self.assertEqual(extract_fieldnames("module")[0], "module")

		self.assertEqual(extract_fieldnames("count(`tabPhoto`.name) as total_count")[0], "tabPhoto.name")

		self.assertEqual(extract_fieldnames("count(distinct `tabPhoto`.name)")[0], "tabPhoto.name")

		self.assertEqual(extract_fieldnames("count(`tabPhoto`.name)")[0], "tabPhoto.name")

		self.assertEqual(
			extract_fieldnames("count(distinct `tabJob Applicant`.name) as total_count")[0],
			"tabJob Applicant.name",
		)

		self.assertEqual(
			extract_fieldnames("(1 / nullif(locate('a', `tabAddress`.`name`), 0)) as `_relevance`")[0],
			"tabAddress.name",
		)

		self.assertEqual(
			extract_fieldnames("(1 / nullif(locate('(a)', `tabAddress`.`name`), 0)) as `_relevance`")[0],
			"tabAddress.name",
		)

		self.assertEqual(extract_fieldnames("EXTRACT(MONTH FROM date_column) AS month")[0], "date_column")

		self.assertEqual(extract_fieldnames("COUNT(*) AS count")[0], "*")

		self.assertEqual(
			extract_fieldnames("first_name + ' ' + last_name AS full_name"), ["first_name", "last_name"]
		)

		self.assertEqual(
			extract_fieldnames("CONCAT(first_name, ' ', last_name) AS full_name"),
			["first_name", "last_name"],
		)

		self.assertEqual(
			extract_fieldnames("CONCAT(id, '/', name, '/', age, '/', marks) AS student"),
			["id", "name", "age", "marks"],
		)

		self.assertEqual(extract_fieldnames("tablefield.fiedname")[0], "tablefield.fiedname")

		self.assertEqual(extract_fieldnames("`tabChild DocType`.`fiedname`")[0], "tabChild DocType.fiedname")

		self.assertEqual(extract_fieldnames("sum(1)"), [])

	def test_export_report_via_email(self):
		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			file_format_type="CSV",
			fields=("name", "module", "issingle"),
			filters={"issingle": 1, "module": "Core"},
			export_in_background=1,
		)

		frappe.db.delete("Email Queue")
		user_email = frappe.get_cached_value("User", frappe.session.user, "email")
		frappe.db.delete("Email Unsubscribe", {"email": user_email})
		export_query()
		email_queue = frappe.get_all("Email Queue")

		self.assertTrue(email_queue, "Email was not enqueued")

	def test_export_ignores_link_titles_argument(self):
		"""Regression: the report view exports with the same args it renders the table with."""
		previous_response = frappe.local.response
		self.addCleanup(setattr, frappe.local, "response", previous_response)
		frappe.local.response = frappe._dict()
		frappe.local.form_dict = frappe._dict(
			doctype="DocType",
			file_format_type="CSV",
			fields=("name", "module", "issingle"),
			filters={"issingle": 1, "module": "Core"},
			with_link_titles=1,
		)

		export_query()

		self.assertIn("filecontent", frappe.local.response)

	def test_get_sends_link_titles_when_requested(self):
		self.enable_link_titles("User")
		with self.set_user("test@example.com"):
			todo = self.make_todo("Report view link title task")
			response = self.get_todo_rows(todo.name, with_link_titles=1)

			full_name = frappe.db.get_value("User", "test@example.com", "full_name")
			self.assertEqual(frappe.local.response["_link_titles"]["User::test@example.com"], full_name)
			self.assertIn("test@example.com", response["values"][0])

	def test_get_skips_link_titles_unless_requested(self):
		self.enable_link_titles("User")
		with self.set_user("test@example.com"):
			todo = self.make_todo("Report view task without titles")
			self.get_todo_rows(todo.name)
			self.assertNotIn("_link_titles", frappe.local.response)

	def test_get_sends_link_titles_for_child_table_columns(self):
		"""`compress` drops the child table prefix, so keys pair back to the requested fields."""
		self.enable_link_titles("Role", title_field="role_name")

		self.get_rows(
			doctype="User",
			fields=["`tabUser`.`name`", "`tabHas Role`.`role`"],
			filters={"name": "Administrator"},
			with_link_titles=1,
		)

		self.assertEqual(frappe.local.response["_link_titles"]["Role::System Manager"], "System Manager")

	def test_get_sends_link_titles_for_aliased_child_table_columns(self):
		self.enable_link_titles("User")
		group = frappe.get_doc(
			{
				"doctype": "User Group",
				"name": "Report Link Titles",
				"user_group_members": [{"user": "test@example.com"}],
			}
		).insert()
		frappe.get_doc("User", "test@example.com").add_roles("System Manager")
		full_name = frappe.db.get_value("User", "test@example.com", "full_name")
		self.assertNotEqual(full_name, "test@example.com")

		with self.set_user("test@example.com"):
			result = self.get_rows(
				doctype="User Group",
				fields=[
					"`tabUser Group`.`name`",
					"`tabUser Group Member`.`user` as 'User Group Member:user'",
				],
				filters={"name": group.name},
				with_link_titles=1,
			)

			self.assertEqual(result["keys"], ["name", "User Group Member:user"])
			self.assertEqual(result["values"][0][1], "test@example.com")
			self.assertEqual(frappe.local.response["_link_titles"]["User::test@example.com"], full_name)

	def get_todo_rows(self, name, **extra_params):
		return self.get_rows(
			doctype="ToDo",
			fields=["name", "allocated_to"],
			filters={"name": name},
			**extra_params,
		)

	def get_rows(self, **form_params):
		previous_response = frappe.local.response
		self.addCleanup(setattr, frappe.local, "response", previous_response)
		frappe.local.response = frappe._dict()
		frappe.local.form_dict = frappe._dict(**form_params)
		return get()

	def enable_link_titles(self, doctype, title_field=None):
		self.set_doctype_property(doctype, "show_title_field_in_link", "1", "Check")
		if title_field:
			self.set_doctype_property(doctype, "title_field", title_field, "Data")

	def set_doctype_property(self, doctype, property, value, property_type):
		property_setter = frappe.get_doc(
			doctype="Property Setter",
			doc_type=doctype,
			doctype_or_field="DocType",
			property=property,
			property_type=property_type,
			value=value,
		).insert()
		self.addCleanup(property_setter.delete)

	def make_todo(self, description):
		return frappe.get_doc(
			doctype="ToDo",
			description=description,
			allocated_to=frappe.session.user,
			assigned_by=frappe.session.user,
		).insert()

	def test_get_with_multiple_group_by_and_aggregates(self):
		user = create_user("test_reportview_group_by@example.com", "System Manager")
		with self.set_user(user.name):
			frappe.local.form_dict = frappe._dict(
				doctype="User",
				fields=[
					"`tabUser`.`user_type`",
					"`tabUser`.`enabled`",
					{"COUNT": "`tabUser`.`name`", "as": "_aggregate_column"},
					{"SUM": "`tabUser`.`simultaneous_sessions`", "as": "_aggregate_column_1"},
				],
				group_by="`tabUser`.`user_type`, `tabUser`.`enabled`",
				order_by="_aggregate_column desc",
			)
			result = get()
			expected = frappe.get_list(
				"User",
				fields=[
					"user_type",
					"enabled",
					{"COUNT": "*", "as": "count"},
					{"SUM": "simultaneous_sessions", "as": "total"},
				],
				group_by="user_type, enabled",
				as_list=True,
			)

		self.assertEqual(result["keys"], ["user_type", "enabled", "_aggregate_column", "_aggregate_column_1"])
		self.assertEqual(sorted(map(tuple, result["values"])), sorted(map(tuple, expected)))

	def test_delete_bulk_reports_reason_per_document(self):
		email_queue = frappe.get_doc(
			doctype="Email Queue", sender="test@example.com", message="Your report is ready"
		).insert()
		user = create_user("test_reportview_bulk_delete_manager@example.com", "System Manager")
		with self.set_user(user.name), patch.object(frappe.db, "commit"), patch.object(frappe.db, "rollback"):
			undeleted = delete_bulk("Email Queue", [email_queue.name])

		self.assertEqual(undeleted, [email_queue.name])
		self.assertIn("Only Administrator can delete Email Queue", frappe.message_log[-1].message[0])

	def test_delete_bulk_reports_missing_permission(self):
		user = create_user("test_reportview_bulk_delete_manager@example.com", "System Manager")
		with self.set_user(user.name), patch.object(frappe.db, "commit"), patch.object(frappe.db, "rollback"):
			delete_bulk("User", ["Guest", "Administrator"])

		message = frappe.message_log[-1].message
		self.assertEqual(len(message), 1)
		self.assertIn("You need the 'delete' permission", message[0])

	def test_delete_bulk_keeps_other_permission_errors(self):
		user = create_user("test_reportview_bulk_delete_manager@example.com", "System Manager")
		with (
			self.set_user(user.name),
			patch.object(frappe.db, "commit"),
			patch.object(frappe.db, "rollback"),
			patch(
				"frappe.delete_doc",
				side_effect=lambda doctype, name: frappe.has_permission(
					"User", "write", "Administrator", throw=True
				),
			),
		):
			delete_bulk("Auto Repeat", ["AUT-AR-00001"])

		self.assertIn("No permission for", frappe.message_log[-1].message[0])

	def test_delete_bulk_logs_unexpected_error(self):
		user = create_user("test_reportview_bulk_delete_manager@example.com", "System Manager")
		with (
			self.set_user(user.name),
			patch.object(frappe.db, "commit"),
			patch.object(frappe.db, "rollback"),
			patch("frappe.delete_doc", side_effect=frappe.QueryTimeoutError),
		):
			delete_bulk("User", ["test@example.com"])

		error_log = get_log_db().get_value(
			"Error Log",
			{"reference_name": "test@example.com"},
			["name", "fingerprint"],
			as_dict=True,
			order_by="creation desc",
		)
		self.assertIn(error_log.name, frappe.message_log[-1].message[0])
		self.assertTrue(error_log.fingerprint)

	def test_delete_bulk_logs_unexpected_error_once(self):
		logged_before = get_log_db().count("Error Log", {"reference_name": "test1@example.com"})
		user = create_user("test_reportview_bulk_delete_manager@example.com", "System Manager")
		with (
			self.set_user(user.name),
			patch.object(frappe.db, "commit"),
			patch.object(frappe.db, "rollback"),
			patch(
				"frappe.delete_doc", side_effect=[None, frappe.QueryTimeoutError, frappe.QueryTimeoutError]
			),
		):
			delete_bulk("User", ["test@example.com", "test1@example.com"])

		self.assertEqual(
			get_log_db().count("Error Log", {"reference_name": "test1@example.com"}), logged_before + 1
		)

	def test_delete_bulk_hides_error_log_link_without_permission(self):
		user = create_user("test_reportview_bulk_delete@example.com", "Website Manager")
		with (
			self.set_user(user.name),
			patch.object(frappe.db, "commit"),
			patch.object(frappe.db, "rollback"),
			patch("frappe.delete_doc", side_effect=frappe.QueryTimeoutError),
		):
			delete_bulk("User", ["test@example.com"])

		self.assertNotIn("error-log", frappe.message_log[-1].message[0])

	def test_delete_bulk_lists_what_each_document_is_linked_with(self):
		salutation = frappe.get_doc(doctype="Salutation", salutation="Professor").insert()
		contact = frappe.get_doc(doctype="Contact", first_name="Priya", salutation=salutation.name).insert()
		user = create_user("test_reportview_bulk_delete_manager@example.com", "System Manager")

		with self.set_user(user.name), patch.object(frappe.db, "commit"), patch.object(frappe.db, "rollback"):
			delete_bulk("Salutation", [salutation.name])

		self.assertIn(contact.name, frappe.message_log[-1].message[0])
