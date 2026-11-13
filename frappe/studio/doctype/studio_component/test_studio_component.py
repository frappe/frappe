# Copyright (c) 2025, Frappe Technologies Pvt Ltd and Contributors
# See license.txt

import os
from unittest.mock import patch

import frappe
from frappe.studio.doctype.studio_app.test_studio_app import (
	exports_in_tempdir,
	make_studio_app,
	make_studio_page,
)
from frappe.tests import IntegrationTestCase

COMPONENT_SCRIPT = 'export default {\n\tprops: { title: String },\n\temits: ["select"],\n}\n'


def export_scripted_component():
	"""A scripted component used by a page of a standard app, and the path of its script file."""
	app = make_studio_app(
		app_name="scripted-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="frappe"
	)
	component = frappe.get_doc(
		doctype="Studio Component",
		component_name="Scripted " + frappe.generate_hash(length=10),
		script=COMPONENT_SCRIPT,
	).insert()
	blocks = [{"componentName": component.name, "isStudioComponent": True, "children": []}]
	page = make_studio_page(app.name, blocks=frappe.as_json(blocks))
	component.reload()
	return component, page, os.path.join(page.get_component_folder_path(), f"{component.name}.js")


class TestStudioComponent(IntegrationTestCase):
	def test_component_id_must_scrub_to_a_single_file_name(self):
		component = frappe.get_doc(doctype="Studio Component", component_name="../Outside")
		self.assertRaises(frappe.ValidationError, component.insert)

	def test_block_round_trip(self):
		block = {"componentName": "div", "children": [{"componentName": "span"}]}
		component = frappe.get_doc(
			doctype="Studio Component",
			component_name="Round trip " + frappe.generate_hash(length=10),
			block=block,
		).insert()
		component.reload()
		self.assertEqual(component.block, frappe.as_json(block, indent=None))
		self.assertEqual(frappe.parse_json(component.block), block)

	def test_standard_components_cannot_be_changed_outside_developer_mode(self):
		component = frappe.get_doc(doctype="Studio Component", component_name="Deployed").insert()
		component.db_set("is_standard", 1)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			component.component_name = "Edited"
			self.assertRaises(frappe.PermissionError, component.save)
			self.assertRaises(frappe.PermissionError, frappe.delete_doc, "Studio Component", component.name)

	def test_deleting_a_component_removes_its_files(self):
		with exports_in_tempdir():
			app = make_studio_app(
				app_name="exported-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="frappe"
			)
			component = frappe.get_doc(doctype="Studio Component", component_name="Exported").insert()
			blocks = [{"componentName": component.name, "isStudioComponent": True, "children": []}]
			page = make_studio_page(app.name, blocks=frappe.as_json(blocks))
			path = os.path.join(page.get_component_folder_path(), f"{frappe.scrub(component.name)}.json")
			self.assertTrue(os.path.exists(path))
			self.assertTrue(frappe.parse_json(frappe.read_file(path)).is_standard)
			self.assertTrue(frappe.db.get_value("Studio Component", component.name, "is_standard"))

			component.delete()

			self.assertFalse(os.path.exists(path))

	def test_export_drops_empty_block_values(self):
		block = {
			"componentName": "div",
			"innerHTML": "",
			"classes": [],
			"componentProps": {"label": ""},
			"children": [{"componentName": "span", "innerHTML": "", "attributes": {}}],
		}
		component = frappe.get_doc(
			doctype="Studio Component",
			component_name="Export " + frappe.generate_hash(length=10),
			block=block,
		).insert()
		doc_export = component.as_dict(no_nulls=True)

		component.run_method("before_export", doc_export)

		self.assertEqual(
			doc_export.block,
			{
				"componentName": "div",
				"componentProps": {"label": ""},
				"children": [{"componentName": "span"}],
			},
		)

	def test_script_exports_to_a_file_beside_the_json(self):
		with exports_in_tempdir():
			component, _page, script_path = export_scripted_component()
			self.assertEqual(frappe.read_file(script_path), COMPONENT_SCRIPT)
			exported = frappe.parse_json(frappe.read_file(script_path.removesuffix(".js") + ".json"))
			self.assertNotIn("script", exported)

			component.script = "export default {}\n"
			component.save()
			self.assertEqual(frappe.read_file(script_path), "export default {}\n")

			component.script = ""
			component.save()
			self.assertFalse(os.path.exists(script_path))

	def test_export_keeps_a_script_file_edited_on_disk(self):
		with exports_in_tempdir():
			component, page, script_path = export_scripted_component()
			with open(script_path, "w") as script_file:
				script_file.write("export default { props: { edited: Boolean } }\n")

			component.component_name = "Renamed"
			component.save()
			page.save()

			self.assertEqual(frappe.read_file(script_path), "export default { props: { edited: Boolean } }\n")

	def test_deleting_a_component_removes_its_script_file(self):
		with exports_in_tempdir():
			component, page, script_path = export_scripted_component()
			page.blocks = "[]"
			page.save()
			self.assertFalse(os.path.exists(script_path))
			self.assertTrue(frappe.db.exists("Studio Component", component.name))
