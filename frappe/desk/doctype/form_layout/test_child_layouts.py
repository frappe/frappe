# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
import os
import shutil
import tempfile
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.doctype.form_layout.form_layout import (
	FORM_LAYOUT_TYPES,
	get_form_layouts,
	save_form_layout,
)
from frappe.desk.doctype.form_layout.test_form_layout import a_manager, a_user_with_role, data, make_layout
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

PARENT_DT = "Test Layout Parent 45901"
ROW_DT = "Test Layout Row 45901"
TAG_DT = "Test Layout Tag 45901"
SINGLE_DT = "Test Layout Single 45901"
PARENT_ROLE = "Test Layout Parent Reader 45901"
PARENT_READER = "test_layout_parent_reader_45901@example.com"


def a_tree(fieldname: str) -> str:
	return json.dumps([{"sections": [{"name": "main", "columns": [{"fields": [fieldname]}]}]}])


class TestChildLayouts(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		a_user_with_role(PARENT_READER, PARENT_ROLE)
		new_doctype(ROW_DT, istable=1, fields=[data("item"), data("note")]).insert(ignore_if_duplicate=True)
		new_doctype(
			TAG_DT,
			istable=1,
			fields=[{"label": "Tag", "fieldname": "tag", "fieldtype": "Link", "options": "Role"}],
		).insert(ignore_if_duplicate=True)
		new_doctype(
			PARENT_DT,
			fields=[
				data("title"),
				{"label": "Items", "fieldname": "items", "fieldtype": "Table", "options": ROW_DT},
				{"label": "More Items", "fieldname": "more_items", "fieldtype": "Table", "options": ROW_DT},
				{"label": "Tags", "fieldname": "tags", "fieldtype": "Table MultiSelect", "options": TAG_DT},
			],
			permissions=[{"role": PARENT_ROLE, "read": 1, "write": 0, "create": 0, "delete": 0}],
		).insert(ignore_if_duplicate=True)
		new_doctype(SINGLE_DT, issingle=1, fields=[data("setting")]).insert(ignore_if_duplicate=True)
		# SQLite rolls back DDL, so each test's rollback would drop the DocTypes.
		frappe.db.commit()  # nosemgrep

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		for dt in (PARENT_DT, ROW_DT, TAG_DT, SINGLE_DT):
			frappe.delete_doc_if_exists("DocType", dt)
		frappe.delete_doc_if_exists("User", PARENT_READER)
		frappe.delete_doc_if_exists("Role", PARENT_ROLE)
		frappe.db.commit()  # nosemgrep
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.clear_messages()

	def tearDown(self):
		frappe.db.rollback()

	def children(self, type: str = "Details") -> dict:
		with set_user(PARENT_READER):
			return get_form_layouts(PARENT_DT, type)["children"]

	def test_every_type_carries_each_table_childs_details_rows(self):
		default = make_layout(dt=ROW_DT, layout=a_tree("item")).insert()
		conditional = make_layout(dt=ROW_DT, condition="doc.note", layout=a_tree("note")).insert()
		make_layout(dt=ROW_DT, type="Side Panel", layout=a_tree("note")).insert()
		for type in FORM_LAYOUT_TYPES:
			children = self.children(type)
			self.assertEqual(list(children), [ROW_DT])
			self.assertEqual(
				[(row["name"], row["condition"]) for row in children[ROW_DT]],
				[(default.name, None), (conditional.name, "doc.note")],
			)
			self.assertEqual(
				children[ROW_DT][0]["layout"][0]["sections"][0]["columns"][0]["fields"], ["item"]
			)
			self.assertEqual(children[ROW_DT][0]["omitted"], [])

	def test_a_child_with_no_row_gets_an_empty_list(self):
		self.assertEqual(self.children(), {ROW_DT: []})

	def test_a_reader_of_the_parent_gets_rows_of_a_child_they_cannot_read(self):
		row = make_layout(dt=ROW_DT, layout=a_tree("item")).insert()
		with set_user(PARENT_READER):
			self.assertFalse(frappe.has_permission(ROW_DT, "read"))
			self.assertFalse(frappe.has_permission("Form Layout", "read"))
		self.assertEqual([one["name"] for one in self.children()[ROW_DT]], [row.name])

	def test_a_doctype_with_no_table_has_no_children(self):
		with set_user(a_manager()):
			self.assertEqual(get_form_layouts(SINGLE_DT, "Details")["children"], {})

	def test_a_child_app_file_comes_after_its_rows(self):
		folder = tempfile.mkdtemp(prefix="test_child_layouts_45901_")
		self.addCleanup(shutil.rmtree, folder)
		with open(os.path.join(folder, "details.json"), "w") as f:
			f.write(frappe.as_json({"layout": json.loads(a_tree("note")), "omitted": ["item"]}) + "\n")

		def in_folder(dt, type):
			return os.path.join(folder, f"{frappe.scrub(type)}.json") if dt == ROW_DT else None

		self.enterContext(
			patch("frappe.desk.doctype.form_layout.app_layout.app_layout_path", side_effect=in_folder)
		)
		self.assertEqual(
			[(row["name"], row["omitted"]) for row in self.children()[ROW_DT]], [(None, ["item"])]
		)
		row = make_layout(dt=ROW_DT, layout=a_tree("item")).insert()
		self.assertEqual([one["name"] for one in self.children()[ROW_DT]], [row.name])

	def test_a_child_doctype_saves_only_details(self):
		self.enterContext(set_user(a_manager()))
		self.assertTrue(save_form_layout(ROW_DT, "Details", a_tree("item")))
		for type in ("Side Panel", "Quick Entry", "New Record"):
			frappe.clear_messages()
			self.assertIsNone(save_form_layout(ROW_DT, type, a_tree("item")))
			self.assertIn("child table", frappe.message_log[-1]["message"])
			self.assertFalse(frappe.db.exists("Form Layout", {"dt": ROW_DT, "type": type}))

	def test_a_single_saves_details_and_side_panel_only(self):
		self.enterContext(set_user(a_manager()))
		for type in ("Details", "Side Panel"):
			self.assertTrue(save_form_layout(SINGLE_DT, type, a_tree("setting")))
		for type in ("Quick Entry", "New Record"):
			frappe.clear_messages()
			self.assertIsNone(save_form_layout(SINGLE_DT, type, a_tree("setting")))
			self.assertIn("never created", frappe.message_log[-1]["message"])
			self.assertFalse(frappe.db.exists("Form Layout", {"dt": SINGLE_DT, "type": type}))
