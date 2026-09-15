# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.reportview import (
	_reorder_by_visible_names,
	export_query,
	extract_fieldnames,
	get,
	get_field_info,
	get_filter_dashboard_data,
	get_stats,
)
from frappe.tests import IntegrationTestCase


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
		export_query()
		email_queue = frappe.get_all("Email Queue")

		self.assertTrue(email_queue, "Email was not enqueued")

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
