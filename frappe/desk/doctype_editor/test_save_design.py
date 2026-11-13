# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.doctype_editor.save import save_doctype_editor
from frappe.desk.doctype_editor.versions import base_version
from frappe.tests import IntegrationTestCase

DOCTYPE = "Test Editor 47271"


def make_custom_doctype(name: str = DOCTYPE, fields: list[dict] | None = None, **kwargs):
	"""A custom DocType with a `title` field; DDL commits, so each test deletes it again."""
	frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
	doc = frappe.get_doc(
		{
			"doctype": "DocType",
			"name": name,
			"module": "Custom",
			"custom": 1,
			"fields": fields or [{"fieldname": "title", "label": "Title", "fieldtype": "Data"}],
			"permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}],
			**kwargs,
		}
	).insert()
	return doc


def details_rows(dt: str = DOCTYPE) -> list:
	return frappe.get_all(
		"Form Layout", filters={"dt": dt, "type": "Details"}, fields=["name", "layout", "omitted"]
	)


def placed(row) -> list[str]:
	tree = json.loads(row.layout)
	return [
		field
		for tab in tree
		for section in tab["sections"]
		for column in section["columns"]
		for field in column["fields"]
	]


class TestSaveDesign(IntegrationTestCase):
	def setUp(self):
		make_custom_doctype()
		self.addCleanup(frappe.delete_doc, "DocType", DOCTYPE, force=True, ignore_missing=True)
		self.addCleanup(frappe.db.delete, "Form Layout", {"dt": DOCTYPE})

	def save(self, edits, dt: str = DOCTYPE, version: dict | None = None):
		return save_doctype_editor(dt, "Design", version or base_version(dt), edits)

	def test_an_added_field_is_saved_and_placed_on_details(self):
		result = self.save(
			[
				{"act": "fields.add_field", "label": "Due Date", "fieldtype": "Date"},
				{
					"act": "canvas.place_field",
					"layout": {"type": "Details"},
					"fieldname": "due_date",
					"column": "column_1",
					"index": 0,
				},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertEqual(frappe.get_meta(DOCTYPE).get_field("due_date").fieldtype, "Date")
		[row] = details_rows()
		self.assertEqual(placed(row), ["due_date", "title"])
		self.assertEqual(json.loads(row.omitted or "[]"), [])

	def test_canvas_edits_shape_the_details_layout(self):
		details = {"type": "Details"}
		result = self.save(
			[
				{"act": "fields.add_field", "label": "Notes", "fieldtype": "Small Text"},
				{"act": "canvas.add_tab", "layout": details, "name": "more", "label": "More"},
				{"act": "canvas.add_section", "layout": details, "tab": "more", "name": "notes_section"},
				{"act": "canvas.add_column", "layout": details, "section": "notes_section"},
				{
					"act": "canvas.place_field",
					"layout": details,
					"fieldname": "notes",
					"section": "notes_section",
					"column": "column_2",
				},
				{
					"act": "canvas.set_container_property",
					"layout": details,
					"container": "notes_section",
					"property": "collapsible",
					"value": 1,
				},
				{"act": "canvas.remove_column", "layout": details, "section": "notes_section", "column": "column_1"},
				{"act": "canvas.move_tab", "layout": details, "tab": "more", "index": 0},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		[row] = details_rows()
		[more, first] = json.loads(row.layout)
		self.assertEqual(more["name"], "more")
		[section] = more["sections"]
		self.assertEqual(section["collapsible"], 1)
		self.assertEqual(section["columns"], [{"name": "column_2", "fields": ["notes"]}])
		self.assertEqual(placed(row), ["notes", "title"])

	def test_a_column_named_in_two_sections_needs_its_section(self):
		details = {"type": "Details"}
		result = self.save(
			[
				{"act": "canvas.add_section", "layout": details, "tab": "first_tab", "name": "other"},
				{"act": "canvas.unplace_field", "layout": details, "fieldname": "title"},
				{"act": "canvas.place_field", "layout": details, "fieldname": "title", "column": "column_1"},
			]
		)
		self.assertFalse(result["saved"])
		[error] = result["errors"]
		self.assertEqual(error["edit"], 2)
		self.assertEqual(error["target"]["kind"], "container")

	def test_field_properties_are_set_and_fields_reordered(self):
		result = self.save(
			[
				{"act": "fields.add_field", "label": "Status", "fieldtype": "Data"},
				{"act": "fields.set_field_property", "fieldname": "title", "property": "reqd", "value": 1},
				{"act": "fields.reorder_field", "fieldname": "status", "index": 0},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		meta = frappe.get_meta(DOCTYPE)
		self.assertEqual(meta.get_field("title").reqd, 1)
		self.assertEqual([field.fieldname for field in meta.fields], ["status", "title"])

	def test_a_fieldname_is_changed_only_by_renaming(self):
		result = self.save(
			[{"act": "fields.set_field_property", "fieldname": "title", "property": "fieldname", "value": "x"}]
		)
		self.assertFalse(result["saved"])
		[error] = result["errors"]
		self.assertEqual(error["target"], {"kind": "field", "fieldname": "title", "property": "fieldname"})
