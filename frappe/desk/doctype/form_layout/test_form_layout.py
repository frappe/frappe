# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch

import frappe
from frappe.desk.doctype.form_layout.form_layout import (
	deduplicate_names,
	get_form_layouts,
	parse_layout,
	save_form_layout,
)
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

MANAGER = "test_form_layout_manager@example.com"


def make_layout(**kwargs):
	values = {"doctype": "Form Layout", "dt": "Note", "type": "Details", "layout": "[]"}
	values.update(kwargs)
	return frappe.get_doc(values)


def a_manager() -> str:
	if not frappe.db.exists("User", MANAGER):
		frappe.get_doc(
			doctype="User",
			email=MANAGER,
			first_name="Layout Manager",
			user_type="System User",
			roles=[{"role": "System Manager"}],
		).insert(ignore_permissions=True)
	return MANAGER


def published_doctypes(publish) -> list[str]:
	"""The doctypes named by each `doctype_update` sent through the patched publisher."""
	return [
		call.args[1]["doctype"]
		for call in publish.call_args_list
		if call.args[0] == "doctype_update" and call.kwargs.get("after_commit")
	]


class TestFormLayout(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_single_default_per_dt_and_type(self):
		make_layout().insert()
		self.assertRaises(frappe.ValidationError, make_layout().insert)

	def test_refuses_a_section_or_tab_named_like_a_field(self):
		section = [{"sections": [{"name": "title", "columns": [{"fields": ["content"]}]}]}]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(section)).insert)
		tab = [{"name": "public", "sections": [{"columns": [{"fields": ["content"]}]}]}]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(tab)).insert)
		# A break's fieldname is the section's own, as the meta fallback names it.
		own = [{"sections": [{"name": "seen_by_section", "columns": [{"fields": ["content"]}]}]}]
		make_layout(layout=json.dumps(own)).insert()

	def test_section_names_are_unique_across_tabs(self):
		twice = [
			{"name": "a", "sections": [{"name": "details", "columns": [{"fields": ["title"]}]}]},
			{"name": "b", "sections": [{"name": "details", "columns": [{"fields": ["content"]}]}]},
		]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(twice)).insert)
		tabs = parse_layout(json.dumps(twice))
		deduplicate_names(tabs)
		self.assertEqual([s["name"] for t in tabs for s in t["sections"]], ["details", "details-2"])

	def test_conditional_rows_coexist_with_default(self):
		make_layout().insert()
		make_layout(condition="doc.public").insert()
		make_layout(condition="doc.expire_notification_on").insert()

	def test_default_allowed_per_type(self):
		make_layout().insert()
		make_layout(type="Quick Entry").insert()

	def test_synthesizes_names_from_label_slug(self):
		tree = [{"sections": [{"label": "Contact  Details!", "columns": [{"fields": ["title"]}]}]}]
		tabs = parse_layout(json.dumps(tree))
		section = tabs[0]["sections"][0]
		self.assertEqual(section["name"], "contact_details")
		self.assertEqual(section["columns"][0]["name"], "column_1")

	def test_synthesizes_positional_names_and_dedupes(self):
		tree = [
			{
				"sections": [
					{"columns": []},
					{"label": "Details", "columns": []},
					{"name": "details", "columns": []},
				]
			}
		]
		sections = parse_layout(json.dumps(tree))[0]["sections"]
		self.assertEqual([s["name"] for s in sections], ["section_1", "details_2", "details"])

	def test_wraps_tabless_layout(self):
		tree = [{"label": "Details", "columns": [{"fields": ["title"]}]}]
		tabs = parse_layout(json.dumps(tree))
		self.assertEqual(tabs[0]["name"], "first_tab")
		self.assertEqual(tabs[0]["sections"][0]["name"], "details")

	def test_keeps_authored_names(self):
		tree = [{"name": "main", "sections": [{"name": "who", "columns": [{"name": "left", "fields": []}]}]}]
		tabs = parse_layout(json.dumps(tree))
		self.assertEqual(tabs[0]["name"], "main")
		self.assertEqual(tabs[0]["sections"][0]["name"], "who")
		self.assertEqual(tabs[0]["sections"][0]["columns"][0]["name"], "left")

	def test_fallback_is_deterministic(self):
		first = get_form_layouts("Note", "Details")["fallback"]
		second = get_form_layouts("Note", "Details")["fallback"]
		self.assertTrue(first)
		self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

	def test_names_are_stored_at_write_time(self):
		tree = [{"label": "Lead Details", "sections": [{"label": "Who", "columns": [{"fields": ["title"]}]}]}]
		doc = make_layout(layout=json.dumps(tree)).insert()
		stored = json.loads(frappe.db.get_value("Form Layout", doc.name, "layout"))
		self.assertEqual(stored[0]["name"], "lead_details")
		self.assertEqual(stored[0]["sections"][0]["name"], "who")
		self.assertEqual(stored[0]["sections"][0]["columns"][0]["name"], "column_1")

	def test_stored_name_survives_a_label_rename(self):
		tree = [{"label": "Lead Details", "sections": []}]
		doc = make_layout(layout=json.dumps(tree)).insert()
		stored = json.loads(doc.layout)
		stored[0]["label"] = "Everything Else"
		doc.layout = json.dumps(stored)
		doc.save()
		self.assertEqual(json.loads(doc.layout)[0]["name"], "lead_details")

	def test_tabless_layout_is_stored_without_a_wrapper(self):
		tree = [{"label": "Who", "columns": [{"fields": ["title"]}]}]
		doc = make_layout(layout=json.dumps(tree)).insert()
		stored = json.loads(doc.layout)
		self.assertEqual(len(stored), 1)
		self.assertEqual(stored[0]["name"], "who")
		self.assertNotIn("sections", stored[0])

	def test_duplicate_authored_names_are_rejected(self):
		tree = [{"name": "details", "sections": []}, {"name": "details", "sections": []}]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(tree)).insert)

	def test_duplicate_names_are_rejected_at_every_level(self):
		sections = [{"name": "who", "columns": []}, {"name": "who", "columns": []}]
		self.assertRaises(
			frappe.ValidationError, make_layout(layout=json.dumps([{"sections": sections}])).insert
		)
		columns = [{"name": "left", "fields": []}, {"name": "left", "fields": []}]
		tree = [{"sections": [{"columns": columns}]}]
		self.assertRaises(frappe.ValidationError, make_layout(layout=json.dumps(tree)).insert)

	def test_invalid_layout_is_rejected(self):
		self.assertRaises(frappe.ValidationError, make_layout(layout="{not json").insert)
		self.assertRaises(frappe.ValidationError, make_layout(layout='{"tabs": []}').insert)

	def test_deduplicate_names_repairs_a_synthesized_collision(self):
		# What `get_meta_layout` hits when a Tab Break's fieldname is literally `first_tab`.
		tabs = [{"name": "first_tab", "sections": []}, {"name": "first_tab", "sections": []}]
		deduplicate_names(tabs)
		self.assertEqual([tab["name"] for tab in tabs], ["first_tab", "first_tab-2"])

	def test_fallback_names_are_unique(self):
		tabs = get_form_layouts("Note", "Details")["fallback"]
		names = [tab["name"] for tab in tabs]
		self.assertEqual(len(names), len(set(names)))
		for tab in tabs:
			section_names = [section["name"] for section in tab["sections"]]
			self.assertEqual(len(section_names), len(set(section_names)))

	def test_saving_under_another_doctypes_name_is_refused(self):
		note_layout = make_layout().insert()
		with self.assertRaises(frappe.ValidationError):
			save_form_layout("ToDo", "Details", "[]", name=str(note_layout.name))
		self.assertEqual(frappe.db.get_value("Form Layout", note_layout.name, "dt"), "Note")

	def test_rejects_a_doctype_filter_posing_as_a_name(self):
		self.assertRaises(frappe.FrappeTypeError, get_form_layouts, ["!=", ""], "Details")
		self.assertRaises(frappe.FrappeTypeError, save_form_layout, "Note", "Details", "[]", name=["!=", ""])

	def test_rows_come_back_as_authored(self):
		tree = [{"name": "main", "sections": [{"name": "who", "columns": [{"fields": ["title"]}]}]}]
		make_layout(layout=json.dumps(tree)).insert()
		result = get_form_layouts("Note", "Details")
		self.assertEqual(len(result["layouts"]), 1)
		fields = result["layouts"][0]["layout"][0]["sections"][0]["columns"][0]["fields"]
		self.assertEqual(fields, ["title"])

	def test_a_save_announces_its_doctype(self):
		with set_user(a_manager()), patch("frappe.publish_realtime") as publish:
			make_layout().insert()
		self.assertEqual(published_doctypes(publish), ["Note"])

	def test_a_delete_announces_its_doctype(self):
		with set_user(a_manager()):
			layout = make_layout().insert()
			with patch("frappe.publish_realtime") as publish:
				layout.delete()
		self.assertEqual(published_doctypes(publish), ["Note"])

	def test_moving_a_layout_announces_both_doctypes(self):
		with set_user(a_manager()):
			layout = make_layout().insert()
			layout.dt = "ToDo"
			with patch("frappe.publish_realtime") as publish:
				layout.save()
		self.assertEqual(sorted(published_doctypes(publish)), ["Note", "ToDo"])
