# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from json import dumps, loads
from unittest.mock import patch

import frappe
from frappe.desk.desktop import get_workspace
from frappe.desk.doctype.workspace.workspace import save_page
from frappe.desk.doctype.workspace_layout.workspace_layout import remove_layouts_without_files
from frappe.desk.layouts import block_id, item_id
from frappe.desk.test_desktop import block, make_chart, make_named, make_user, make_workspace
from frappe.desk.test_widgets import make_card, make_custom_block, make_link, make_shortcut
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
