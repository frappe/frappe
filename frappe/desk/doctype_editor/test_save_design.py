# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
import os
import shutil
import tempfile
from unittest.mock import patch

import frappe
from frappe.desk.doctype_editor.rename import rename_field
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


def delete_committed(doctype: str, name: str):
	"""Its insert's DDL committed, and the class's rollback runs after this cleanup."""
	frappe.delete_doc(doctype, name, force=True, ignore_missing=True)
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
		self.addCleanup(frappe.delete_doc, "DocType", child, force=True, ignore_missing=True)
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
		self.assertEqual(result.get("written"), [])
		self.assertFalse(frappe.get_meta(DOCTYPE).get_field("due"))
		self.assertEqual(details_rows(), [])

	def test_a_layout_failing_after_the_doctype_saved_reports_what_was_written(self):
		result = self.save(
			[
				{"act": "fields.add_field", "label": "Due", "fieldtype": "Date"},
				{"act": "canvas.add_tab", "layout": {"type": "Details"}, "name": "due"},
			]
		)
		self.assertFalse(result["saved"])
		self.assertEqual(result["written"], [DOCTYPE])
		self.assertTrue(frappe.get_meta(DOCTYPE).get_field("due"))
		self.assertEqual(details_rows(), [])

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
		self.addCleanup(frappe.db.sql_ddl, f"alter table `tabToDo` drop column if exists {fieldname}")
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
