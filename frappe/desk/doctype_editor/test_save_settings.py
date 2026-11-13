# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.desk.doctype_editor.create import create_doctype
from frappe.desk.doctype_editor.load import get_doctype_editor
from frappe.desk.doctype_editor.mode import permissions_refusal
from frappe.desk.doctype_editor.save import save_doctype_editor
from frappe.desk.doctype_editor.test_load import CUSTOMIZER, a_customizer_role, a_user
from frappe.desk.doctype_editor.test_save_design import DOCTYPE, delete_committed, make_custom_doctype
from frappe.desk.doctype_editor.versions import base_version
from frappe.permissions import copy_perms
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

NOTE = "Note"
CREATED = "Test Editor 47277 New"
SERIES_FIELD = {"fieldname": "naming_series", "label": "Series", "fieldtype": "Select", "options": "T-.###"}


def prop(property: str, value) -> dict:
	return {"act": "settings.set_doctype_property", "property": property, "value": value}


def perm(right: str, value: int = 1, role: str = "System Manager", **row) -> dict:
	return {"act": "settings.set_permission", "role": role, "right": right, "value": value, **row}


def doc_perm(doctype: str, dt: str, role: str = "System Manager", if_owner: int = 0) -> dict:
	filters = {"parent": dt, "role": role, "permlevel": 0, "if_owner": if_owner}
	return frappe.db.get_value(doctype, filters, "*", as_dict=True)


class TestSaveSettingsDesign(IntegrationTestCase):
	def setUp(self):
		make_custom_doctype()
		self.addCleanup(frappe.delete_doc, "DocType", DOCTYPE, force=True, ignore_missing=True)

	def save(self, edits: list) -> dict:
		return save_doctype_editor(DOCTYPE, "Design", base_version(DOCTYPE), edits)

	def test_form_and_list_properties_are_set(self):
		result = self.save(
			[prop("title_field", "title"), prop("search_fields", "title"), prop("track_changes", 1)]
		)
		self.assertTrue(result["saved"], result)
		saved = frappe.db.get_value("DocType", DOCTYPE, ["title_field", "search_fields", "track_changes"])
		self.assertEqual(saved, ("title", "title", 1))

	def test_the_kind_of_a_saved_doctype_is_refused(self):
		result = self.save([prop("istable", 1)])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "setting", "property": "istable"})

	def test_a_naming_pattern_is_saved(self):
		result = self.save([prop("naming_rule", "Expression"), prop("autoname", "format:T-{#####}")])
		self.assertTrue(result["saved"], result)
		self.assertEqual(frappe.db.get_value("DocType", DOCTYPE, "autoname"), "format:T-{#####}")

	def test_number_in_order_is_refused_while_records_exist(self):
		frappe.get_doc({"doctype": DOCTYPE, "title": "One"}).insert()
		result = self.save([prop("naming_rule", "Autoincrement"), prop("autoname", "autoincrement")])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["edit"], 1)
		self.assertIn("records", result["errors"][0]["message"])

	def test_the_naming_series_list_adds_its_field(self):
		edits = [
			prop("naming_rule", 'By "Naming Series" field'),
			prop("autoname", "naming_series:"),
			{"act": "settings.set_naming_series", "options": ["T-.####", "U-.####"], "default": "U-.####"},
		]
		result = self.save(edits)
		self.assertTrue(result["saved"], result)
		field = frappe.get_meta(DOCTYPE, cached=False).get_field("naming_series")
		self.assertEqual((field.options, field.default), ("T-.####\nU-.####", "U-.####"))

	def test_a_role_gets_read_and_write(self):
		result = self.save(
			[
				{"act": "settings.add_permission", "role": "Blogger"},
				perm("write", role="Blogger"),
			]
		)
		self.assertTrue(result["saved"], result)
		row = doc_perm("DocPerm", DOCTYPE, "Blogger")
		self.assertEqual((row.read, row.write, row.create), (1, 1, 0))

	def test_a_right_ticks_its_prerequisites_and_unticks_its_dependents(self):
		frappe.db.set_value("DocType", DOCTYPE, "is_submittable", 1)
		result = self.save([perm("cancel"), perm("amend")])
		self.assertTrue(result["saved"], result)
		row = doc_perm("DocPerm", DOCTYPE)
		self.assertEqual((row.write, row.submit, row.cancel, row.amend), (1, 1, 1, 1))
		result = self.save([perm("write", 0)])
		self.assertTrue(result["saved"], result)
		row = doc_perm("DocPerm", DOCTYPE)
		self.assertEqual((row.read, row.write, row.submit, row.cancel, row.amend), (1, 0, 0, 0, 0))

	def test_a_role_is_removed(self):
		result = self.save([{"act": "settings.remove_permission", "role": "System Manager"}])
		self.assertTrue(result["saved"], result)
		self.assertIsNone(doc_perm("DocPerm", DOCTYPE))

	def test_a_second_row_for_the_same_role_and_level_is_refused(self):
		result = self.save([{"act": "settings.add_permission", "role": "System Manager"}])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"]["kind"], "setting")


class TestCreateWithSettings(IntegrationTestCase):
	def tearDown(self):
		delete_committed("DocType", CREATED)

	def test_a_new_doctype_takes_its_kind_from_the_settings(self):
		definition = {"name": CREATED, "module": "Custom", "custom": 1, "fields": [SERIES_FIELD]}
		result = create_doctype(
			definition, None, [prop("is_submittable", 1), prop("title_field", "naming_series")]
		)
		self.assertTrue(result["saved"], result)
		saved = frappe.db.get_value("DocType", CREATED, ["is_submittable", "title_field"])
		self.assertEqual(saved, (1, "naming_series"))


class TestSaveSettingsCustomize(IntegrationTestCase):
	"""Customize Form's DDL commits, so each test removes what it wrote and commits."""

	def setUp(self):
		self.setters = set(frappe.get_all("Property Setter", {"doc_type": NOTE}, pluck="name"))

	def tearDown(self):
		frappe.db.rollback()
		for name in set(frappe.get_all("Property Setter", {"doc_type": NOTE}, pluck="name")) - self.setters:
			frappe.delete_doc("Property Setter", name, force=True, ignore_permissions=True)
		frappe.db.delete("Custom DocPerm", {"parent": NOTE})
		frappe.clear_cache(doctype=NOTE)
		frappe.db.commit()  # nosemgrep

	def save(self, edits: list) -> dict:
		return save_doctype_editor(NOTE, "Customize", base_version(NOTE), edits)

	def setter(self, property: str):
		filters = {"doc_type": NOTE, "doctype_or_field": "DocType", "property": property}
		return frappe.db.get_value("Property Setter", filters, "value")

	def test_a_property_is_set_and_reset_through_a_property_setter(self):
		result = self.save([prop("track_changes", 0)])
		self.assertTrue(result["saved"], result)
		self.assertEqual(self.setter("track_changes"), "0")
		result = self.save([{"act": "settings.reset_doctype_property", "property": "track_changes"}])
		self.assertTrue(result["saved"], result)
		self.assertIsNone(self.setter("track_changes"))

	def test_a_property_customize_form_does_not_set_is_refused(self):
		result = self.save([prop("allow_rename", 0)])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "setting", "property": "allow_rename"})

	def test_number_in_order_is_refused(self):
		result = self.save([prop("autoname", "autoincrement")])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"]["property"], "autoname")

	def test_a_first_edit_copies_the_app_rows_and_a_reset_removes_them(self):
		app_roles = set(frappe.get_all("DocPerm", {"parent": NOTE}, pluck="role"))
		result = self.save([perm("export", role="Desk User", if_owner=1)])
		self.assertTrue(result["saved"], result)
		self.assertEqual(set(frappe.get_all("Custom DocPerm", {"parent": NOTE}, pluck="role")), app_roles)
		self.assertEqual(doc_perm("Custom DocPerm", NOTE, "Desk User", if_owner=1).export, 1)
		self.assertEqual(frappe.get_meta(NOTE, cached=False).get_permissions()[0].doctype, "Custom DocPerm")
		result = self.save([{"act": "settings.reset_permissions"}])
		self.assertTrue(result["saved"], result)
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": NOTE}))

	def test_an_invalid_right_is_refused_before_the_write(self):
		result = self.save([perm("submit", role="Desk User")])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "setting", "property": "permissions"})
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": NOTE}))

	def test_a_permission_edit_by_someone_else_makes_the_save_stale(self):
		version = base_version(NOTE)
		self.save([perm("export", role="Desk User", if_owner=1)])
		result = save_doctype_editor(
			NOTE, "Customize", version, [perm("print", role="Desk User", if_owner=1)]
		)
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["code"], "stale")

	def test_a_customizer_without_system_manager_cannot_change_permissions(self):
		"""The refused saves write nothing, so the tearDown's rollback removes the customizer."""
		customizer = a_user(CUSTOMIZER, a_customizer_role())
		with set_user(customizer):
			self.assertEqual(get_doctype_editor(NOTE, "Customize")["permissions_refusal"], permissions_refusal())
			for edit in (perm("export", role="Desk User", if_owner=1), {"act": "settings.reset_permissions"}):
				result = self.save([edit])
				self.assertFalse(result["saved"])
				self.assertEqual(result["errors"][0]["target"], {"kind": "setting", "property": "permissions"})
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": NOTE}))
		self.assertIsNone(get_doctype_editor(NOTE, "Customize")["permissions_refusal"])

	def test_an_edit_keeps_mask_and_the_rows_it_did_not_change(self):
		copy_perms(NOTE)
		masked = doc_perm("Custom DocPerm", NOTE).name
		frappe.db.set_value("Custom DocPerm", masked, "mask", 1)
		before = set(frappe.get_all("Custom DocPerm", {"parent": NOTE}, pluck="name"))
		with patch("frappe.desk.doctype_editor.customize_save.clear_permissions_cache") as clear:
			result = self.save([perm("export", role="Desk User", if_owner=1)])
		self.assertTrue(result["saved"], result)
		clear.assert_called_once_with(NOTE)
		self.assertEqual(set(frappe.get_all("Custom DocPerm", {"parent": NOTE}, pluck="name")), before)
		self.assertEqual(frappe.db.get_value("Custom DocPerm", masked, "mask"), 1)
		self.assertEqual(doc_perm("Custom DocPerm", NOTE, "Desk User", if_owner=1).export, 1)

	def test_the_last_rule_is_not_removed(self):
		rows = frappe.get_all("DocPerm", {"parent": NOTE}, ["role", "permlevel", "if_owner"])
		result = self.save([{"act": "settings.remove_permission", **row} for row in rows])
		self.assertFalse(result["saved"])
		self.assertEqual(result["errors"][0]["target"], {"kind": "setting", "property": "permissions"})
		self.assertFalse(frappe.db.exists("Custom DocPerm", {"parent": NOTE}))
