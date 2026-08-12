# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.desk.doctype.form_layout.form_layout import get_form_layouts, parse_layout
from frappe.tests import IntegrationTestCase


def make_layout(**kwargs):
	values = {"doctype": "Form Layout", "dt": "Note", "type": "Details", "layout": "[]"}
	values.update(kwargs)
	return frappe.get_doc(values)


class TestFormLayout(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_single_default_per_dt_and_type(self):
		make_layout().insert()
		self.assertRaises(frappe.ValidationError, make_layout().insert)

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

	def test_rows_come_back_as_authored(self):
		tree = [{"name": "main", "sections": [{"name": "who", "columns": [{"fields": ["title"]}]}]}]
		make_layout(layout=json.dumps(tree)).insert()
		result = get_form_layouts("Note", "Details")
		self.assertEqual(len(result["layouts"]), 1)
		fields = result["layouts"][0]["layout"][0]["sections"][0]["columns"][0]["fields"]
		self.assertEqual(fields, ["title"])
