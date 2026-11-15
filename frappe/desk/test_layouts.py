# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
from json import dumps, loads
from unittest.mock import patch

import frappe
from frappe.desk.desktop import get_workspace, view_as
from frappe.desk.doctype.workspace.workspace import new_page, save_page
from frappe.desk.doctype.workspace_layout.workspace_layout import remove_layouts_without_files
from frappe.desk.layouts import block_id, item_id
from frappe.desk.test_desktop import block, make_chart, make_named, make_user, make_workspace
from frappe.desk.test_widgets import make_card, make_custom_block, make_link, make_shortcut
from frappe.patches.v17_0.make_custom_workspace_copies_layouts import execute
from frappe.tests import IntegrationTestCase
from frappe.utils.logging import get_log_db

INDIA = "layout-india@example.com"
US = "layout-us@example.com"
MANAGER = "layout-manager@example.com"


class TestLayouts(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		make_user(INDIA, ["Desk User"])
		make_user(US, ["Desk User"])
		make_user(MANAGER, ["Desk User", "Workspace Manager"])
		frappe.defaults.set_user_default("layout_country", "India", INDIA)
		frappe.defaults.set_user_default("layout_country", "United States", US)

		self.todos = make_shortcut("ToDos")
		self.notes = make_shortcut("Notes", link_to="Note")
		self.gst = make_shortcut("GST", link_to="Note")
		frappe.db.delete("Workspace Layout", {"workspace": "Layout Page"})
		self.page = make_workspace(
			"Layout Page", content=[widget_block(self.todos), widget_block(self.notes)]
		)

	def test_an_add_only_layout_reaches_only_the_users_its_condition_holds_for(self):
		make_layout(
			"India",
			module="Desk",
			condition='frappe.defaults.get_user_default("layout_country") == "India"',
			add=[{"after": id_of(self.todos), "block": widget_block(self.gst)}],
		)

		self.assertEqual(shown(INDIA), ["ToDos", "GST", "Notes"])
		self.assertEqual(shown(US), ["ToDos", "Notes"])

	def test_every_matching_layout_applies_and_the_stronger_wins_a_clash(self):
		make_layout("App", module="Desk", move=[{"id": id_of(self.todos), "after": id_of(self.notes)}])
		make_layout("Site", move=[{"id": id_of(self.notes), "after": id_of(self.todos)}])
		self.assertEqual(shown(US), ["ToDos", "Notes"], "the site's move wins")

		make_layout("App Extra", module="Desk", add=[{"after": None, "block": widget_block(self.gst)}])
		self.assertEqual(shown(US), ["GST", "ToDos", "Notes"], "both layouts apply")

	def test_a_hide_from_a_weaker_layout_beats_a_stronger_move(self):
		make_layout("App", module="Desk", hide=[id_of(self.notes)])
		make_layout("Site", move=[{"id": id_of(self.notes), "after": None}], resize={id_of(self.notes): 12})
		self.assertEqual(shown(US), ["ToDos"])

	def test_an_add_after_a_hidden_or_missing_block_goes_to_the_end(self):
		make_layout(
			"App",
			module="Desk",
			hide=[id_of(self.todos)],
			add=[{"after": id_of(self.todos), "block": widget_block(self.gst)}],
		)
		self.assertEqual(shown(US), ["Notes", "GST"])

		frappe.db.delete("Workspace Layout", {"workspace": "Layout Page"})
		make_layout("App", module="Desk", add=[{"after": "no-such-block", "block": widget_block(self.gst)}])
		self.assertEqual(shown(US), ["ToDos", "Notes", "GST"])

	def test_an_add_in_a_card_joins_that_card(self):
		todo, note = make_link("ToDo"), make_link("Note")
		card = make_card("Things", [todo])
		make_workspace("Layout Page", content=[widget_block(card)])
		make_layout(
			"App", module="Desk", add=[{"in": id_of(card), "after": None, "block": widget_block(note)}]
		)

		frappe.set_user(US)
		widgets = get_workspace("Layout Page")["widgets"]["widget"]
		self.assertEqual([row["link_to"] for row in widgets[id_of(card)]["data"]["items"]], ["Note", "ToDo"])

		frappe.set_user("Administrator")
		make_layout("Site", hide=[item_id(id_of(card), todo.name)])
		frappe.set_user(US)
		widgets = get_workspace("Layout Page")["widgets"]["widget"]
		self.assertEqual([row["link_to"] for row in widgets[id_of(card)]["data"]["items"]], ["Note"])

	def test_a_condition_that_raises_counts_as_false_and_is_logged(self):
		errors = get_log_db().count("Error Log")
		make_layout("Broken", module="Desk", condition="1 / 0", hide=[id_of(self.todos)])

		self.assertEqual(shown(US), ["ToDos", "Notes"])
		self.assertEqual(get_log_db().count("Error Log"), errors + 1)

	def test_holding_every_role_gets_every_role_layout(self):
		make_layout(
			"Desk Users",
			module="Desk",
			condition='"Desk User" in frappe.get_roles()',
			hide=[id_of(self.notes)],
		)
		make_layout(
			"Accounts",
			module="Desk",
			condition='"Workspace Manager" in frappe.get_roles()',
			hide=[id_of(self.todos)],
		)

		self.assertEqual(shown(US), ["ToDos"])
		self.assertEqual(shown(MANAGER), [])

	def test_saving_a_layout_clears_the_conditions_it_was_read_with(self):
		layout = make_layout("App", module="Desk", condition="False", hide=[id_of(self.todos)])
		self.assertEqual(shown(US), ["ToDos", "Notes"])

		layout.condition = "True"
		layout.save()
		self.assertEqual(shown(US), ["Notes"])

	def test_a_layout_whose_file_is_gone_is_removed_and_a_site_layout_is_kept(self):
		app = make_layout("App", module="Desk", hide=[id_of(self.todos)])
		site = make_layout("Site", hide=[id_of(self.notes)])

		remove_layouts_without_files("frappe")

		self.assertFalse(frappe.db.exists("Workspace Layout", app.name))
		self.assertTrue(frappe.db.exists("Workspace Layout", site.name))


class TestSavingLayouts(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		make_user(US, ["Desk User"])
		make_user(INDIA, ["Desk User"])
		make_user(MANAGER, ["Desk User", "Workspace Manager"])
		self.todos, self.notes, self.extra = (make_shortcut(label) for label in ("ToDos", "Notes", "Extra"))
		frappe.db.delete("Workspace Layout", {"workspace": "Layout Page"})
		blocks = [widget_block(self.todos), widget_block(self.notes), widget_block(self.extra)]
		make_workspace("Layout Page", content=blocks, standard=1)

	def test_a_site_edit_keeps_its_move_and_hide_and_gets_the_apps_new_block(self):
		frappe.set_user(MANAGER)
		save_page("Layout Page", 1, {}, dumps([drawn(self.extra), drawn(self.notes)]))
		self.assertEqual(shown(US), ["Extra", "Notes"])

		frappe.set_user("Administrator")
		gst = make_shortcut("GST", link_to="Note")
		app = frappe.get_doc("Workspace", "Layout Page")
		app.content = dumps([*loads(app.content), widget_block(gst)])
		app.save()

		self.assertEqual(shown(US), ["Extra", "Notes", "GST"])
		self.assertEqual(
			loads(app.content)[0]["data"]["widget"], self.todos.name, "the app's own page is untouched"
		)

	def test_a_users_edit_reaches_nobody_else(self):
		frappe.set_user(US)
		save_page("Layout Page", 1, {}, dumps([drawn(self.notes)]))

		self.assertEqual(shown(US), ["Notes"])
		self.assertEqual(shown(INDIA), ["ToDos", "Notes", "Extra"])
		layout = frappe.get_doc("Workspace Layout", {"workspace": "Layout Page", "user": US})
		self.assertFalse(frappe.has_permission("Workspace Layout", "read", layout, user=INDIA))

	def test_editing_an_apps_widget_on_a_site_saves_a_site_copy_in_its_place(self):
		frappe.set_user("Administrator")
		app_widget = make_shortcut("App ToDos", module="Desk")
		make_workspace(
			"Layout Page", content=[widget_block(app_widget), widget_block(self.notes)], standard=1
		)

		frappe.set_user(MANAGER)
		edit = {
			app_widget.name: {"label": "Our ToDos", "config": {**app_widget.get_config(), "color": "Red"}}
		}
		save_page("Layout Page", 1, {}, dumps([drawn(app_widget), drawn(self.notes)]), widget_edits=edit)

		self.assertEqual(shown(US), ["Our ToDos", "Notes"])
		self.assertEqual(frappe.db.get_value("Widget", app_widget.name, "label"), "App ToDos")

	def test_a_new_block_of_each_type_saves_a_widget_of_that_type(self):
		frappe.set_user("Administrator")
		make_workspace("Layout New", content=[])
		make_chart("WL Chart", "ToDo")
		make_named("Number Card", "WL Card", label="WL Card", document_type="ToDo", function="Count")
		step = make_named(
			"Onboarding Step", "WL Step", title="WL Step", action="Go to Page", path="/desk/todo"
		)
		make_named(
			"Module Onboarding",
			"WL Onboarding",
			title="WL Onboarding",
			module="Desk",
			success_message="Done",
			documentation_url="https://example.com",
			allow_roles=[{"role": "Desk User"}],
			steps=[{"step": step.name}],
		)
		rows = {
			"shortcut": [{"label": "S", "type": "DocType", "link_to": "ToDo"}],
			"card": [
				{"label": "C", "links": dumps([{"label": "ToDo", "link_type": "DocType", "link_to": "ToDo"}])}
			],
			"number_card": [{"label": "N", "number_card_name": "WL Card"}],
			"chart": [{"label": "Ch", "chart_name": "WL Chart"}],
			"quick_list": [{"label": "Q", "document_type": "ToDo"}],
			"custom_block": [{"label": "B", "custom_block_name": make_custom_block("WL Block")}],
		}
		blocks = [block(block_type, rows[block_type][0]["label"]) for block_type in rows]
		blocks.append(block("onboarding", "WL Onboarding"))

		save_page("Layout New", 0, rows, dumps(blocks))

		content = loads(frappe.db.get_value("Workspace", "Layout New", "content"))
		types = [frappe.db.get_value("Widget", b["data"]["widget"], "type") for b in content]
		expected = ["Shortcut", "Card", "Number Card", "Chart", "Quick List", "Custom Block", "Onboarding"]
		self.assertEqual(types, expected)


class TestV16CopiesPatch(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# a v16 site still has the columns the patch reads; a new site never had them
		for column in ("user", "content", "widgets"):
			if not frappe.db.has_column("Custom Workspace", column):
				frappe.db.sql_ddl(f"alter table `tabCustom Workspace` add column `{column}` longtext")

	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		make_user(US, ["Desk User"])
		make_user(INDIA, ["Desk User"])
		frappe.db.delete("Workspace Layout", {"workspace": "Layout Page"})
		frappe.db.delete("Custom Workspace", {"workspace": "Layout Page"})
		make_workspace(
			"Layout Page",
			content=[block("shortcut", "My ToDos"), block("shortcut", "My Notes")],
			standard=1,
			shortcuts=[
				{"type": "DocType", "link_to": "ToDo", "label": "My ToDos"},
				{"type": "DocType", "link_to": "Note", "label": "My Notes"},
			],
		)

	def test_a_site_copy_draws_the_same_page_and_still_gets_the_apps_new_block(self):
		copy = [block("shortcut", "My Notes"), block("shortcut", "Audit"), block("shortcut", "My ToDos")]
		made_up = {"shortcut": [{"type": "DocType", "link_to": "ToDo", "label": "Audit"}]}
		make_v16_copy(copy, made_up)

		execute()
		self.assertEqual(labels(US), ["My Notes", "Audit", "My ToDos"])

		execute()
		self.assertEqual(frappe.db.count("Workspace Layout", {"workspace": "Layout Page"}), 1)

		app = frappe.get_doc("Workspace", "Layout Page")
		app.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "New In App"})
		app.content = dumps([*loads(app.content), block("shortcut", "New In App")])
		app.save()
		self.assertEqual(labels(US), ["My Notes", "Audit", "My ToDos", "New In App"])

	def test_a_users_copy_becomes_their_own_layout(self):
		make_v16_copy([block("shortcut", "My Notes")], {}, user=US)

		execute()

		self.assertEqual(labels(US), ["My Notes"])
		self.assertEqual(labels(INDIA), ["My ToDos", "My Notes"])
		self.assertFalse(frappe.db.exists("Custom Workspace", {"workspace": "Layout Page"}))


class TestEditor(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		make_user(US, ["Desk User"])
		make_user(MANAGER, ["Desk User", "Workspace Manager"])
		self.todos, self.notes, self.gst = (make_shortcut(label) for label in ("ToDos", "Notes", "GST"))
		frappe.db.delete("Workspace Layout", {"workspace": "Layout Page"})
		make_workspace(
			"Layout Page", content=[widget_block(self.todos), widget_block(self.notes)], standard=1
		)
		self.app = make_layout("Accounts", module="Desk", hide=[id_of(self.notes)])
		self.app_extra = make_layout(
			"India", module="Desk", add=[{"after": None, "block": widget_block(self.gst)}]
		)
		self.site = make_layout("Site edits", hide=[id_of(self.todos)])

	def test_a_manager_edits_the_sites_layout_and_sees_the_apps_locked(self):
		frappe.set_user(MANAGER)
		rows = {row["label"]: row for row in get_workspace("Layout Page", edit=1)["layouts"]}

		self.assertTrue(rows["Site edits"]["editable"] and rows["Site edits"]["editing"])
		self.assertFalse(
			rows["Accounts"]["editable"] or rows["India"]["editable"] or rows["Default"]["editable"]
		)

	def test_the_editor_draws_the_weaker_layouts_under_the_one_edited_and_says_where_blocks_came_from(self):
		frappe.set_user(MANAGER)
		page = get_workspace("Layout Page", layout=self.app_extra.name, edit=1)

		drawn = {block["data"]["widget"]: block for block in page["content"]}
		self.assertNotIn("hidden_by", drawn[self.todos.name], "a stronger layout's hide is not drawn")
		self.assertEqual(drawn[self.notes.name]["hidden_by"], "Frappe Framework")
		self.assertEqual(drawn[self.gst.name]["origin"], "Frappe Framework")

	def test_a_reader_gets_no_picker(self):
		frappe.set_user(US)
		self.assertEqual(get_workspace("Layout Page", edit=1)["layouts"], [])

	def test_an_apps_layout_is_saved_only_in_developer_mode(self):
		frappe.set_user(MANAGER)
		page = dumps([drawn(self.todos)])
		self.assertRaises(frappe.PermissionError, save_page, "Layout Page", 1, {}, page, layout=self.app.name)


class TestDrafts(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		make_user(US, ["Desk User"])
		make_user(MANAGER, ["Desk User", "Workspace Manager"])
		self.todos, self.notes = make_shortcut("ToDos"), make_shortcut("Notes", link_to="Note")
		frappe.db.delete("Workspace Layout", {"workspace": "Layout Page"})
		make_workspace(
			"Layout Page", content=[widget_block(self.todos), widget_block(self.notes)], standard=1
		)

	def test_a_new_layout_is_saved_with_its_condition_and_nothing_exists_before(self):
		frappe.set_user(MANAGER)
		draft = get_workspace("Layout Page", edit=1, new_layout=1)
		self.assertTrue(draft["new_layout"])
		self.assertEqual(
			draft["layout_fields"], ["layout_name", "condition"], "only a developer picks a module"
		)
		self.assertFalse(frappe.db.exists("Workspace Layout", {"workspace": "Layout Page"}))

		settings = {"layout_name": "Managers", "condition": '"Workspace Manager" in frappe.get_roles()'}
		save_page("Layout Page", 1, {}, dumps([drawn(self.notes)]), layout_settings=settings)

		self.assertEqual(shown(MANAGER), ["Notes"])
		self.assertEqual(shown(US), ["ToDos", "Notes"])

	def test_a_developers_module_choice_writes_that_apps_file(self):
		frappe.conf.developer_mode = 1
		settings = {"layout_name": "WL Exported", "condition": "", "module": "Desk"}
		save_page("Layout Page", 1, {}, dumps([drawn(self.todos)]), layout_settings=settings)

		layout = frappe.get_doc(
			"Workspace Layout", {"workspace": "Layout Page", "layout_name": "WL Exported"}
		)
		self.addCleanup(lambda: layout.delete())
		self.assertTrue(layout.file_path().startswith(frappe.get_module_path("Desk")))
		self.assertTrue(os.path.exists(layout.file_path()))

	def test_a_new_workspace_hides_the_generated_custom_card(self):
		new_page(
			{
				"title": "WL New",
				"name": "WL New",
				"label": "WL New",
				"public": 1,
				"module": "Desk",
				"content": "[]",
			}
		)
		self.addCleanup(frappe.delete_doc, "Workspace", "WL New")
		self.assertTrue(frappe.db.get_value("Workspace", "WL New", "hide_custom"))


class TestViewAs(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		for user in (INDIA, US):
			make_user(user, ["Desk User"])
		make_user(MANAGER, ["Desk User", "Workspace Manager"])
		frappe.defaults.set_user_default("layout_country", "India", INDIA)
		self.todos, self.gst = make_shortcut("ToDos"), make_shortcut("GST", link_to="Note")
		frappe.db.delete("Workspace Layout", {"workspace": "Layout Page"})
		make_workspace("Layout Page", content=[widget_block(self.todos)], standard=1)
		india = 'frappe.defaults.get_user_default("layout_country") == "India"'
		make_layout(
			"India", module="Desk", condition=india, add=[{"after": None, "block": widget_block(self.gst)}]
		)
		self.site = make_layout(None, resize={id_of(self.todos): 6})

	def test_a_reader_may_not_view_as_someone_else(self):
		frappe.set_user(US)
		self.assertRaises(frappe.PermissionError, view_as, "Layout Page", INDIA)

	def test_viewing_as_a_user_lands_on_the_site_layout_over_theirs(self):
		frappe.set_user(MANAGER)
		self.assertEqual(view_as("Layout Page", INDIA)["layout"], self.site.name)

		page = get_workspace("Layout Page", edit=1, view_as=INDIA)
		self.assertEqual(page["layout"], self.site.name)
		self.assertEqual([b["data"]["widget"] for b in page["content"]], [self.gst.name, self.todos.name])
		mine = get_workspace("Layout Page", edit=1)
		self.assertEqual([b["data"]["widget"] for b in mine["content"]], [self.todos.name])

	def test_preview_as_a_user_is_what_they_see(self):
		frappe.set_user(MANAGER)
		preview = get_workspace("Layout Page", view_as=INDIA)["content"]
		frappe.set_user(INDIA)
		self.assertEqual(preview, get_workspace("Layout Page")["content"])


class TestDeletesAndRenames(IntegrationTestCase):
	def setUp(self):
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		make_user(US, ["Desk User"])
		self.todos = make_shortcut("ToDos")
		for name in ("Layout Page", "Layout Page Renamed"):
			frappe.db.delete("Workspace Layout", {"workspace": name})
			frappe.db.delete("Workspace", {"name": name})
		make_workspace("Layout Page", content=[widget_block(self.todos)])

	def test_uninstalling_a_companion_keeps_the_sites_edits_for_a_reinstall(self):
		from frappe.installer import _delete_linked_documents, _get_module_linked_doctype_field_map

		module = make_module("WL Companion")
		gst, einvoice = make_shortcut("GST", module=module), make_shortcut("E-Invoice", module=module)
		adds = [{"after": None, "block": widget_block(w)} for w in (einvoice, gst)]
		make_layout("India", module=module, add=adds)
		make_layout("Site", hide=[id_of(einvoice)])
		self.assertEqual(shown(US), ["GST", "ToDos"])

		records = [frappe.get_doc(dt, name).as_dict() for dt, name in self.app_records(module)]
		_delete_linked_documents(module, _get_module_linked_doctype_field_map(), dry_run=False)
		self.assertEqual(shown(US), ["ToDos"])

		for record in records:
			frappe.get_doc(record).insert()
		self.assertEqual(shown(US), ["GST", "ToDos"])

	def app_records(self, module):
		return [
			(doctype, name)
			for doctype in ("Widget", "Workspace Layout")
			for name in frappe.get_all(doctype, {"module": module}, pluck="name")
		]

	def test_deleting_a_site_workspace_drops_its_layouts(self):
		make_layout("Site", hide=[id_of(self.todos)])
		frappe.delete_doc("Workspace", "Layout Page")

		make_workspace("Layout Page", content=[widget_block(self.todos)])
		self.assertEqual(shown(US), ["ToDos"])
		self.assertFalse(frappe.db.exists("Workspace Layout", {"workspace": "Layout Page"}))

	def test_renaming_a_workspace_keeps_its_site_layout(self):
		notes = make_shortcut("Notes", link_to="Note")
		make_workspace("Layout Page", content=[widget_block(self.todos), widget_block(notes)])
		make_layout("Site", hide=[id_of(self.todos)])

		frappe.rename_doc("Workspace", "Layout Page", "Layout Page Renamed", force=True)

		frappe.set_user(US)
		page = get_workspace("Layout Page Renamed")
		self.assertEqual([page["widgets"]["widget"][b["id"]]["label"] for b in page["content"]], ["Notes"])


def make_module(name):
	if not frappe.db.exists("Module Def", name):
		frappe.get_doc(
			{"doctype": "Module Def", "module_name": name, "app_name": "frappe", "custom": 1}
		).insert()
	return name


def make_v16_copy(content: list, widgets: dict, user: str | None = None):
	row = frappe.get_doc({"doctype": "Custom Workspace", "workspace": "Layout Page"}).insert()
	table = frappe.qb.DocType("Custom Workspace")
	frappe.qb.update(table).set(table.content, dumps(content)).set(table.widgets, dumps(widgets)).set(
		table.user, user
	).where(table.name == row.name).run()


def labels(user: str) -> list[str]:
	"""Each drawn block's label, old label-keyed blocks and Widgets alike."""
	current = frappe.session.user
	frappe.set_user(user)
	page = get_workspace("Layout Page")
	frappe.set_user(current)
	widgets = page["widgets"]["widget"]
	return [
		widgets[b["id"]]["label"] if b["type"] == "widget" else b["data"][f"{b['type']}_name"]
		for b in page["content"]
	]


def drawn(widget) -> dict:
	return {**widget_block(widget), "id": id_of(widget)}


def shown(user: str) -> list[str]:
	current = frappe.session.user
	frappe.set_user(user)
	page = get_workspace("Layout Page")
	frappe.set_user(current)
	widgets = page["widgets"]["widget"]
	return [widgets[block["id"]]["label"] for block in page["content"]]


def widget_block(widget) -> dict:
	return {"type": "widget", "data": {"widget": widget.name, "col": 4}}


def id_of(widget) -> str:
	return block_id(widget_block(widget))


def make_layout(layout_name, module=None, condition=None, **changes):
	return frappe.get_doc(
		{
			"doctype": "Workspace Layout",
			"workspace": "Layout Page",
			"layout_name": layout_name,
			"module": module,
			"condition": condition,
			"changes": changes,
		}
	).insert()
