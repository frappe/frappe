# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import glob
import json
import os
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from babel.util import pathmatch

import frappe
from frappe.desk.doctype.form_layout.app_layout import app_layout_key, app_layout_path, read_app_layout
from frappe.desk.doctype.form_layout.form_layout import (
	FORM_LAYOUT_TYPES,
	LAYOUT_BREAKS,
	get_form_layouts,
	layout_entries,
)
from frappe.desk.doctype.form_layout.test_form_layout import a_manager, make_layout
from frappe.gettext.extractors.form_layout import extract
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

CONTACT_INLINE_FIELDS = {"email_id", "phone", "mobile_no"}


def a_tree(fieldname: str) -> list:
	return [{"sections": [{"label": "Main", "columns": [{"fields": [fieldname]}]}]}]


class TestAppLayout(IntegrationTestCase):
	def setUp(self):
		self.folder = tempfile.mkdtemp(prefix="test_app_layout_45447_")
		self.addCleanup(shutil.rmtree, self.folder)
		in_folder = lambda dt, type: os.path.join(self.folder, f"{frappe.scrub(type)}.json")  # noqa: E731
		self.enterContext(
			patch("frappe.desk.doctype.form_layout.app_layout.app_layout_path", side_effect=in_folder)
		)
		frappe.db.delete("Form Layout", {"dt": "Note"})
		self.enterContext(set_user(a_manager()))

	def tearDown(self):
		frappe.db.rollback()

	def write_file(self, type: str, tree: list, omitted: list | None = None) -> str:
		path = os.path.join(self.folder, f"{frappe.scrub(type)}.json")
		with open(path, "w") as f:
			f.write(frappe.as_json({"layout": tree, "omitted": omitted or []}) + "\n")
		return path

	def test_no_row_returns_the_file(self):
		self.write_file("Details", a_tree("title"), omitted=["content"])
		layouts = get_form_layouts("Note", "Details")["layouts"]
		self.assertEqual(len(layouts), 1)
		self.assertEqual((layouts[0]["name"], layouts[0]["condition"]), (None, None))
		self.assertEqual(layouts[0]["omitted"], ["content"])
		section = layouts[0]["layout"][0]["sections"][0]
		self.assertEqual((section["name"], section["columns"][0]["fields"]), ("main", ["title"]))

	def test_no_file_and_no_row_returns_nothing(self):
		self.assertEqual(get_form_layouts("Note", "Details")["layouts"], [])

	def test_a_default_row_replaces_the_file(self):
		self.write_file("Details", a_tree("title"))
		row = make_layout(layout=json.dumps(a_tree("content"))).insert()
		layouts = get_form_layouts("Note", "Details")["layouts"]
		self.assertEqual([layout["name"] for layout in layouts], [row.name])

	def test_a_conditional_row_comes_before_the_file(self):
		self.write_file("Details", a_tree("title"))
		row = make_layout(condition="doc.public", layout=json.dumps(a_tree("content"))).insert()
		layouts = get_form_layouts("Note", "Details")["layouts"]
		self.assertEqual(
			[(layout["name"], layout["condition"]) for layout in layouts],
			[(row.name, "doc.public"), (None, None)],
		)

	def test_new_record_without_its_own_layout_reads_the_details_file(self):
		self.write_file("Details", a_tree("title"))
		layouts = get_form_layouts("Note", "New Record")["layouts"]
		self.assertEqual(layouts[0]["layout"][0]["sections"][0]["columns"][0]["fields"], ["title"])

	def test_a_details_row_beats_a_new_record_file(self):
		self.write_file("New Record", a_tree("title"))
		row = make_layout(layout=json.dumps(a_tree("content"))).insert()
		layouts = get_form_layouts("Note", "New Record")["layouts"]
		self.assertEqual([layout["name"] for layout in layouts], [row.name])

	def test_a_quick_entry_file_opens_the_dialog(self):
		frappe.db.delete("Form Layout", {"dt": "Event"})
		self.assertFalse(get_form_layouts("Event", "Quick Entry")["dialog"])
		self.write_file("Quick Entry", a_tree("subject"))
		self.assertTrue(get_form_layouts("Event", "Quick Entry")["dialog"])

	def test_a_file_change_changes_the_cache_key(self):
		path = self.write_file("Details", a_tree("title"))
		before = app_layout_key("Note", "Details")
		self.assertEqual(
			get_form_layouts("Note", "Details")["layouts"][0]["layout"][0]["sections"][0]["columns"][0][
				"fields"
			],
			["title"],
		)

		self.write_file("Details", a_tree("content"))
		os.utime(path, ns=(before[1] + 1_000_000, before[1] + 1_000_000))
		self.assertNotEqual(app_layout_key("Note", "Details"), before)
		fields = get_form_layouts("Note", "Details")["layouts"][0]["layout"][0]["sections"][0]["columns"][0][
			"fields"
		]
		self.assertEqual(fields, ["content"])


class TestContactLayoutFiles(IntegrationTestCase):
	def test_the_files_sit_in_the_contact_doctype_folder(self):
		for type, name in (("Quick Entry", "quick_entry.json"), ("New Record", "new_record.json")):
			path = app_layout_path("Contact", type)
			self.assertTrue(
				path.endswith(os.path.join("contacts", "doctype", "contact", "frontend", "layouts", name))
			)
			self.assertTrue(os.path.exists(path))
		self.assertIsNone(read_app_layout("Contact", "Details"))

	def test_both_files_carry_email_phone_and_mobile_as_inline_fields(self):
		for type in ("Quick Entry", "New Record"):
			tabs = json.loads(read_app_layout("Contact", type).layout)
			inline = {entry["fieldname"] for entry in layout_entries(tabs) if isinstance(entry, dict)}
			self.assertEqual(inline, CONTACT_INLINE_FIELDS, type)

	def test_new_record_lists_every_field_of_contact(self):
		app_layout = read_app_layout("Contact", "New Record")
		tabs = json.loads(app_layout.layout)
		placed = {entry["fieldname"] if isinstance(entry, dict) else entry for entry in layout_entries(tabs)}
		own_fields = {
			field.fieldname
			for field in frappe.get_doc("DocType", "Contact").fields
			if field.fieldtype not in LAYOUT_BREAKS
		}
		self.assertEqual(placed | set(app_layout.omitted), own_fields)

	def test_contact_create_reads_the_file_with_no_site_row(self):
		frappe.db.delete("Form Layout", {"dt": "Contact"})
		self.addCleanup(frappe.db.rollback)
		with set_user(a_manager()):
			response = get_form_layouts("Contact", "Quick Entry")
		self.assertTrue(response["dialog"])
		self.assertEqual([layout["name"] for layout in response["layouts"]], [None])


class TestEveryAppLayoutFile(IntegrationTestCase):
	def test_every_installed_file_passes_the_checks_a_row_gets(self):
		files = installed_layout_files()
		self.assertIn(
			os.path.realpath(app_layout_path("Contact", "New Record")), [path for path, _dt, _type in files]
		)
		for path, dt, type in files:
			with self.subTest(path=path):
				self.assert_file_is_a_valid_row(path, dt, type)

	def assert_file_is_a_valid_row(self, path: str, dt: str, type: str):
		with open(path) as f:
			text = f.read()
		data = json.loads(text)
		self.assertEqual(text, frappe.as_json(data) + "\n", "not written as a server save writes it")
		self.assertEqual(set(data), {"layout", "omitted"})
		self.assertIsInstance(data["layout"], list)
		self.assertTrue(all(isinstance(fieldname, str) for fieldname in data["omitted"]))
		row = make_layout(dt=dt, type=type, layout=json.dumps(data["layout"]))
		row.validate_layout()
		self.assertEqual(json.loads(row.layout), data["layout"], "a container has no name")


def installed_layout_files() -> list[tuple[str, str, str]]:
	"""`(path, doctype, layout type)` for each layout file of every installed app."""
	files = []
	for app in frappe.get_installed_apps():
		pattern = os.path.join(frappe.get_app_path(app), "*", "doctype", "*", "frontend", "layouts", "*.json")
		for path in glob.glob(pattern):
			folder = Path(path).parents[2]
			with open(folder / f"{folder.name}.json") as f:
				dt = json.load(f)["name"]
			type = next(type for type in FORM_LAYOUT_TYPES if frappe.scrub(type) == Path(path).stem)
			files.append((os.path.realpath(path), dt, type))
	return files


class TestFormLayoutExtractor(IntegrationTestCase):
	def test_one_glob_names_the_files_and_the_doctype_glob_does_not(self):
		path = "frappe/contacts/doctype/contact/frontend/layouts/new_record.json"
		self.assertTrue(pathmatch("**/doctype/*/frontend/layouts/*.json", path))
		self.assertFalse(pathmatch("**/doctype/*/*.json", path))

	def test_extracts_container_and_inline_field_labels_of_contact_files(self):
		with open(app_layout_path("Contact", "New Record"), "rb") as f:
			messages = {message: comments[0] for _lineno, _function, message, comments in extract(f)}
		self.assertEqual(
			messages["Google Contacts"],
			"Label of the sb_00 section of DocType 'Contact' in the New Record layout",
		)
		self.assertEqual(
			messages["Mobile No"],
			"Label of the mobile_no (Data) field in DocType 'Contact' in the New Record layout",
		)
		with open(app_layout_path("Contact", "Quick Entry"), "rb") as f:
			labels = {message for _lineno, _function, message, _comments in extract(f)}
		self.assertEqual(labels, {"Email Address", "Phone", "Mobile No"})

	def test_extracts_a_description_and_skips_what_is_not_a_message(self):
		layout = {
			"layout": [
				{"name": "main", "description": "Who to call", "columns": [{"fields": []}]},
				{"name": "numbered", "label": 5, "columns": []},
				{"name": "no_children", "label": "Not a field"},
			]
		}
		text = frappe.as_json(layout).encode()
		messages = [message for _lineno, _function, message, _comments in extract(BytesIO(text))]
		self.assertEqual(messages, ["Who to call"])
