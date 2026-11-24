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
from frappe.studio.doctype.studio_component.studio_component import get_frappe_app_component_folder
from frappe.studio.doctype.studio_page.studio_page import get_blocks
from frappe.studio.tests.test_permissions import make_studio_user
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

	def test_a_frappe_app_holds_a_global_component_in_its_files(self):
		with exports_in_tempdir():
			component = frappe.get_doc(
				doctype="Studio Component",
				component_name="Shipped " + frappe.generate_hash(length=10),
				script=COMPONENT_SCRIPT,
				frappe_app="frappe",
			).insert()
			folder = get_frappe_app_component_folder("frappe")
			script_path = os.path.join(folder, f"{component.name}.js")

			self.assertEqual(component.is_standard, 1)
			exported = frappe.get_file_json(os.path.join(folder, f"{component.name}.json"))
			self.assertEqual(exported["frappe_app"], "frappe")
			self.assertNotIn("script", exported)
			self.assertEqual(frappe.read_file(script_path), COMPONENT_SCRIPT)

			component.delete()
			self.assertFalse(os.path.exists(script_path))

	def test_only_a_global_component_belongs_to_a_frappe_app(self):
		app = make_studio_app(app_name="owned-" + frappe.generate_hash(length=10))
		component = frappe.get_doc(
			doctype="Studio Component", component_name="Owned", studio_app=app.name, frappe_app="frappe"
		)
		self.assertRaises(frappe.ValidationError, component.insert)

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			component = frappe.get_doc(doctype="Studio Component", component_name="Live", frappe_app="frappe")
			self.assertRaises(frappe.PermissionError, component.insert)

	def test_deleting_a_component_removes_its_files(self):
		with exports_in_tempdir():
			app = make_studio_app(
				app_name="exported-" + frappe.generate_hash(length=10), is_standard=1, frappe_app="frappe"
			)
			component = frappe.get_doc(
				doctype="Studio Component",
				component_name="Exported",
				studio_app=app.name,
				script=COMPONENT_SCRIPT,
			).insert()
			blocks = [{"componentName": component.component_id, "isStudioComponent": True, "children": []}]
			page = make_studio_page(app.name, blocks=frappe.as_json(blocks))
			path = os.path.join(page.get_component_folder_path(), "exported.json")
			script_path = path.removesuffix(".json") + ".js"
			self.assertTrue(os.path.exists(path))
			self.assertTrue(os.path.exists(script_path))
			self.assertTrue(frappe.parse_json(frappe.read_file(path)).is_standard)
			self.assertTrue(frappe.db.get_value("Studio Component", component.name, "is_standard"))

			self.assertRaises(frappe.LinkExistsError, component.delete)
			self.assertTrue(os.path.exists(path))
			page.blocks = "[]"
			page.save()
			self.assertFalse(os.path.exists(path))
			self.assertFalse(os.path.exists(script_path))

			# files that no page uses, such as files written by hand, go with the component
			component.reload().export_to_folder(page.get_component_folder_path())
			self.assertTrue(os.path.exists(script_path))
			component.delete()
			self.assertFalse(os.path.exists(path))
			self.assertFalse(os.path.exists(script_path))

	def test_a_component_in_use_cannot_be_deleted(self):
		app = make_studio_app(app_name="uses-" + frappe.generate_hash(length=10))
		card = frappe.get_doc(doctype="Studio Component", component_name="Card").insert()
		use_card = {"componentName": card.component_id, "isStudioComponent": True, "children": []}
		card_list = frappe.get_doc(
			doctype="Studio Component", component_name="Card List", studio_app=app.name, block=use_card
		).insert()
		page = make_studio_page(app.name, blocks="[]")
		page.draft_blocks = frappe.as_json([use_card])
		page.save()

		with self.assertRaises(frappe.LinkExistsError) as error:
			card.delete()
		self.assertIn("Card List (component)", str(error.exception))
		self.assertIn(f"{page.page_title} (page)", str(error.exception))

		# a user who cannot read the page gets no title, and the delete is refused all the same
		other_app = make_studio_app(app_name="other-" + frappe.generate_hash(length=10))
		frappe.permissions.add_user_permission(
			"Studio App", other_app.name, make_studio_user("limited@example.com")
		)
		with self.set_user("limited@example.com"):
			self.assertEqual(card.get_usages(), [None, None])
			with self.assertRaises(frappe.LinkExistsError) as error:
				card.delete()
			self.assertIn("is used in: 2 places that you cannot access.", str(error.exception))

		page.draft_blocks = "[]"
		page.save()
		card_list.delete()
		card.reload().delete()
		self.assertFalse(frappe.db.exists("Studio Component", card.name))

		# an app's components can use each other, and go with the app
		card = frappe.get_doc(doctype="Studio Component", component_name="Card", studio_app=app.name).insert()
		frappe.get_doc(
			doctype="Studio Component", component_name="Card List", studio_app=app.name, block=use_card
		).insert()
		app.delete()
		self.assertFalse(frappe.db.exists("Studio Component", card.name))

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
			component, page, script_path = export_scripted_component()
			self.assertEqual(frappe.read_file(script_path), COMPONENT_SCRIPT)
			exported = frappe.parse_json(frappe.read_file(script_path.removesuffix(".js") + ".json"))
			self.assertNotIn("script", exported)

			component.script = "export default {}\n"
			component.save()
			self.assertEqual(frappe.read_file(script_path), "export default {}\n")

			# a save that does not change the script keeps a file edited on disk
			with open(script_path, "w") as script_file:
				script_file.write("export default { props: { edited: Boolean } }\n")
			component.component_name = "Renamed"
			component.save()
			page.save()
			self.assertEqual(frappe.read_file(script_path), "export default { props: { edited: Boolean } }\n")

			component.reload()
			component.script = ""
			component.save()
			self.assertFalse(os.path.exists(script_path))

	def test_two_apps_can_each_have_a_component_with_the_same_id(self):
		with exports_in_tempdir():
			suffix = frappe.generate_hash(length=10)
			component_id = f"header_{suffix}"
			blocks = frappe.as_json([{"componentName": component_id, "isStudioComponent": True}])
			global_component = frappe.get_doc(
				doctype="Studio Component", component_id=component_id, component_name="Global"
			).insert()
			pages = {}
			for label in ("First", "Second"):
				app = make_studio_app(
					app_name=f"{label.lower()}-{suffix}", is_standard=1, frappe_app="frappe"
				)
				frappe.get_doc(
					doctype="Studio Component",
					component_id=component_id,
					component_name=label,
					studio_app=app.name,
					script=COMPONENT_SCRIPT,
				).insert()
				pages[label] = make_studio_page(app.name, blocks=blocks)
			other_page = make_studio_page(make_studio_app(app_name=f"other-{suffix}").name, blocks=blocks)

			self.assertEqual(global_component.name, component_id)
			for label, page in pages.items():
				component = page.get_components(get_blocks(page))[0]
				self.assertEqual(component.name, f"{page.studio_app}/{component_id}")
				folder = page.get_component_folder_path()
				exported = frappe.parse_json(frappe.read_file(os.path.join(folder, f"{component_id}.json")))
				self.assertEqual(exported.component_name, label)
				self.assertTrue(os.path.exists(os.path.join(folder, f"{component_id}.js")))
			self.assertEqual(other_page.get_components(get_blocks(other_page))[0].name, global_component.name)

			global_component.script = COMPONENT_SCRIPT
			global_component.save()
			self.assertEqual(global_component.get_export_folders(), [])

	def test_an_app_takes_its_components_with_it(self):
		with exports_in_tempdir():
			suffix = frappe.generate_hash(length=10)
			app = make_studio_app(app_name=f"owner-{suffix}", is_standard=1, frappe_app="frappe")
			component = frappe.get_doc(
				doctype="Studio Component", component_name="Card", studio_app=app.name
			).insert()
			blocks = [{"componentName": component.component_id, "isStudioComponent": True}]
			make_studio_page(app.name, blocks=frappe.as_json(blocks))

			new_name = f"renamed-{suffix}"
			frappe.rename_doc("Studio App", app.name, new_name)
			self.assertFalse(frappe.db.exists("Studio Component", component.name))
			renamed = frappe.get_doc("Studio Component", f"{new_name}/card")
			exported = frappe.parse_json(
				frappe.read_file(os.path.join(renamed.get_export_folders()[0], "card.json"))
			)
			self.assertEqual((exported.name, exported.studio_app), (renamed.name, new_name))

			frappe.delete_doc("Studio App", new_name)
			self.assertFalse(frappe.db.exists("Studio Component", renamed.name))

	def test_renaming_a_component_changes_its_id_everywhere(self):
		with exports_in_tempdir():
			suffix = frappe.generate_hash(length=10)
			old_id, new_id = f"autocomplete_{suffix}", f"combobox_{suffix}"
			blocks = frappe.as_json([{"componentName": old_id, "isStudioComponent": True}])
			pages = {}
			for label in ("renamed", "other"):
				app = make_studio_app(app_name=f"{label}-{suffix}", is_standard=1, frappe_app="frappe")
				frappe.get_doc(
					doctype="Studio Component",
					component_id=old_id,
					component_name="Autocomplete",
					studio_app=app.name,
					script=COMPONENT_SCRIPT,
				).insert()
				pages[label] = make_studio_page(app.name, blocks=blocks)
			page = pages["renamed"]
			component = frappe.get_doc("Studio Component", f"{page.studio_app}/{old_id}")

			component.component_id = "edited"
			component.save()
			self.assertEqual(component.component_id, old_id)

			frappe.rename_doc("Studio Component", component.name, new_id)

			renamed = frappe.get_doc("Studio Component", f"{page.studio_app}/{new_id}")
			self.assertEqual(renamed.component_id, new_id)
			page.reload()
			self.assertEqual(get_blocks(page)[0]["componentName"], new_id)
			folder = page.get_component_folder_path()
			self.assertEqual(sorted(os.listdir(folder)), [f"{new_id}.js", f"{new_id}.json"])
			self.assertEqual(
				frappe.parse_json(frappe.read_file(page.get_folder_path(True))).blocks, get_blocks(page)
			)
			self.assertEqual(
				frappe.parse_json(frappe.read_file(os.path.join(folder, f"{new_id}.json"))).name, renamed.name
			)

			other = pages["other"]
			other.reload()
			self.assertEqual(get_blocks(other)[0]["componentName"], old_id)
			self.assertTrue(os.path.exists(os.path.join(other.get_component_folder_path(), f"{old_id}.js")))

	def test_a_global_component_cannot_depend_on_one_app(self):
		app_import = 'import { useCart } from "@app/stores/cart"\nexport default {}\n'
		library_import = 'import { ref } from "vue"\nexport default {}\n'
		vue_block = {
			"componentName": "div",
			"children": [{"componentName": "Cart", "isCustomVueComponent": True}],
		}
		app = make_studio_app(app_name="owner-" + frappe.generate_hash(length=10))

		component = frappe.get_doc(doctype="Studio Component", component_name="Global", script=app_import)
		self.assertRaises(frappe.ValidationError, component.insert)
		component.script = library_import
		component.block = vue_block
		component.insert()
		self.assertIn("Cart", frappe.as_json(frappe.get_message_log()))

		frappe.clear_messages()
		frappe.get_doc(
			doctype="Studio Component",
			component_name="Owned",
			studio_app=app.name,
			script=app_import,
			block=vue_block,
		).insert()
		self.assertEqual(frappe.get_message_log(), [])

	def test_a_global_component_moves_to_the_app_that_uses_it(self):
		with exports_in_tempdir():
			suffix = frappe.generate_hash(length=10)
			component = frappe.get_doc(
				doctype="Studio Component", component_name=f"Card {suffix}", script=COMPONENT_SCRIPT
			).insert()
			component_id = component.component_id
			blocks = frappe.as_json([{"componentName": component_id, "isStudioComponent": True}])
			app = make_studio_app(app_name=f"owner-{suffix}", is_standard=1, frappe_app="frappe")
			page = make_studio_page(app.name, blocks=blocks)
			other_page = make_studio_page(make_studio_app(app_name=f"other-{suffix}").name, blocks=blocks)

			component.reload()
			moved = component.set_app(app.name)

			self.assertEqual(moved, {"name": f"{app.name}/{component_id}", "is_global_kept": True})
			self.assertEqual(page.get_components(get_blocks(page))[0].name, moved["name"])
			self.assertEqual(other_page.get_components(get_blocks(other_page))[0].name, component_id)
			folder = page.get_component_folder_path()
			exported = frappe.parse_json(frappe.read_file(os.path.join(folder, f"{component_id}.json")))
			self.assertEqual(exported.studio_app, app.name)

			frappe.delete_doc("Studio Page", other_page.name, force=True)
			leftover = frappe.get_doc("Studio Component", component_id)
			second_app = make_studio_app(app_name=f"second-{suffix}")
			self.assertFalse(leftover.set_app(second_app.name)["is_global_kept"])
			self.assertFalse(frappe.db.exists("Studio Component", component_id))

			owned = frappe.get_doc("Studio Component", moved["name"])
			self.assertEqual(owned.set_app()["name"], component_id)
			self.assertFalse(frappe.db.exists("Studio Component", moved["name"]))
			self.assertEqual(page.get_components(get_blocks(page))[0].name, component_id)
			self.assertEqual(sorted(os.listdir(folder)), [f"{component_id}.js", f"{component_id}.json"])
			exported = frappe.parse_json(frappe.read_file(os.path.join(folder, f"{component_id}.json")))
			self.assertEqual((exported.name, exported.get("studio_app")), (component_id, None))

	def test_input_rows_of_a_site_component_become_script_props(self):
		from frappe.studio.doctype.studio_component.patches import move_inputs_to_script_props

		def make_component(label, inputs, **fields):
			component = frappe.get_doc(
				doctype="Studio Component",
				component_name=f"{label} {frappe.generate_hash(length=10)}",
				inputs=inputs,
				**fields,
			)
			# a save cannot add an input row, so only the files of an app bring the rows
			self.assertRaisesRegex(
				frappe.ValidationError, "You cannot add or edit input rows", component.insert
			)
			with patch.dict(frappe.flags, in_import=True):
				return component.insert()

		plain = make_component(
			"Plain",
			[
				{"input_name": "title", "type": "text", "required": 1},
				{"input_name": "size", "type": "select", "options": "sm\nmd", "default": "md"},
				{"input_name": "rows", "type": "Data", "description": "The rows to show"},
				{"input_name": "open", "type": "checkbox"},
			],
		)
		bound = make_component(
			"Bound", [{"input_name": "title", "type": "text", "default": "{{ page.title }}"}]
		)
		typed = make_component("Typed", [{"input_name": "step", "type": "number", "default": "2"}])
		standard = make_component("Standard", [{"input_name": "title", "type": "text"}])
		standard.db_set("is_standard", 1)

		move_inputs_to_script_props.execute()
		move_inputs_to_script_props.execute()

		plain.reload()
		self.assertEqual(plain.inputs, [])
		self.assertEqual(
			plain.script,
			"export default {\n"
			"\tprops: {\n"
			"\t\ttitle: { type: String, required: true },\n"
			'\t\tsize: { type: String, default: "md", meta: { control: "select", options: ["sm","md"] } },\n'
			'\t\trows: { meta: { description: "The rows to show" } },\n'
			"\t\topen: Boolean,\n"
			"\t},\n"
			"}\n",
		)
		for kept in (bound, typed, standard):
			kept.reload()
			self.assertFalse(kept.script)
			self.assertEqual(len(kept.inputs), 1)

		# an older component can keep its rows or lose them, and cannot change them
		bound.component_name = "Bound again"
		bound.save()
		bound.inputs[0].default = "Title"
		self.assertRaisesRegex(frappe.ValidationError, "You cannot add or edit input rows", bound.save)
		bound.reload()
		bound.inputs = []
		bound.save()
