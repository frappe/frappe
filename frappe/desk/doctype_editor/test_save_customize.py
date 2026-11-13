# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.custom.doctype.customize_form.customize_form import CustomizeForm
from frappe.desk.doctype.form_layout.app_layout import read_app_layouts
from frappe.desk.doctype.form_layout.form_layout import parse_layout, source_fingerprint
from frappe.desk.doctype_editor.customize import get_customizations
from frappe.desk.doctype_editor.customize_acts import customization_rows, export, reset_all
from frappe.desk.doctype_editor.save import save_doctype_editor
from frappe.desk.doctype_editor.versions import base_version
from frappe.tests import IntegrationTestCase

# Note renders Details from its breaks; Contact ships New Record and Quick Entry layout files.
NOTE, CONTACT = "Note", "Contact"
CHILD = "T47273 Customize Row"
SITE_ROWS = ("Custom Field", "Property Setter", "Form Layout")


def save(doctype: str, edits: list, version: dict | None = None) -> dict:
	return save_doctype_editor(doctype, "Customize", version or base_version(doctype), edits)


def rows_of(doctype: str, dt: str) -> set[str]:
	key = "doc_type" if doctype == "Property Setter" else "dt"
	return set(frappe.get_all(doctype, filters={key: dt}, pluck="name"))


def custom_field(dt: str, fieldname: str):
	return frappe.db.get_value(
		"Custom Field", {"dt": dt, "fieldname": fieldname}, ["name", "insert_after", "label"], as_dict=True
	)


def property_value(dt: str, fieldname: str, property: str):
	return frappe.db.get_value(
		"Property Setter", {"doc_type": dt, "field_name": fieldname, "property": property}, "value"
	)


def site_layouts(dt: str, type: str = "Details") -> list:
	return frappe.get_all(
		"Form Layout",
		filters={"dt": dt, "type": type, "app": ("is", "not set")},
		fields=["name", "layout", "fingerprint", "condition"],
	)


def add_field(label: str, **place) -> dict:
	return {"act": "fields.add_field", "label": label, "fieldtype": "Data", **place}


def rename(old: str, new: str) -> dict:
	return {"act": "fields.rename_field", "fieldname": old, "new_fieldname": new}


class TestSaveCustomize(IntegrationTestCase):
	"""Customize Form's DDL commits, so each test deletes what it made and commits."""

	def setUp(self):
		self.before = {(doctype, dt): rows_of(doctype, dt) for doctype in SITE_ROWS for dt in (NOTE, CONTACT)}

	def tearDown(self):
		frappe.db.rollback()
		for (doctype, dt), names in self.before.items():
			for name in rows_of(doctype, dt) - names:
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		if frappe.db.exists("DocType", CHILD):
			frappe.delete_doc("DocType", CHILD, force=True, ignore_permissions=True)
		for dt in (NOTE, CONTACT):
			for column in frappe.db.get_table_columns(dt):
				if column.startswith("custom_t47273"):
					frappe.db.sql_ddl(f"alter table `tab{dt}` drop column `{column}`")
			frappe.clear_cache(doctype=dt)
		frappe.db.commit()  # nosemgrep

	def test_add_field_anchors_after_the_field_drawn_before_it(self):
		result = save(
			NOTE,
			[
				add_field(
					"T47273 Code", layout={"type": "Details"}, section="section_1", column="column_1", index=1
				)
			],
		)
		self.assertTrue(result["saved"], result)
		self.assertEqual(custom_field(NOTE, "custom_t47273_code").insert_after, "title")
		self.assertFalse(site_layouts(NOTE))

	def test_add_field_first_in_a_column_anchors_on_the_column(self):
		save(
			NOTE,
			[
				add_field(
					"T47273 Top", layout={"type": "Details"}, section="section_1", column="column_1", index=0
				)
			],
		)
		self.assertEqual(custom_field(NOTE, "custom_t47273_top").insert_after, "column_1")
		save(
			NOTE, [{"act": "fields.set_field_property", "fieldname": "title", "property": "bold", "value": 1}]
		)
		self.assertEqual(custom_field(NOTE, "custom_t47273_top").insert_after, "column_1")

	def test_property_change_makes_a_property_setter_and_its_reset_deletes_it(self):
		edit = {"act": "fields.set_field_property", "fieldname": "title", "property": "label"}
		self.assertTrue(save(NOTE, [{**edit, "value": "T47273 Heading"}])["saved"])
		self.assertEqual(property_value(NOTE, "title", "label"), "T47273 Heading")
		self.assertEqual(frappe.get_meta(NOTE).get_field("title").label, "T47273 Heading")
		reset = {"act": "fields.reset_field_property", "fieldname": "title", "property": "label"}
		self.assertTrue(save(NOTE, [reset])["saved"])
		self.assertIsNone(property_value(NOTE, "title", "label"))

	def test_a_standard_field_is_hidden_never_deleted(self):
		result = save(NOTE, [{"act": "fields.delete_field", "fieldname": "content"}])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "field", "fieldname": "content"})
		hide = {"act": "fields.set_field_property", "fieldname": "content", "property": "hidden", "value": 1}
		result = save(NOTE, [hide])
		self.assertTrue(result["saved"], result)
		self.assertEqual(property_value(NOTE, "content", "hidden"), "1")

	def test_a_site_custom_field_renames_and_deletes(self):
		save(NOTE, [add_field("T47273 Old")])
		rename = {
			"act": "fields.rename_field",
			"fieldname": "custom_t47273_old",
			"new_fieldname": "custom_t47273_new",
		}
		self.assertTrue(save(NOTE, [rename])["saved"])
		self.assertIsNone(custom_field(NOTE, "custom_t47273_old"))
		self.assertEqual(custom_field(NOTE, "custom_t47273_new").label, "T47273 Old")
		self.assertTrue(
			save(NOTE, [{"act": "fields.delete_field", "fieldname": "custom_t47273_new"}])["saved"]
		)
		self.assertIsNone(custom_field(NOTE, "custom_t47273_new"))

	def test_a_custom_field_keeps_its_custom_prefix_on_rename(self):
		save(NOTE, [add_field("T47273 Prefix")])
		result = save(NOTE, [rename("custom_t47273_prefix", "t47273_prefix")])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"]["fieldname"], "custom_t47273_prefix")
		self.assertIsNotNone(custom_field(NOTE, "custom_t47273_prefix"))

	def test_a_rename_or_delete_moves_the_anchors_on_it(self):
		save(NOTE, [add_field("T47273 A"), add_field("T47273 B")])
		frappe.db.set_value(
			"Custom Field", custom_field(NOTE, "custom_t47273_b").name, "insert_after", "custom_t47273_a"
		)
		self.assertTrue(save(NOTE, [rename("custom_t47273_a", "custom_t47273_c")])["saved"])
		self.assertEqual(custom_field(NOTE, "custom_t47273_b").insert_after, "custom_t47273_c")
		self.assertTrue(save(NOTE, [{"act": "fields.delete_field", "fieldname": "custom_t47273_c"}])["saved"])
		self.assertNotIn(
			custom_field(NOTE, "custom_t47273_b").insert_after, ("custom_t47273_a", "custom_t47273_c")
		)

	def test_a_failed_write_reports_only_what_committed(self):
		bold = {"act": "fields.set_field_property", "fieldname": "title", "property": "bold", "value": 1}
		refused = patch.object(
			CustomizeForm, "save_customization", side_effect=frappe.ValidationError("T47273")
		)
		with refused:
			result = save(NOTE, [bold])
		self.assertFalse(result["saved"])
		self.assertEqual(result["written"], [])
		save(NOTE, [add_field("T47273 Old")])
		with refused:
			result = save(NOTE, [rename("custom_t47273_old", "custom_t47273_new")])
		self.assertEqual(result["written"], [NOTE])
		self.assertIsNotNone(custom_field(NOTE, "custom_t47273_new"))

	def test_a_custom_field_anchors_by_the_fallback_drawn_with_the_sites_custom_fields(self):
		place = {"layout": {"type": "Details"}, "section": "section_1", "column": "column_1"}
		self.assertTrue(save(NOTE, [add_field("T47273 A", **place, index=1)])["saved"])
		self.assertTrue(save(NOTE, [add_field("T47273 B", **place, index=2)])["saved"])
		self.assertEqual(custom_field(NOTE, "custom_t47273_b").insert_after, "custom_t47273_a")

	def test_a_standard_move_takes_the_anchor_of_the_custom_field_drawn_after_it(self):
		place = {"layout": {"type": "Details"}, "section": "section_1", "column": "column_1"}
		self.assertTrue(save(NOTE, [add_field("T47273 A", **place, index=1)])["saved"])
		move = {"act": "canvas.move_field", "fieldname": "content", **place, "index": 1}
		self.assertTrue(save(NOTE, [move])["saved"])
		self.assertEqual(custom_field(NOTE, "custom_t47273_a").insert_after, "content")
		self.assertEqual(json.loads(property_value(NOTE, None, "field_order"))[:2], ["title", "content"])

	def test_a_renamed_custom_table_keeps_its_rows(self):
		table = {
			"act": "fields.add_field",
			"label": "T47273 Seen",
			"fieldtype": "Table",
			"options": "Note Seen By",
		}
		self.assertTrue(save(NOTE, [table])["saved"])
		note = frappe.get_doc(
			{"doctype": NOTE, "title": "T47273 Note", "custom_t47273_seen": [{"user": "Administrator"}]}
		).insert()
		try:
			result = save(NOTE, [rename("custom_t47273_seen", "custom_t47273_readers")])
			self.assertTrue(result["saved"], result)
			self.assertEqual(len(frappe.get_doc(NOTE, note.name).get("custom_t47273_readers")), 1)
		finally:
			frappe.delete_doc(NOTE, note.name, force=True)
			# tearDown rolls back first, so commit the delete
			frappe.db.commit()  # nosemgrep

	def test_a_new_child_table_takes_design_edits(self):
		table = {"act": "fields.add_child_table", "name": CHILD, "table_field": "custom_t47273_rows"}
		result = save(NOTE, {NOTE: [table], CHILD: [add_field("T47273 Item")]})
		self.assertTrue(result["saved"], result)
		self.assertTrue(frappe.db.exists("DocField", {"parent": CHILD, "fieldname": "t47273_item"}))

	def test_a_changed_app_layout_makes_a_save_on_it_stale(self):
		version = base_version(CONTACT)
		version["app_layouts"]["New Record"] = "t47273"
		layout = parse_layout(read_app_layouts(CONTACT, "New Record").entries[0].layout)
		section = layout[0]["sections"][0]
		place = {"section": section["name"], "column": section["columns"][0]["name"], "index": 0}
		result = save(CONTACT, [add_field("T47273 Late", layout={"type": "New Record"}, **place)], version)
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["code"], "stale")

	def test_a_skipped_change_does_not_reach_the_field_checks(self):
		edit = {
			"act": "fields.set_field_property",
			"fieldname": "seen_by_section",
			"property": "in_list_view",
		}
		result = save(NOTE, [{**edit, "value": 1}])
		self.assertTrue(result["saved"], result)
		self.assertEqual(result["skipped"][0]["target"]["property"], "in_list_view")
		self.assertIsNone(property_value(NOTE, "seen_by_section", "in_list_view"))

	def test_a_select_turned_data_takes_new_options(self):
		edit = {"act": "fields.set_field_property", "fieldname": "status"}
		result = save(
			CONTACT,
			[
				{**edit, "property": "fieldtype", "value": "Data"},
				{**edit, "property": "options", "value": ""},
			],
		)
		self.assertTrue(result["saved"], result)
		self.assertFalse(result.get("skipped"))
		self.assertEqual(property_value(CONTACT, "status", "fieldtype"), "Data")
		self.assertEqual(property_value(CONTACT, "status", "options"), "")

	def test_a_system_manager_saves_and_only_a_system_manager_renames(self):
		with self.set_user("test@example.com"):
			self.assertTrue(save(NOTE, [add_field("T47273 Mine")])["saved"])
			self.assertTrue(save(NOTE, [rename("custom_t47273_mine", "custom_t47273_ours")])["saved"])
			with (
				patch("frappe.desk.doctype_editor.save.check_mode"),
				patch("frappe.get_roles", return_value=[]),
			):
				result = save(NOTE, [rename("custom_t47273_ours", "custom_t47273_theirs")])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"]["fieldname"], "custom_t47273_theirs")
		self.assertIsNotNone(custom_field(NOTE, "custom_t47273_ours"))

	def test_a_standard_field_cannot_be_renamed(self):
		rename = {"act": "fields.rename_field", "fieldname": "title", "new_fieldname": "t47273_title"}
		result = save(NOTE, [rename])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"]["fieldname"], "title")

	def test_a_standard_move_on_a_break_rendered_doctype_writes_field_order(self):
		move = {"act": "canvas.move_field", "fieldname": "content", "layout": {"type": "Details"}}
		self.assertTrue(
			save(NOTE, [{**move, "section": "section_1", "column": "column_1", "index": 0}])["saved"]
		)
		self.assertEqual(json.loads(property_value(NOTE, None, "field_order"))[:2], ["content", "title"])
		self.assertFalse(site_layouts(NOTE))

	def test_a_container_edit_forks_a_site_layout_with_its_fingerprint(self):
		add = {
			"act": "canvas.add_section",
			"layout": {"type": "Details"},
			"tab": "first_tab",
			"name": "t47273",
		}
		self.assertTrue(save(NOTE, [add])["saved"])
		(row,) = site_layouts(NOTE)
		self.assertEqual(row.fingerprint, source_fingerprint(NOTE, "Details"))
		self.assertIn("t47273", [section["name"] for section in json.loads(row.layout)[0]["sections"]])

	def test_rules_fetch_and_link_filters_on_standard_fields_make_property_setters(self):
		properties = {
			"depends_on": "eval:doc.first_name",
			"mandatory_depends_on": "eval:doc.user",
			"read_only_depends_on": "eval:!doc.__islocal",
			"fetch_from": "user.full_name",
			"fetch_if_empty": "1",
		}
		filters = '[["User","enabled","=",1]]'
		edits = [
			{"act": "fields.set_field_property", "fieldname": "designation", "property": key, "value": value}
			for key, value in properties.items()
		]
		edits.append(
			{
				"act": "fields.set_field_property",
				"fieldname": "user",
				"property": "link_filters",
				"value": filters,
			}
		)
		result = save(CONTACT, edits)
		self.assertTrue(result["saved"], result)
		self.assertFalse(result.get("skipped"), result)
		saved = {key: property_value(CONTACT, "designation", key) for key in properties}
		self.assertEqual(saved, properties)
		self.assertEqual(property_value(CONTACT, "user", "link_filters"), filters)

	def test_container_rules_fork_into_the_site_layout(self):
		details = {"type": "Details"}
		rule = {"act": "canvas.set_container_property", "layout": details, "value": "eval:doc.public"}
		edits = [
			{"act": "canvas.add_section", "layout": details, "tab": "first_tab", "name": "t47273"},
			{**rule, "container": "first_tab", "property": "dependsOn"},
			{**rule, "container": "t47273", "property": "dependsOn"},
			{**rule, "container": "t47273", "property": "collapsibleDependsOn"},
			{**rule, "container": "column_1", "section": "t47273", "property": "dependsOn"},
		]
		self.assertTrue(save(NOTE, edits)["saved"])
		(row,) = site_layouts(NOTE)
		tab = json.loads(row.layout)[0]
		[section] = [each for each in tab["sections"] if each["name"] == "t47273"]
		rules = (tab, section, section["columns"][0])
		self.assertEqual([each["dependsOn"] for each in rules], ["eval:doc.public"] * 3)
		self.assertEqual(section["collapsibleDependsOn"], "eval:doc.public")

	def test_a_quick_entry_placement_forks_the_app_layout(self):
		tab = parse_layout(read_app_layouts(CONTACT, "Quick Entry").entries[0].layout)[0]["name"]
		place = {"act": "canvas.place_field", "fieldname": "designation", "tab": tab}
		self.assertTrue(save(CONTACT, [{**place, "layout": {"type": "Quick Entry"}}])["saved"])
		(row,) = site_layouts(CONTACT, "Quick Entry")
		self.assertIn("designation", row.layout)
		self.assertEqual(row.fingerprint, source_fingerprint(CONTACT, "Quick Entry"))

	def test_a_custom_field_on_an_app_layout_is_anchored_without_a_fork(self):
		layout = parse_layout(read_app_layouts(CONTACT, "New Record").entries[0].layout)
		column = layout[0]["sections"][0]["columns"][0]
		section = layout[0]["sections"][0]["name"]
		place = {"layout": {"type": "New Record"}, "section": section, "column": column["name"], "index": 1}
		result = save(CONTACT, [add_field("T47273 Badge", **place)])
		self.assertTrue(result["saved"], result)
		self.assertEqual(custom_field(CONTACT, "custom_t47273_badge").insert_after, column["fields"][0])
		self.assertFalse(site_layouts(CONTACT, "New Record"))

	def test_reset_to_app_removes_every_site_row_of_the_type(self):
		add = {
			"act": "canvas.add_section",
			"layout": {"type": "Details"},
			"tab": "first_tab",
			"name": "t47273",
		}
		save(NOTE, [add, {"act": "layouts.add", "type": "Details", "id": "new", "condition": "doc.public"}])
		self.assertEqual(len(site_layouts(NOTE)), 2)
		self.assertTrue(save(NOTE, [{"act": "layouts.reset_to_app", "type": "Details"}])["saved"])
		self.assertFalse(site_layouts(NOTE))

	def test_a_blocking_refusal_stops_the_save_keyed_to_field_and_property(self):
		edit = {"act": "fields.set_field_property", "fieldname": "title", "property": "fieldtype"}
		result = save(NOTE, [{**edit, "value": "Table"}])
		self.assertFalse(result["saved"])
		self.assertEqual(
			result["errors"][0]["target"], {"kind": "field", "fieldname": "title", "property": "fieldtype"}
		)
		self.assertIsNone(property_value(NOTE, "title", "fieldtype"))

	def test_an_app_made_layout_is_refused(self):
		row = frappe.get_doc({"doctype": "Form Layout", "dt": NOTE, "type": "Details", "app": "frappe"})
		row.db_insert()
		result = save(NOTE, [add_field("T47273 App", layout={"type": "Details", "id": row.name}, index=0)])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "layout", "layout": row.name})

	def test_a_changed_customization_makes_the_save_stale(self):
		version = base_version(NOTE)
		save(
			NOTE, [{"act": "fields.set_field_property", "fieldname": "title", "property": "bold", "value": 1}]
		)
		result = save(NOTE, [add_field("T47273 Late")], version)
		self.assertEqual(result["errors"][0]["code"], "stale")
		self.assertIsNone(custom_field(NOTE, "custom_t47273_late"))

	def test_reset_all_counts_first_then_deletes_and_keeps_system_rows(self):
		if any(self.before[(doctype, NOTE)] for doctype in SITE_ROWS):
			self.skipTest("Reset all would delete this site's own Note customizations.")
		save(NOTE, [add_field("T47273 Gone")])
		save(
			NOTE, [{"act": "fields.set_field_property", "fieldname": "title", "property": "bold", "value": 1}]
		)
		kept = frappe.get_doc(
			{"doctype": "Custom Field", "dt": NOTE, "label": "T47273 Kept", "fieldtype": "Data"}
		)
		kept.is_system_generated = 1
		kept.insert()
		counts = reset_all(NOTE)
		self.assertGreaterEqual(counts["delete"]["custom_fields"], 1)
		self.assertGreaterEqual(counts["keep"]["custom_fields"], 1)
		self.assertIsNotNone(custom_field(NOTE, "custom_t47273_gone"))
		reset_all(NOTE, confirm=1)
		self.assertIsNone(custom_field(NOTE, "custom_t47273_gone"))
		self.assertIsNone(property_value(NOTE, "title", "bold"))
		self.assertIsNotNone(custom_field(NOTE, "custom_t47273_kept"))

	def test_a_non_blocking_refusal_saves_and_comes_back_skipped(self):
		edit = {"act": "fields.set_field_property", "fieldname": "title", "property": "reqd", "value": 0}
		result = save(NOTE, [edit])
		self.assertTrue(result["saved"], result)
		self.assertEqual(result["skipped"][0]["target"]["fieldname"], "title")
		self.assertIsNone(property_value(NOTE, "title", "reqd"))

	def test_a_reset_keeps_a_property_setter_an_app_made(self):
		frappe.make_property_setter(
			{"doctype": NOTE, "fieldname": "title", "property": "bold", "value": 1, "property_type": "Check"}
		)
		reset = {"act": "fields.reset_field_property", "fieldname": "title", "property": "bold"}
		self.assertTrue(save(NOTE, [reset])["saved"])
		self.assertEqual(property_value(NOTE, "title", "bold"), "1")

	def test_a_reset_on_an_app_custom_field_restores_its_own_value(self):
		app_field = frappe.get_doc(
			{"doctype": "Custom Field", "dt": NOTE, "label": "T47273 App Made", "fieldtype": "Data"}
		)
		app_field.is_system_generated = 1
		app_field.insert()
		edit = {"act": "fields.set_field_property", "fieldname": app_field.fieldname, "property": "label"}
		self.assertTrue(save(NOTE, [{**edit, "value": "T47273 Site Label"}])["saved"])
		self.assertEqual(property_value(NOTE, app_field.fieldname, "label"), "T47273 Site Label")
		setters = get_customizations(frappe.get_meta(NOTE))["property_setters"]
		setter = next(row for row in setters if row.field_name == app_field.fieldname)
		self.assertEqual(setter.app_value, "T47273 App Made")
		reset = {"act": "fields.reset_field_property", "fieldname": app_field.fieldname, "property": "label"}
		self.assertTrue(save(NOTE, [reset])["saved"])
		self.assertIsNone(property_value(NOTE, app_field.fieldname, "label"))
		self.assertEqual(frappe.get_meta(NOTE).get_field(app_field.fieldname).label, "T47273 App Made")

	def test_an_edit_after_a_reset_on_an_app_custom_field_wins(self):
		app_field = frappe.get_doc(
			{"doctype": "Custom Field", "dt": NOTE, "label": "T47274 App Made", "fieldtype": "Data"}
		)
		app_field.is_system_generated = 1
		app_field.insert()
		edit = {"act": "fields.set_field_property", "fieldname": app_field.fieldname, "property": "label"}
		self.assertTrue(save(NOTE, [{**edit, "value": "T47274 Site Label"}])["saved"])
		reset = {"act": "fields.reset_field_property", "fieldname": app_field.fieldname, "property": "label"}
		self.assertTrue(save(NOTE, [reset, {**edit, "value": "T47274 Later Label"}])["saved"])
		self.assertEqual(property_value(NOTE, app_field.fieldname, "label"), "T47274 Later Label")
		self.assertEqual(frappe.get_meta(NOTE).get_field(app_field.fieldname).label, "T47274 Later Label")

	def test_reset_all_keeps_the_fields_only_administrator_may_delete(self):
		save(NOTE, [add_field("T47273 Admin")])
		name = custom_field(NOTE, "custom_t47273_admin").name
		with patch.dict(frappe.session, {"user": "Guest"}):
			delete, keep = customization_rows(NOTE)
		self.assertIn(name, keep["custom_fields"])
		self.assertNotIn(name, delete["custom_fields"])

	def test_without_customize_form_write_every_act_is_refused(self):
		version = base_version(NOTE)
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.PermissionError, save, NOTE, [add_field("T47273 No")], version)
			self.assertRaises(frappe.PermissionError, reset_all, NOTE)
			self.assertRaises(frappe.PermissionError, export, NOTE, "Desk")
		finally:
			frappe.set_user("Administrator")

	def test_settings_acts_wait_for_their_own_ticket(self):
		edit = {"act": "settings.set_doctype_property", "property": "description", "value": "T47273"}
		result = save(NOTE, [edit])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["edit"], 0)

	def test_export_needs_developer_mode(self):
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			self.assertRaises(frappe.PermissionError, export, NOTE, "Desk")
