# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.desk.desktop import get_workspace
from frappe.desk.test_desktop import make_user, make_workspace
from frappe.desk.widgets import clear_types_cache
from frappe.tests import IntegrationTestCase

READER = "widget-reader@example.com"


class TestWidgets(IntegrationTestCase):
	def setUp(self):
		# developer mode would export every record into the app
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(clear_types_cache)
		make_user(READER, ["Desk User"])

	def test_names_are_module_and_label_with_the_type_on_a_clash(self):
		make_widget_type("WT Other")
		shortcut = make_shortcut("Profit and Loss", module="Desk")
		other = make_widget("WT Other", "Profit and Loss", module="Desk")

		self.assertEqual(shortcut.name, "Desk-Profit and Loss")
		self.assertEqual(other.name, "Desk-Profit and Loss (WT Other)")

		shortcut.label = "Profit"
		shortcut.save()
		self.assertEqual(shortcut.name, "Desk-Profit and Loss")

	def test_a_site_widget_takes_the_bare_label(self):
		label = frappe.generate_hash(length=8)
		first = make_shortcut(label)
		second = make_shortcut(label)
		self.assertEqual(first.name, label)
		self.assertEqual(second.name, f"{label}-1")

	def test_link_props_follow_a_rename_and_block_a_delete(self):
		report = make_report("WT Report")
		widget = make_shortcut("Report", type="Report", link_to=report)
		self.assertNotIn("link_to", frappe.parse_json(widget.config))

		frappe.rename_doc("Report", report, "WT Report Renamed", force=True)
		widget.reload()
		self.assertEqual(widget.get_config()["link_to"], "WT Report Renamed")

		self.assertRaises(frappe.LinkExistsError, frappe.delete_doc, "Report", "WT Report Renamed")

	def test_filter_rows_drop_their_doctype(self):
		widget = make_shortcut(
			"Open", stats_filter=[["ToDo", "status", "=", "Open"], ["ToDo Child", "x", "=", 1]]
		)
		self.assertEqual(
			widget.get_config()["stats_filter"], [["status", "=", "Open"], ["ToDo Child", "x", "=", 1]]
		)

	def test_a_shortcut_draws_with_its_count(self):
		frappe.get_doc({"doctype": "ToDo", "description": "one", "allocated_to": READER}).insert()
		widget = make_shortcut("Mine", stats_filter=[["allocated_to", "=", "@me"]])
		frappe.set_user(READER)

		page = read_page([widget.name])

		self.assertEqual(page["widgets"]["widget"][widget.name]["data"]["count"], 1)
		self.assertEqual([b["data"]["widget"] for b in page["content"]], [widget.name])

	def test_a_shortcut_the_reader_may_not_open_is_left_out(self):
		unreadable = make_shortcut("Errors", link_to="Error Log")
		inactive_domain = make_shortcut("Domain", restrict_to_domain=make_domain("WT Inactive"))
		frappe.set_user(READER)

		page = read_page([unreadable.name, inactive_domain.name])

		self.assertEqual(page["content"], [])
		self.assertEqual(page["widgets"]["widget"], {})

	def test_a_widget_whose_type_is_gone_is_left_out(self):
		widget = make_shortcut("Orphan")
		frappe.db.set_value("Widget", widget.name, "type", "WT Missing")
		frappe.set_user(READER)

		self.assertEqual(read_page([widget.name])["content"], [])

	def test_data_is_cached_per_user_until_the_widget_is_saved(self):
		widget = make_shortcut("Cached", stats_filter=[["allocated_to", "=", "@me"]])
		frappe.set_user(READER)
		self.assertEqual(count_of(widget), 0)

		frappe.set_user("Administrator")
		frappe.get_doc({"doctype": "ToDo", "description": "two", "allocated_to": READER}).insert()
		self.assertEqual(count_of(widget), 0, "the reader's count is still cached")

		frappe.set_user("Administrator")
		widget.reload()
		widget.save()
		frappe.set_user(READER)
		self.assertEqual(count_of(widget), 1)

	def test_a_card_shows_only_the_links_the_reader_may_open(self):
		todo = make_link("ToDo")
		note = make_link("Note")
		errors = make_link("Error Log")
		card = make_card("Things", [todo, note, errors])
		gone = make_card("Admin Things", [errors])
		frappe.set_user(READER)

		page = read_page([card.name, gone.name])

		rows = page["widgets"]["widget"][card.name]["data"]["items"]
		self.assertEqual([row["link_to"] for row in rows], ["ToDo", "Note"])
		self.assertNotIn(gone.name, page["widgets"]["widget"])

	def test_a_link_says_which_records_it_needs_first(self):
		link = make_link("ToDo", dependencies="WT Missing DocType, ToDo")
		card = make_card("Needs", [link])
		frappe.set_user(READER)

		row = read_page([card.name])["widgets"]["widget"][card.name]["data"]["items"][0]

		self.assertEqual(row["incomplete_dependencies"], ["WT Missing DocType"])

	def test_the_customizations_card_shows_once_where_it_is_placed(self):
		make_report("WT Custom Report")
		placed = make_widget("Module Customizations", "Our Reports", module="Desk")
		shortcut = make_shortcut("First")

		appended = read_page([shortcut.name], hide_custom=0)["content"]
		self.assertEqual(appended[0]["data"]["widget"], shortcut.name)
		self.assertEqual(len(appended), 2, "a page that shows custom reports gets the card last")

		content = read_page([placed.name, shortcut.name], hide_custom=0)["content"]
		self.assertEqual([b["data"]["widget"] for b in content], [placed.name, shortcut.name])


def read_page(names: list[str], hide_custom: int = 1) -> dict:
	frappe.set_user("Administrator")
	content = [{"id": name, "type": "widget", "data": {"widget": name, "col": 4}} for name in names]
	workspace = make_workspace("WT Page", content=content, hide_custom=hide_custom)
	frappe.set_user(READER)
	return get_workspace(workspace.name)


def count_of(widget) -> int:
	user = frappe.session.user
	page = read_page([widget.name])
	frappe.set_user(user)
	return page["widgets"]["widget"][widget.name]["data"]["count"]


def make_shortcut(label, module=None, **config):
	return make_widget("Shortcut", label, module, **({"type": "DocType", "link_to": "ToDo"} | config))


def make_widget(widget_type, label, module=None, **config):
	return frappe.get_doc(
		{"doctype": "Widget", "type": widget_type, "label": label, "module": module, "config": config}
	).insert()


def make_link(link_to, **config):
	return make_widget("Link", link_to, link_type="DocType", link_to=link_to, **config)


def make_card(label, links):
	return make_widget("Card", label, widgets=[{"widget": link.name} for link in links])


def make_widget_type(name):
	if not frappe.db.exists("Widget Type", name):
		frappe.get_doc({"doctype": "Widget Type", "type_name": name, "module": "Desk"}).insert()


def make_report(name):
	for report in (name, f"{name} Renamed"):
		frappe.delete_doc_if_exists("Report", report, force=True)
	frappe.get_doc(
		{
			"doctype": "Report",
			"report_name": name,
			"ref_doctype": "ToDo",
			"report_type": "Report Builder",
			"is_standard": "No",
			"module": "Desk",
		}
	).insert()
	return name


def make_domain(name):
	if not frappe.db.exists("Domain", name):
		frappe.get_doc({"doctype": "Domain", "domain": name}).insert()
	return name
