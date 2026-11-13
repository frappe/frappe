# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
import os
import shutil
import tempfile
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.doctype import write_doctype_files
from frappe.desk.doctype.form_layout.form_layout import get_form_layouts
from frappe.desk.doctype_editor.rename import rename_field
from frappe.desk.doctype_editor.save import save_doctype_editor
from frappe.desk.doctype_editor.versions import base_version
from frappe.tests import IntegrationTestCase
from frappe.utils import CallbackManager

DOCTYPE = "Test Editor 47271"


def make_custom_doctype(name: str = DOCTYPE, fields: list[dict] | None = None, **kwargs):
	"""A custom DocType with a `title` field; DDL commits, so each test deletes it again."""
	frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
	frappe.db.sql_ddl(f"drop table if exists `tab{name}`")
	frappe.db.delete("Form Layout", {"dt": name})
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


def drop_column(dt: str, fieldname: str):
	if frappe.db.has_column(dt, fieldname):
		frappe.db.sql_ddl(f"alter table `tab{dt}` drop column `{fieldname}`")


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


def delete_committed(doctype: str, name: str):
	"""Its insert's DDL committed, and the class's rollback runs after this cleanup."""
	frappe.delete_doc(doctype, name, force=True, ignore_missing=True)
	frappe.db.commit()  # nosemgrep


def restore_modified(doctype: str, modified):
	"""A save of a real DocType commits with its DDL, so the rollback cannot undo it."""
	frappe.db.set_value("DocType", doctype, "modified", modified, update_modified=False)
	frappe.db.commit()  # nosemgrep


def omitted(row) -> list[str]:
	return json.loads(row.omitted or "[]")


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
		self.assertEqual(omitted(row), [])

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
				{
					"act": "canvas.remove_column",
					"layout": details,
					"section": "notes_section",
					"column": "column_1",
				},
				{"act": "canvas.move_tab", "layout": details, "tab": "more", "index": 0},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		[row] = details_rows()
		[more, _first] = json.loads(row.layout)
		self.assertEqual(more["name"], "more")
		[section] = more["sections"]
		self.assertEqual(section["collapsible"], 1)
		self.assertEqual(section["columns"], [{"name": "column_2", "fields": ["notes"]}])
		self.assertEqual(placed(row), ["notes", "title"])

	def test_fields_of_a_removed_container_with_no_sibling_leave_the_layout(self):
		details = {"type": "Details"}
		tree = self.save([{"act": "canvas.add_tab", "layout": details, "name": "more"}])
		self.assertTrue(tree["saved"], tree.get("errors"))
		[row] = details_rows()
		section = json.loads(row.layout)[0]["sections"][0]["name"]
		result = self.save([{"act": "canvas.remove_section", "layout": details, "section": section}])
		self.assertTrue(result["saved"], result.get("errors"))
		[row] = details_rows()
		self.assertEqual(placed(row), [])
		self.assertEqual(omitted(row), ["title"])

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
			[
				{
					"act": "fields.set_field_property",
					"fieldname": "title",
					"property": "fieldname",
					"value": "x",
				}
			]
		)
		self.assertFalse(result["saved"])
		[error] = result["errors"]
		self.assertEqual(error["target"], {"kind": "field", "fieldname": "title", "property": "fieldname"})

	def test_a_fetched_field_takes_its_type_from_the_source(self):
		if frappe.db.db_type == "sqlite":
			self.skipTest("DocType.update_fields_to_fetch's update query is ambiguous on SQLite")
		result = self.save(
			[
				{"act": "fields.add_field", "label": "Owner User", "fieldtype": "Link", "options": "User"},
				{
					"act": "fields.fetch_field",
					"link": "owner_user",
					"source": "full_name",
					"layout": {"type": "Details"},
					"column": "column_1",
				},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		field = frappe.get_meta(DOCTYPE).get_field("full_name")
		self.assertEqual(
			(field.fieldtype, field.fetch_from, field.read_only), ("Data", "owner_user.full_name", 1)
		)
		self.assertEqual(field.label, "Full Name")
		[row] = details_rows()
		self.assertEqual(placed(row), ["title", "owner_user", "full_name"])

	def test_a_deleted_field_leaves_every_layout(self):
		self.save([{"act": "fields.add_field", "label": "Status", "fieldtype": "Data"}])
		self.save([{"act": "canvas.unplace_field", "layout": {"type": "Details"}, "fieldname": "title"}])
		quick_entry = frappe.get_doc(
			{
				"doctype": "Form Layout",
				"dt": DOCTYPE,
				"type": "Quick Entry",
				"layout": frappe.as_json(
					[
						{
							"name": "t",
							"sections": [{"name": "s", "columns": [{"name": "c", "fields": ["status"]}]}],
						}
					]
				),
				"omitted": frappe.as_json(["title"]),
			}
		).insert()

		result = self.save(
			[
				{"act": "fields.delete_field", "fieldname": "title"},
				{"act": "fields.delete_field", "fieldname": "status"},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertFalse(frappe.get_meta(DOCTYPE).get_field("status"))
		[details] = details_rows()
		self.assertEqual((placed(details), omitted(details)), ([], []))
		quick_entry.reload()
		self.assertEqual((placed(quick_entry), omitted(quick_entry)), ([], []))

	def test_a_type_with_no_layout_starts_from_what_the_desk_shows(self):
		self.save(
			[
				{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "more"},
				{"act": "canvas.unplace_field", "layout": {"type": "Details"}, "fieldname": "title"},
			]
		)
		result = self.save(
			[
				{"act": "fields.add_field", "label": "Notes", "fieldtype": "Small Text"},
				{"act": "fields.set_field_property", "fieldname": "title", "property": "reqd", "value": 1},
				{"act": "canvas.add_tab", "layout": {"type": "Quick Entry"}, "name": "extra"},
				{"act": "canvas.add_tab", "layout": {"type": "New Record"}, "name": "extra"},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		for type, fields in (("Quick Entry", ["title"]), ("New Record", [])):
			with self.subTest(type=type):
				[row] = frappe.get_all(
					"Form Layout", filters={"dt": DOCTYPE, "type": type}, fields=["layout"]
				)
				self.assertEqual(placed(row), fields)

	def test_a_row_the_save_rewrites_matches_its_source_again(self):
		self.save([{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "more"}])
		self.save(
			[
				{
					"act": "fields.add_field",
					"label": "Due",
					"fieldtype": "Date",
					"layout": {"type": "Details"},
					"column": "column_1",
				}
			]
		)
		[layout] = get_form_layouts(DOCTYPE, "Details")["layouts"]
		self.assertFalse(layout["source_changed"])

	def test_a_field_added_off_the_layout_is_omitted_from_its_rows(self):
		self.save([{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "more"}])
		self.save([{"act": "fields.add_field", "label": "Due", "fieldtype": "Date"}])
		[row] = details_rows()
		self.assertEqual(omitted(row), ["due"])

	def test_the_rename_wrapper_moves_data_and_rewrites_layout_rows(self):
		self.save(
			[
				{
					"act": "canvas.place_field",
					"layout": {"type": "Details"},
					"fieldname": "title",
					"column": "column_1",
				}
			]
		)
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "Kept"}).insert()

		result = rename_field(DOCTYPE, "title", "subject")
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertTrue(frappe.get_meta(DOCTYPE).get_field("subject"))
		self.assertEqual(frappe.db.get_value(DOCTYPE, record.name, "subject"), "Kept")
		[row] = details_rows()
		self.assertEqual(placed(row), ["subject"])

	def test_a_field_added_in_the_same_save_renames_freely(self):
		result = self.save(
			[
				{
					"act": "fields.add_field",
					"label": "Due",
					"fieldtype": "Date",
					"layout": {"type": "Details"},
					"column": "column_1",
				},
				{"act": "fields.rename_field", "fieldname": "due", "new_fieldname": "due_on"},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertTrue(frappe.get_meta(DOCTYPE).get_field("due_on"))
		[row] = details_rows()
		self.assertEqual(placed(row), ["title", "due_on"])

	def test_a_saved_field_renamed_twice_moves_its_data_once(self):
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "Kept"}).insert()
		result = self.save(
			[
				{"act": "fields.rename_field", "fieldname": "title", "new_fieldname": "subject"},
				{"act": "fields.rename_field", "fieldname": "subject", "new_fieldname": "headline"},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertEqual(frappe.db.get_value(DOCTYPE, record.name, "headline"), "Kept")

	def test_a_renamed_field_deleted_and_added_again_starts_empty(self):
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "Old"}).insert()
		result = self.save(
			[
				{"act": "fields.rename_field", "fieldname": "title", "new_fieldname": "headline"},
				{"act": "fields.delete_field", "fieldname": "headline"},
				{"act": "fields.add_field", "label": "Headline", "fieldtype": "Data"},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertIsNone(frappe.db.get_value(DOCTYPE, record.name, "headline"))
		self.assertEqual(frappe.db.get_value(DOCTYPE, record.name, "title"), "Old")

	def test_a_saved_field_renamed_back_keeps_its_name(self):
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "Kept"}).insert()
		result = self.save(
			[
				{"act": "fields.rename_field", "fieldname": "title", "new_fieldname": "subject"},
				{"act": "fields.rename_field", "fieldname": "subject", "new_fieldname": "title"},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertEqual(frappe.db.get_value(DOCTYPE, record.name, "title"), "Kept")

	def test_renaming_a_saved_standard_field_is_refused(self):
		with patch.dict(frappe.conf, {"developer_mode": 1}):
			result = self.save(
				[{"act": "fields.rename_field", "fieldname": "description", "new_fieldname": "details"}],
				dt="ToDo",
			)
		self.assertFalse(result["saved"])
		[error] = result["errors"]
		self.assertEqual(error["target"], {"kind": "field", "fieldname": "description"})

	def test_a_new_child_table_is_saved_before_its_parent(self):
		child = f"{DOCTYPE} Item"
		self.addCleanup(delete_committed, "DocType", child)
		result = self.save(
			{
				DOCTYPE: [
					{
						"act": "fields.add_child_table",
						"table_field": "items",
						"label": "Items",
						"name": child,
					},
				],
				child: [{"act": "fields.add_field", "label": "Qty", "fieldtype": "Int"}],
			}
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertEqual(result["children"], [child])
		child_doc = frappe.get_doc("DocType", child)
		self.assertEqual((child_doc.istable, child_doc.custom, child_doc.module), (1, 1, "Custom"))
		self.assertEqual([field.fieldname for field in child_doc.fields], ["qty"])
		table = frappe.get_meta(DOCTYPE).get_field("items")
		self.assertEqual((table.fieldtype, table.options), ("Table", child))

	def test_a_renamed_table_field_keeps_its_rows(self):
		child = f"{DOCTYPE} Item"
		self.addCleanup(delete_committed, "DocType", child)
		added = self.save(
			{
				DOCTYPE: [{"act": "fields.add_child_table", "table_field": "items", "name": child}],
				child: [{"act": "fields.add_field", "label": "Qty", "fieldtype": "Int"}],
			}
		)
		self.assertTrue(added["saved"], added.get("errors"))
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "Kept", "items": [{"qty": 2}]}).insert()

		result = self.save([{"act": "fields.rename_field", "fieldname": "items", "new_fieldname": "lines"}])
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertEqual([row.qty for row in frappe.get_doc(DOCTYPE, record.name).lines], [2])

	def test_a_saved_virtual_field_renames_with_no_column(self):
		make_custom_doctype(
			fields=[{"fieldname": "shown", "label": "Shown", "fieldtype": "Data", "is_virtual": 1}]
		)
		result = self.save([{"act": "fields.rename_field", "fieldname": "shown", "new_fieldname": "seen"}])
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertTrue(frappe.get_meta(DOCTYPE).get_field("seen"))

	def test_a_table_field_is_not_renamed_onto_a_deleted_table_s_rows(self):
		child = f"{DOCTYPE} Item"
		self.addCleanup(delete_committed, "DocType", child)
		added = self.save(
			{
				DOCTYPE: [{"act": "fields.add_child_table", "table_field": "items", "name": child}],
				child: [{"act": "fields.add_field", "label": "Qty", "fieldtype": "Int"}],
			}
		)
		self.assertTrue(added["saved"], added.get("errors"))
		table = self.save(
			[
				{
					"act": "fields.add_field",
					"label": "Old Items",
					"fieldtype": "Table",
					"options": child,
				}
			]
		)
		self.assertTrue(table["saved"], table.get("errors"))
		frappe.get_doc({"doctype": DOCTYPE, "title": "Old", "old_items": [{"qty": 1}]}).insert()
		deleted = self.save([{"act": "fields.delete_field", "fieldname": "old_items"}])
		self.assertTrue(deleted["saved"], deleted.get("errors"))

		result = self.save(
			[{"act": "fields.rename_field", "fieldname": "items", "new_fieldname": "old_items"}]
		)
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "field", "fieldname": "items"})

	def test_a_renamed_table_field_leaves_other_parents_rows_alone(self):
		child, other = f"{DOCTYPE} Item", f"{DOCTYPE} Other"
		self.addCleanup(delete_committed, "DocType", child)
		added = self.save(
			{
				DOCTYPE: [{"act": "fields.add_child_table", "table_field": "items", "name": child}],
				child: [{"act": "fields.add_field", "label": "Qty", "fieldtype": "Int"}],
			}
		)
		self.assertTrue(added["saved"], added.get("errors"))
		make_custom_doctype(other, [{"fieldname": "items", "fieldtype": "Table", "options": child}])
		self.addCleanup(delete_committed, "DocType", other)
		shared = frappe.get_doc({"doctype": other, "items": [{"qty": 5}]}).insert()

		result = self.save([{"act": "fields.rename_field", "fieldname": "items", "new_fieldname": "lines"}])
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertEqual([row.qty for row in frappe.get_doc(other, shared.name).items], [5])

	def test_a_parent_failing_its_checks_leaves_no_new_child_table(self):
		child = f"{DOCTYPE} Item"
		self.addCleanup(delete_committed, "DocType", child)
		result = self.save(
			{
				DOCTYPE: [
					{"act": "fields.add_child_table", "table_field": "items", "name": child},
					{"act": "fields.add_field", "label": "Party", "fieldtype": "Link"},
				],
				child: [{"act": "fields.add_field", "label": "Qty", "fieldtype": "Int"}],
			}
		)
		self.assertFalse(result["saved"])
		self.assertNotIn("written", result)
		self.assertFalse(frappe.db.exists("DocType", child))

	def test_a_child_failing_the_document_checks_is_not_written(self):
		child = f"{DOCTYPE} Item"
		self.addCleanup(delete_committed, "DocType", child)
		for field in ({"label": "Qty", "fieldtype": "Bogus"}, {"label": "Q" * 300, "fieldtype": "Int"}):
			with self.subTest(field=field["label"][:3]):
				result = self.save(
					{
						DOCTYPE: [{"act": "fields.add_child_table", "table_field": "items", "name": child}],
						child: [{"act": "fields.add_field", "fieldname": "qty", **field}],
					}
				)
				self.assertFalse(result["saved"])
				self.assertNotIn("written", result)
				self.assertFalse(frappe.db.exists("DocType", child))

	def test_edits_for_a_doctype_the_save_does_not_add_are_refused(self):
		result = self.save(
			{DOCTYPE: [], "ToDo": [{"act": "fields.add_field", "label": "X", "fieldtype": "Data"}]}
		)
		self.assertFalse(result["saved"])
		[error] = result["errors"]
		self.assertEqual((error["target"], error["doctype"]), ({"kind": "banner"}, "ToDo"))

	def test_layouts_are_added_renamed_conditioned_and_deleted(self):
		compact = {"type": "Details", "id": "new-1"}
		result = self.save(
			[
				{
					"act": "layouts.add",
					"type": "Details",
					"id": "new-1",
					"condition": "doc.title",
					"start": "copy",
				},
				{"act": "layouts.rename", "layout": compact, "title": "Compact"},
				{"act": "canvas.add_tab", "layout": compact, "name": "extra"},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		[row] = frappe.get_all("Form Layout", {"dt": DOCTYPE}, ["name", "title", "condition", "layout"])
		self.assertEqual((row.title, row.condition), ("Compact", "doc.title"))
		self.assertEqual([tab["name"] for tab in json.loads(row.layout)], ["first_tab", "extra"])
		self.assertEqual(placed(row), ["title"])

		ref = {"type": "Details", "id": row.name}
		self.save([{"act": "layouts.set_condition", "layout": ref, "condition": "doc.docstatus == 0"}])
		self.assertEqual(frappe.db.get_value("Form Layout", row.name, "condition"), "doc.docstatus == 0")
		self.save([{"act": "layouts.delete", "layout": ref}])
		self.assertFalse(frappe.db.exists("Form Layout", row.name))

	def test_the_default_layout_moves_to_an_older_row_in_one_save(self):
		details = {"type": "Details"}
		self.save([{"act": "layouts.add", "type": "Details", "id": "new-1", "condition": "doc.title"}])
		self.save([{"act": "canvas.add_tab", "layout": details, "name": "more"}])
		older, newer = (
			row.name for row in frappe.get_all("Form Layout", {"dt": DOCTYPE}, order_by="creation asc")
		)
		result = self.save(
			[
				{"act": "layouts.set_condition", "layout": {**details, "id": older}, "condition": ""},
				{
					"act": "layouts.set_condition",
					"layout": {**details, "id": newer},
					"condition": "doc.title",
				},
			]
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertFalse(frappe.db.get_value("Form Layout", older, "condition"))

	def test_a_save_over_a_changed_doctype_is_refused_as_stale(self):
		version = base_version(DOCTYPE)
		frappe.db.set_value("DocType", DOCTYPE, "modified", frappe.utils.add_days(frappe.utils.now(), 1))
		result = self.save(
			[{"act": "fields.add_field", "label": "Due", "fieldtype": "Date"}], version=version
		)
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["code"], "stale")
		self.assertFalse(frappe.get_meta(DOCTYPE).get_field("due"))

	def test_a_layout_type_the_doctype_cannot_have_is_refused(self):
		frappe.db.set_value("DocType", DOCTYPE, "istable", 1)
		frappe.clear_cache(doctype=DOCTYPE)
		result = self.save([{"act": "canvas.add_tab", "layout": {"type": "Quick Entry"}, "name": "more"}])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "layout", "layout": "Quick Entry"})

	def test_placing_an_unknown_field_is_keyed_to_that_field(self):
		result = self.save(
			[
				{
					"act": "canvas.place_field",
					"layout": {"type": "Details"},
					"fieldname": "nope",
					"column": "column_1",
				}
			]
		)
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "field", "fieldname": "nope"})

	def test_a_malformed_edit_is_keyed_to_that_edit(self):
		for edit in (
			{"act": "canvas.add_tab", "layout": "Details", "name": "extra"},
			{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "extra", "index": "x"},
			{"act": ["fields.add_field"]},
		):
			with self.subTest(edit=edit):
				result = self.save([edit])
				self.assertFalse(result["saved"])
				self.assertEqual(
					result["errors"],
					[{"target": {"kind": "banner"}, "message": "This edit is malformed.", "edit": 0}],
				)

	def test_a_doctype_that_fails_validation_writes_nothing(self):
		result = self.save(
			[
				{"act": "fields.add_field", "label": "Due", "fieldtype": "Date"},
				{"act": "fields.add_field", "label": "Party", "fieldtype": "Link"},
				{
					"act": "canvas.place_field",
					"layout": {"type": "Details"},
					"fieldname": "due",
					"column": "column_1",
				},
			]
		)
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "banner"})
		self.assertNotIn("written", result)
		self.assertFalse(frappe.get_meta(DOCTYPE).get_field("due"))
		self.assertEqual(details_rows(), [])

	def test_a_layout_that_fails_its_checks_writes_nothing(self):
		details = {"type": "Details"}
		cases = {
			"tab named like a new field": [
				{"act": "canvas.add_tab", "layout": details, "name": "due"},
			],
			"two tabs of one name": [
				{"act": "canvas.add_tab", "layout": details, "name": "extra"},
				{"act": "canvas.add_tab", "layout": details, "name": "extra"},
			],
			"two layouts without a condition": [
				{"act": "canvas.add_tab", "layout": details, "name": "extra"},
				{"act": "layouts.add", "type": "Details", "id": "new-1", "start": "empty"},
			],
		}
		for case, edits in cases.items():
			with self.subTest(case):
				make_custom_doctype()
				result = self.save([{"act": "fields.add_field", "label": "Due", "fieldtype": "Date"}, *edits])
				self.assertFalse(result["saved"])
				self.assertEqual(result["errors"][0]["target"]["kind"], "layout", result["errors"])
				self.assertNotIn("written", result)
				self.assertFalse(frappe.db.exists("DocField", {"parent": DOCTYPE, "fieldname": "due"}))
				self.assertEqual(details_rows(), [])

	def test_a_write_failing_after_the_doctype_saved_keeps_renamed_data(self):
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "Hello"}).insert()
		with (
			patch(
				"frappe.desk.doctype.form_layout.form_layout.FormLayout.validate",
				side_effect=RuntimeError("disk full"),
			),
			patch("frappe.desk.doctype_editor.save.publish_doctype_update") as publish,
		):
			result = self.save(
				[
					{"act": "fields.rename_field", "fieldname": "title", "new_fieldname": "heading"},
					{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "extra"},
				]
			)
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "banner"})
		# MariaDB and Postgres commit the DocType's DDL; SQLite rolls it back with the rest.
		kept = frappe.db.exists("DocField", {"parent": DOCTYPE, "fieldname": "heading"})
		self.assertEqual(bool(kept), frappe.db.db_type != "sqlite")
		self.assertEqual(result["written"], [DOCTYPE] if kept else [])
		self.assertEqual(publish.called, bool(kept), "open desks hear of a written DocType")
		fieldname = "heading" if kept else "title"
		self.assertEqual(frappe.db.get_value(DOCTYPE, record.name, fieldname), "Hello")
		self.assertEqual(details_rows(), [])

	def test_a_new_field_named_like_a_layout_s_own_field_writes_nothing(self):
		inline = {"fieldname": "notes", "label": "Notes", "fieldtype": "Small Text"}
		tree = [{"sections": [{"columns": [{"fields": ["title", inline]}]}]}]
		frappe.get_doc(
			{"doctype": "Form Layout", "dt": DOCTYPE, "type": "New Record", "layout": json.dumps(tree)}
		).insert()
		result = self.save([{"act": "fields.add_field", "label": "Notes", "fieldtype": "Data"}])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"]["kind"], "layout", result["errors"])
		self.assertNotIn("written", result)
		self.assertFalse(frappe.db.exists("DocField", {"parent": DOCTYPE, "fieldname": "notes"}))
		self.assertFalse(frappe.get_meta(DOCTYPE).get_field("notes"), "the check leaves no unsaved meta")

	def test_a_doctype_save_failing_after_its_ddl_keeps_renamed_data(self):
		record = frappe.get_doc({"doctype": DOCTYPE, "title": "Hello"}).insert()
		with patch(
			"frappe.core.doctype.doctype.doctype.DocType.change_modified_of_parent",
			side_effect=RuntimeError("lost connection"),
		):
			result = self.save(
				[{"act": "fields.rename_field", "fieldname": "title", "new_fieldname": "heading"}]
			)
		self.assertFalse(result["saved"])
		# MariaDB and Postgres commit the DocType's DDL; SQLite rolls it back with the rest.
		kept = frappe.db.exists("DocField", {"parent": DOCTYPE, "fieldname": "heading"})
		self.assertEqual(bool(kept), frappe.db.db_type != "sqlite")
		self.assertEqual(result["written"], [DOCTYPE] if kept else [])
		fieldname = "heading" if kept else "title"
		self.assertEqual(frappe.db.get_value(DOCTYPE, record.name, fieldname), "Hello")

	def test_a_data_move_failing_after_a_write_failure_is_reported(self):
		with (
			patch(
				"frappe.desk.doctype.form_layout.form_layout.FormLayout.validate",
				side_effect=RuntimeError("disk full"),
			),
			patch(
				"frappe.desk.doctype_editor.save.rename_field",
				side_effect=[None, frappe.db.DataError("bad value")],
			),
		):
			result = self.save(
				[
					{"act": "fields.rename_field", "fieldname": "title", "new_fieldname": "heading"},
					{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "extra"},
				]
			)
		self.assertFalse(result["saved"])
		if result["written"]:
			self.assertEqual(len(result["errors"]), 2, result["errors"])

	def test_a_deleted_field_s_column_is_not_taken_by_a_new_name(self):
		self.assertTrue(self.save([{"act": "fields.delete_field", "fieldname": "title"}])["saved"])
		self.addCleanup(drop_column, DOCTYPE, "title")
		self.save([{"act": "fields.add_field", "label": "Name Line", "fieldtype": "Data"}])
		for edit in (
			{"act": "fields.add_field", "label": "Title", "fieldtype": "Int"},
			{"act": "fields.rename_field", "fieldname": "name_line", "new_fieldname": "title"},
		):
			with self.subTest(edit["act"]):
				result = self.save([edit])
				self.assertFalse(result["saved"])
				self.assertEqual(result["errors"][0]["target"]["kind"], "field", result["errors"])

	def test_a_new_field_takes_only_field_properties(self):
		result = self.save(
			[
				{
					"act": "fields.add_field",
					"label": "Due",
					"fieldtype": "Date",
					"properties": {"parent": "Note"},
				}
			]
		)
		self.assertFalse(result["saved"])
		target = {"kind": "field", "fieldname": "due", "property": "parent"}
		self.assertEqual(result["errors"][0]["target"], target)

	def test_a_save_tells_open_desks_once(self):
		frappe.db.commit()  # nosemgrep: flush the setUp insert's own message
		with patch("frappe.realtime.emit_via_redis") as emit:
			result = self.save(
				[
					{"act": "fields.add_field", "label": "Due", "fieldtype": "Date"},
					{"act": "layouts.add", "type": "Details", "id": "new-1", "condition": "doc.title"},
					{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "more"},
				]
			)
			frappe.db.commit()  # nosemgrep
		self.assertTrue(result["saved"], result.get("errors"))
		updates = [call for call in emit.call_args_list if call.args[0] == "doctype_update"]
		self.assertEqual(len(updates), 1)


class TestSaveDesignAppFiles(IntegrationTestCase):
	"""A standard DocType in developer mode: layouts go to the app file, exported in-process here."""

	def setUp(self):
		self.folder = tempfile.mkdtemp(prefix="test_save_design_47271_")
		self.addCleanup(shutil.rmtree, self.folder)
		self.enterContext(
			patch("frappe.desk.doctype.form_layout.app_layout.app_layout_path", side_effect=self.path)
		)
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 1}))
		for method in (
			"export_doc",
			"make_controller_template",
			"set_base_class_for_controller",
			"export_types_to_controller",
		):
			self.enterContext(patch(f"frappe.core.doctype.doctype.doctype.DocType.{method}"))
		self.addCleanup(restore_modified, "ToDo", frappe.db.get_value("DocType", "ToDo", "modified"))
		self.addCleanup(frappe.db.rollback)

	def path(self, dt: str, type: str) -> str:
		return os.path.join(self.folder, f"{frappe.scrub(type)}.json")

	def test_a_standard_doctype_writes_its_app_layout_file(self):
		result = save_doctype_editor(
			"ToDo",
			"Design",
			base_version("ToDo"),
			[{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "extra_47271"}],
		)
		self.assertTrue(result["saved"], result.get("errors"))
		with open(self.path("ToDo", "Details")) as f:
			[entry] = json.load(f)
		self.assertEqual(entry["layout"][-1]["name"], "extra_47271")
		self.assertTrue(result["base_version"]["app_layouts"]["Details"])
		self.assertFalse(
			frappe.get_all("Form Layout", {"dt": "ToDo", "type": "Details", "app": ("is", "not set")})
		)

	def test_a_deferred_export_reports_the_new_app_layout_version(self):
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		frappe.local.request = frappe._dict(after_response=CallbackManager())
		result = save_doctype_editor(
			"ToDo",
			"Design",
			base_version("ToDo"),
			[{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "extra_47271"}],
		)
		self.assertTrue(result["saved"], result.get("errors"))
		self.assertFalse(os.path.exists(self.path("ToDo", "Details")))

		with patch.object(frappe, "publish_realtime") as publish:
			frappe.local.request.after_response.run()
		[message] = [c.args[1] for c in publish.call_args_list if c.args[0] == "doctype_export"]
		self.assertTrue(message["ok"], message["error"])
		self.assertEqual(message["app_layouts"], {"Details": base_version("ToDo")["app_layouts"]["Details"]})

	def test_writing_the_files_again_keeps_a_failed_export_s_layouts(self):
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		self.addCleanup(frappe.cache.delete_value, frappe.get_doc("DocType", "ToDo").staged_app_layouts_key())
		frappe.local.request = frappe._dict(after_response=CallbackManager())
		result = save_doctype_editor(
			"ToDo",
			"Design",
			base_version("ToDo"),
			[{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "extra_47271"}],
		)
		self.assertTrue(result["saved"], result.get("errors"))
		with patch(
			"frappe.core.doctype.doctype.doctype.DocType.export_doc", side_effect=OSError("disk full")
		):
			with self.assertRaises(OSError):
				frappe.local.request.after_response.run()
		self.assertFalse(os.path.exists(self.path("ToDo", "Details")))

		versions = write_doctype_files("ToDo")
		with open(self.path("ToDo", "Details")) as f:
			[entry] = json.load(f)
		self.assertEqual(entry["layout"][-1]["name"], "extra_47271")
		self.assertEqual(versions, base_version("ToDo")["app_layouts"], "the client's next base version")

	def test_an_export_staging_nothing_leaves_the_app_layouts_alone(self):
		doc = frappe.get_doc("DocType", "ToDo")
		layout = [{"name": "details", "sections": [{"name": "s", "columns": [{"name": "c", "fields": []}]}]}]
		frappe.cache.set_value(doc.staged_app_layouts_key(), {"Details": [{"layout": layout}]})
		self.addCleanup(frappe.cache.delete_value, doc.staged_app_layouts_key())
		doc.export_files()
		self.assertFalse(os.path.exists(self.path("ToDo", "Details")))

	def test_an_app_layout_cannot_place_a_site_custom_field(self):
		fieldname = "custom_editor_47271"
		frappe.get_doc(
			{
				"doctype": "Custom Field",
				"dt": "ToDo",
				"fieldname": fieldname,
				"label": "Editor 47271",
				"fieldtype": "Data",
			}
		).insert()
		self.addCleanup(drop_column, "ToDo", fieldname)
		self.addCleanup(delete_committed, "Custom Field", f"ToDo-{fieldname}")
		result = save_doctype_editor(
			"ToDo",
			"Design",
			base_version("ToDo"),
			[
				{
					"act": "canvas.place_field",
					"layout": {"type": "Details"},
					"fieldname": fieldname,
					"column": "column_1",
				}
			],
		)
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "field", "fieldname": fieldname})
		self.assertIn("site custom field", result["errors"][0]["message"])
		self.assertFalse(os.path.exists(self.path("ToDo", "Details")))
