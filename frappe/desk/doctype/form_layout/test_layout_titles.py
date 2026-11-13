# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import hashlib
import json
import os
import shutil
import tempfile
from unittest.mock import patch

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.desk.doctype.form_layout.app_layout import read_app_layouts
from frappe.desk.doctype.form_layout.app_layout_writer import write_app_layouts
from frappe.desk.doctype.form_layout.form_layout import get_form_layouts, omitted_fieldnames, save_form_layout
from frappe.desk.doctype.form_layout.test_app_layout import a_tree
from frappe.desk.doctype.form_layout.test_form_layout import a_manager, make_layout
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user


class TestLayoutTitlesAndFiles(IntegrationTestCase):
	def setUp(self):
		self.folder = tempfile.mkdtemp(prefix="test_layout_titles_47269_")
		self.addCleanup(shutil.rmtree, self.folder)
		self.enterContext(
			patch("frappe.desk.doctype.form_layout.app_layout.app_layout_path", side_effect=self.path)
		)
		frappe.db.delete("Form Layout", {"dt": "Note"})
		self.enterContext(set_user(a_manager()))

	def tearDown(self):
		frappe.db.rollback()

	def path(self, dt: str, type: str) -> str:
		return os.path.join(self.folder, f"{frappe.scrub(type)}.json")

	def write_file(self, data, type: str = "Details"):
		with open(self.path("Note", type), "w") as f:
			f.write(frappe.as_json(data) + "\n")
		self.touch(type)

	def touch(self, type: str = "Details"):
		"""Move the modified time on, so a rewrite within the clock's tick is read again."""
		path = self.path("Note", type)
		mtime = os.stat(path).st_mtime_ns + 1_000_000_000
		os.utime(path, ns=(mtime, mtime))

	def test_a_file_lists_a_default_and_a_conditional_layout(self):
		self.write_file(
			[
				{"title": "Public", "condition": "doc.public", "layout": a_tree("content"), "omitted": []},
				{"title": "Note", "layout": a_tree("title"), "omitted": []},
			]
		)
		layouts = get_form_layouts("Note", "Details")["layouts"]
		self.assertEqual(
			[(layout["name"], layout["title"], layout["condition"]) for layout in layouts],
			[(None, "Public", "doc.public"), (None, "Note", None)],
		)
		self.assertEqual(layouts[0]["layout"][0]["sections"][0]["columns"][0]["fields"], ["content"])

	def test_a_one_layout_file_reads_as_a_list_of_one(self):
		self.write_file({"layout": a_tree("title"), "omitted": ["content"]})
		[entry] = read_app_layouts("Note", "Details").entries
		self.assertEqual((entry.title, entry.condition, entry.omitted), (None, None, ("content",)))

	def test_a_file_with_two_defaults_is_refused(self):
		self.write_file([{"layout": a_tree("title")}, {"layout": a_tree("content")}])
		with self.assertRaisesRegex(frappe.ValidationError, "more than one layout with no condition"):
			get_form_layouts("Note", "Details")

	def test_a_site_default_drops_the_file_and_a_conditional_row_comes_first(self):
		self.write_file(
			[{"condition": "doc.public", "layout": a_tree("content")}, {"layout": a_tree("title")}]
		)
		row = make_layout(condition="doc.title", layout=json.dumps(a_tree("title"))).insert()
		names = [layout["name"] for layout in get_form_layouts("Note", "Details")["layouts"]]
		self.assertEqual(names, [row.name, None, None])

		make_layout(layout=json.dumps(a_tree("content"))).insert()
		self.assertEqual(len(get_form_layouts("Note", "Details")["layouts"]), 2)

	def test_the_writer_round_trips_through_the_reader(self):
		version = write_app_layouts(
			"Note",
			"Details",
			[
				{"title": "Public", "condition": "doc.public", "layout": a_tree("content")},
				{"title": "Note", "layout": a_tree("title"), "omitted": ["ignored"]},
			],
		)
		with open(self.path("Note", "Details"), "rb") as f:
			content = f.read()
		self.assertTrue(content.endswith(b"]\n"))
		self.assertEqual(version, hashlib.sha256(content).hexdigest())

		app_layouts = read_app_layouts("Note", "Details")
		self.assertEqual(app_layouts.version, version)
		public, default = app_layouts.entries
		self.assertEqual((public.title, public.condition), ("Public", "doc.public"))
		self.assertEqual((default.title, default.condition), ("Note", None))
		tabs = json.loads(default.layout)
		self.assertEqual(tabs[0]["sections"][0]["name"], "main", "containers are named as a save names them")
		self.assertEqual(list(default.omitted), omitted_fieldnames("Note", a_tree("title"), custom=False))

	def test_the_writer_runs_the_checks_of_a_save(self):
		with self.assertRaisesRegex(frappe.ValidationError, "Only one Details layout"):
			write_app_layouts("Note", "Details", [{"layout": a_tree("title")}, {"layout": a_tree("content")}])
		named_like_a_field = [{"name": "title", "sections": [{"columns": [{"fields": ["content"]}]}]}]
		with self.assertRaises(frappe.ValidationError):
			write_app_layouts("Note", "Details", [{"layout": named_like_a_field}])
		self.assertFalse(os.path.exists(self.path("Note", "Details")), "a refused list writes nothing")

	def test_a_same_size_rewrite_is_read_again(self):
		write_app_layouts("Note", "Details", [{"condition": "doc.a", "layout": a_tree("title")}])
		self.assertEqual(read_app_layouts("Note", "Details").entries[0].condition, "doc.a")
		write_app_layouts("Note", "Details", [{"condition": "doc.b", "layout": a_tree("title")}])
		self.assertEqual(read_app_layouts("Note", "Details").entries[0].condition, "doc.b")

	def test_an_empty_list_deletes_the_file(self):
		write_app_layouts("Note", "New Record", [{"layout": a_tree("title")}])
		self.assertIsNone(write_app_layouts("Note", "New Record", []))
		self.assertFalse(os.path.exists(self.path("Note", "New Record")))

	def test_the_writer_refuses_a_type_a_save_refuses(self):
		with self.assertRaisesRegex(frappe.ValidationError, "child table"):
			write_app_layouts("Has Role", "Quick Entry", [{"layout": a_tree("role")}])

	def test_the_doctype_export_writes_the_staged_layouts(self):
		doctype = frappe.get_doc("DocType", "Note")
		doctype.flags.app_layouts = {"Quick Entry": [{"layout": a_tree("title"), "size": "2xl"}]}
		doctype.export_app_layouts()
		[entry] = read_app_layouts("Note", "Quick Entry").entries
		self.assertEqual(entry.size, "2xl")

	def test_a_title_is_saved_and_returned(self):
		name = save_form_layout("Note", "Details", json.dumps(a_tree("title")), title="Short note")
		self.assertEqual(frappe.db.get_value("Form Layout", name, "title"), "Short note")
		[layout] = get_form_layouts("Note", "Details")["layouts"]
		self.assertEqual((layout["name"], layout["title"]), (name, "Short note"))

		save_form_layout("Note", "Details", json.dumps(a_tree("content")), name=str(name))
		self.assertEqual(frappe.db.get_value("Form Layout", name, "title"), "Short note", "no title keeps it")

	def test_source_changed_turns_true_when_the_app_file_changes(self):
		version = write_app_layouts("Note", "Details", [{"layout": a_tree("title")}])
		name = save_form_layout("Note", "Details", json.dumps(a_tree("content")))
		self.assertEqual(frappe.db.get_value("Form Layout", name, "fingerprint"), version)
		self.assertFalse(get_form_layouts("Note", "Details")["layouts"][0]["source_changed"])

		write_app_layouts("Note", "Details", [{"layout": a_tree("content")}])
		self.assertTrue(get_form_layouts("Note", "Details")["layouts"][0]["source_changed"])

	def test_a_row_forked_from_the_fallback_sees_a_new_app_file(self):
		save_form_layout("Note", "Details", json.dumps(a_tree("content")))
		self.assertFalse(get_form_layouts("Note", "Details")["layouts"][0]["source_changed"])
		self.write_file([{"layout": a_tree("title")}])
		self.assertTrue(get_form_layouts("Note", "Details")["layouts"][0]["source_changed"])

	def test_a_site_customization_is_not_a_source_change(self):
		save_form_layout("Note", "Details", json.dumps(a_tree("content")))
		written = write_app_layouts("Note", "New Record", [{"layout": a_tree("title")}])
		self.addCleanup(frappe.clear_cache, doctype="Note")
		make_property_setter(
			"Note", None, "field_order", json.dumps(["content", "title"]), "Data", for_doctype=True
		)
		make_property_setter("Note", "title", "label", "Heading", "Data")
		self.assertFalse(get_form_layouts("Note", "Details")["layouts"][0]["source_changed"])
		self.assertEqual(write_app_layouts("Note", "New Record", [{"layout": a_tree("title")}]), written)

	def test_a_later_save_keeps_the_fingerprint_and_an_old_row_has_none(self):
		name = save_form_layout("Note", "Details", json.dumps(a_tree("content")))
		fingerprint = frappe.db.get_value("Form Layout", name, "fingerprint")
		self.write_file([{"layout": a_tree("title")}])
		save_form_layout("Note", "Details", json.dumps(a_tree("title")), name=str(name))
		self.assertEqual(frappe.db.get_value("Form Layout", name, "fingerprint"), fingerprint)

		frappe.db.set_value("Form Layout", name, "fingerprint", None)
		self.assertNotIn("source_changed", get_form_layouts("Note", "Details")["layouts"][0])
