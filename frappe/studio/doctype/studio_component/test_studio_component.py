# Copyright (c) 2025, Frappe Technologies Pvt Ltd and Contributors
# See license.txt

import os
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from studio.studio.doctype.studio_app.test_studio_app import (
	exports_in_tempdir,
	make_studio_app,
	make_studio_page,
)
from studio.studio.doctype.studio_component.patches import set_component_owner


class TestStudioComponent(IntegrationTestCase):
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

	def test_standard_app_components_cannot_be_changed_outside_developer_mode(self):
		app = make_studio_app(app_name="deployed-" + frappe.generate_hash(length=10))
		component = frappe.get_doc(
			doctype="Studio Component", component_name="Deployed", studio_app=app.name
		).insert()
		app.db_set({"is_standard": 1, "frappe_app": "studio"})
		component.db_set("is_standard", 1)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			component.component_name = "Edited"
			self.assertRaises(frappe.PermissionError, component.save)
			self.assertRaises(frappe.PermissionError, frappe.delete_doc, "Studio Component", component.name)

	def test_deleting_an_app_deletes_its_components(self):
		app = make_studio_app(app_name="owner-" + frappe.generate_hash(length=10))
		component = frappe.get_doc(
			doctype="Studio Component", component_name="Owned", studio_app=app.name
		).insert()

		frappe.delete_doc("Studio App", app.name)

		self.assertFalse(frappe.db.exists("Studio Component", component.name))

	def test_unowned_components_join_the_first_app_using_them(self):
		app = make_studio_app(app_name="owner-" + frappe.generate_hash(length=10))
		unowned = frappe.get_doc(doctype="Studio Component", component_name="Unowned").insert()
		blocks = [{"componentName": unowned.name, "isStudioComponent": True, "children": []}]
		make_studio_page(app.name, blocks=frappe.as_json(blocks))

		set_component_owner.execute()

		self.assertEqual(frappe.db.get_value("Studio Component", unowned.name, "studio_app"), app.name)

	def test_standard_components_write_and_remove_their_files(self):
		with exports_in_tempdir():
			app = make_studio_app(app_name="exported-" + frappe.generate_hash(length=10))
			app.enable_app_export("studio")

			created = frappe.get_doc(
				doctype="Studio Component", component_name="Created", studio_app=app.name
			).insert()
			path = os.path.join(created.get_folder_path(), f"{created.name}.json")
			self.assertTrue(created.is_standard)
			self.assertTrue(os.path.exists(path))
			created.delete()
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
