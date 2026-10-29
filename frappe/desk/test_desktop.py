# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from json import dumps
from unittest.mock import patch

import frappe
from frappe.desk.desktop import (
	DEFAULT_LAYOUT,
	get_desktop_page,
	get_recent_activity,
	get_workspace,
	get_workspaces,
)
from frappe.tests import IntegrationTestCase

DESK_USER = "test-get-workspace-user@example.com"
MANAGER = "test-get-workspace-manager@example.com"


class TestDesktop(IntegrationTestCase):
	def test_get_desktop_page_accepts_native_dict(self):
		workspace = frappe.db.get_value("Workspace", {"public": 1}, "name")
		# page as a native dict instead of a JSON string (frappe.parse_json passthrough)
		result = get_desktop_page({"name": workspace})
		self.assertIsInstance(result, dict)
		self.assertIn("charts", result)


class TestGetWorkspace(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		make_user(DESK_USER, ["Desk User"])
		make_user(MANAGER, ["Desk User", "Workspace Manager"])
		make_chart("GW ToDo Chart", "ToDo")
		make_chart("GW Error Chart", "Error Log")

		self.workspace = make_workspace(
			"GW Test",
			content=[
				block("chart", "ToDos"),
				block("chart", "Errors"),
				block("card", "Things"),
				block("header", text="Hello"),
			],
			charts=[
				{"chart_name": "GW ToDo Chart", "label": "ToDos"},
				{"chart_name": "GW Error Chart", "label": "Errors"},
			],
			links=[
				{"type": "Card Break", "label": "Things"},
				{"type": "Link", "label": "ToDo", "link_type": "DocType", "link_to": "ToDo"},
				{"type": "Link", "label": "Errors", "link_type": "DocType", "link_to": "Error Log"},
			],
		)

	def test_unknown_workspace_is_not_found(self):
		frappe.set_user(DESK_USER)
		with self.assertRaises(frappe.DoesNotExistError):
			get_workspace("No Such Workspace")

	def test_role_gated_workspace_is_forbidden(self):
		make_workspace("GW Gated", roles=["System Manager"])
		frappe.set_user(DESK_USER)
		with self.assertRaises(frappe.PermissionError):
			get_workspace("GW Gated")

	def test_someone_elses_private_workspace_is_forbidden(self):
		private = make_workspace("GW Private", public=0, for_user=MANAGER)
		frappe.set_user(MANAGER)
		self.assertFalse(get_workspace(private.name)["public"])
		frappe.set_user(DESK_USER)
		with self.assertRaises(frappe.PermissionError):
			get_workspace(private.name)

	def test_unreadable_widgets_are_dropped_with_their_blocks(self):
		frappe.set_user(DESK_USER)
		payload = get_workspace("GW Test")

		self.assertEqual(list(payload["widgets"]["charts"]), ["ToDos"])
		self.assertEqual(payload["widgets"]["charts"]["ToDos"]["chart_settings"], {})
		self.assertEqual(
			[(b["type"], b["data"].get("chart_name")) for b in payload["content"]],
			[("chart", "ToDos"), ("card", None), ("header", None)],
		)
		links = payload["widgets"]["cards"]["Things"]["links"]
		self.assertEqual([link["link_to"] for link in links], ["ToDo"])
		self.assertIsNone(payload["variant"])
		self.assertFalse(payload["can_edit"])

	def test_no_access_when_every_widget_is_dropped(self):
		make_workspace(
			"GW Locked",
			content=[block("header", text="Errors"), block("chart", "Errors")],
			charts=[{"chart_name": "GW Error Chart", "label": "Errors"}],
		)
		frappe.set_user(DESK_USER)
		self.assertTrue(get_workspace("GW Locked")["no_access"])
		self.assertFalse(get_workspace("GW Test")["no_access"])

	def test_manager_can_edit(self):
		frappe.set_user(MANAGER)
		self.assertTrue(get_workspace("GW Test")["can_edit"])

	def test_layout_is_customized_only_with_site_content(self):
		standard = make_workspace("GW Standard", standard=1)
		frappe.get_doc({"doctype": "Custom Workspace", "workspace": standard.name, "icon": "star"}).insert()

		frappe.set_user(DESK_USER)
		self.assertFalse(get_workspace(standard.name)["is_layout_customized"])

		frappe.set_user("Administrator")
		frappe.db.set_value("Custom Workspace", standard.name, "content", dumps([block("header", text="Hi")]))
		frappe.get_doc("Custom Workspace", standard.name).clear_cache()

		frappe.set_user(DESK_USER)
		self.assertTrue(get_workspace(standard.name)["is_layout_customized"])

	def test_a_save_keeps_blocks_the_editor_could_not_see(self):
		from frappe.desk.doctype.workspace.workspace import save_page

		reader = "test-gw-reader@example.com"
		make_user(reader, ["Desk User", "System Manager"])

		frappe.set_user(MANAGER)
		seen = get_workspace("GW Test")["content"]
		self.assertNotIn("Errors", [b["data"].get("chart_name") for b in seen])
		hello, todos, things = seen[2], seen[0], seen[1]
		save_page("GW Test", public=1, new_widgets={}, blocks=dumps([hello, todos, things]))

		frappe.set_user(reader)
		payload = get_workspace("GW Test")
		self.assertEqual(
			[
				b["data"].get("chart_name") or b["data"].get("card_name") or b["data"].get("text")
				for b in payload["content"]
			],
			["Hello", "ToDos", "Errors", "Things"],
		)
		self.assertIn("Errors", payload["widgets"]["charts"])

	def test_complete_onboarding_is_left_out(self):
		frappe.db.set_single_value("System Settings", "enable_onboarding", 1)
		step = make_named(
			"Onboarding Step", "GW Step", title="GW Step", action="Go to Page", path="/desk/todo"
		)
		make_named(
			"Module Onboarding",
			"GW Onboarding",
			title="GW Onboarding",
			module="Desk",
			success_message="Done",
			documentation_url="https://example.com",
			allow_roles=[{"role": "Desk User"}],
			steps=[{"step": step.name}],
		)
		make_workspace("GW Onboard", content=[block("onboarding", "GW Onboarding")])

		frappe.set_user(DESK_USER)
		self.assertIn("GW Onboarding", get_workspace("GW Onboard")["widgets"]["onboardings"])

		frappe.set_user("Administrator")
		frappe.db.set_value("Onboarding Step", step.name, "is_complete", 1)

		frappe.set_user(DESK_USER)
		payload = get_workspace("GW Onboard")
		self.assertEqual(payload["widgets"]["onboardings"], {})
		self.assertEqual(payload["content"], [])

	def test_boot_keeps_content_for_legacy_only(self):
		make_workspace("GW Legacy", renderer="Legacy", content=[block("header", text="Old")])
		frappe.set_user(DESK_USER)
		frappe.local.request_cache.clear()
		pages = {p.name: p for p in get_workspaces()["pages"]}

		self.assertEqual(pages["GW Legacy"].renderer, "Legacy")
		self.assertIn("Old", pages["GW Legacy"].content)
		self.assertEqual(pages["GW Test"].renderer, "Frappe UI")
		self.assertNotIn("content", pages["GW Test"])


class TestRoleLayouts(IntegrationTestCase):
	ONE = "GW Role One"
	TWO = "GW Role Two"
	BOTH = "test-gw-both@example.com"
	ONLY_TWO = "test-gw-two@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		for role in (self.ONE, self.TWO):
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert()
		make_user(DESK_USER, ["Desk User"])
		make_user(MANAGER, ["Desk User", "Workspace Manager"])
		make_user(self.BOTH, ["Desk User", self.ONE, self.TWO])
		make_user(self.ONLY_TWO, ["Desk User", self.TWO])
		make_workspace(
			"GW Layouts",
			content=[block("header", text="Default")],
			variants=[layout(self.ONE, "One"), layout(self.TWO, "Two")],
		)

	def heading(self, **kwargs):
		payload = get_workspace("GW Layouts", **kwargs)
		return payload["variant"], payload["content"][0]["data"]["text"]

	def test_first_held_role_in_order_wins(self):
		frappe.set_user(self.ONLY_TWO)
		self.assertEqual(self.heading(), (self.TWO, "Two"))
		frappe.set_user(self.BOTH)
		self.assertEqual(self.heading(), (self.ONE, "One"))
		frappe.set_user(DESK_USER)
		self.assertEqual(self.heading(), (None, "Default"))

	def test_administrator_holds_every_role(self):
		self.assertEqual(self.heading(), (self.ONE, "One"))

	def test_a_layout_carries_its_own_widgets(self):
		frappe.set_user("Administrator")
		ws = frappe.get_doc("Workspace", "GW Layouts")
		ws.variants[1].content = dumps([block("shortcut", "Two Notes")])
		ws.variants[1].widgets = dumps(
			{"shortcut": [{"type": "DocType", "link_to": "Note", "label": "Two Notes"}]}
		)
		ws.save()

		frappe.set_user(self.ONLY_TWO)
		payload = get_workspace("GW Layouts")
		self.assertEqual(list(payload["widgets"]["shortcuts"]), ["Two Notes"])

	def test_automatic_and_unknown_roles_never_match(self):
		ws = frappe.get_doc("Workspace", "GW Layouts")
		ws.variants = []
		ws.append("variants", layout("All", "All"))
		ws.append("variants", layout("GW No Such Role", "Missing"))
		ws.flags.ignore_validate = True
		ws.flags.ignore_links = True
		ws.save()

		frappe.set_user(DESK_USER)
		self.assertEqual(self.heading(), (None, "Default"))

	def test_only_an_editor_picks_a_layout(self):
		frappe.set_user(DESK_USER)
		self.assertEqual(self.heading(variant=self.TWO), (None, "Default"))
		frappe.set_user(MANAGER)
		self.assertEqual(self.heading(variant=self.TWO), (self.TWO, "Two"))
		self.assertEqual(self.heading(variant=DEFAULT_LAYOUT), (None, "Default"))

	def test_a_private_workspace_never_walks(self):
		private = make_workspace("GW Private Layouts", public=0, for_user=self.BOTH)
		frappe.set_user(self.BOTH)
		self.assertIsNone(get_workspace(private.name, variant=self.ONE)["variant"])


class TestRecentActivity(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		make_user(DESK_USER, ["Desk User"])
		frappe.db.delete("ToDo", {"owner": DESK_USER})
		frappe.db.delete("Version", {"owner": DESK_USER})
		frappe.db.delete("Comment", {"comment_email": DESK_USER})
		hidden = frappe.get_doc({"doctype": "ToDo", "description": "Hidden"}).insert()

		frappe.set_user(DESK_USER)
		self.commented = frappe.get_doc({"doctype": "ToDo", "description": "Commented"}).insert()
		self.closed = frappe.get_doc({"doctype": "ToDo", "description": "Closed"}).insert()

		comment = self.commented.add_comment("Comment", "On it")
		self.commented.description = "Commented, then reworded"
		self.commented.save(ignore_version=False)
		self.closed.status = "Closed"
		self.closed.save(ignore_version=False)
		hidden_comment = frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "ToDo",
				"reference_name": hidden.name,
				"content": "Not mine to read",
				"comment_email": DESK_USER,
			}
		).insert(ignore_permissions=True)

		self.set_creation("Comment", comment.name, -3)
		self.set_creation("Version", self.version_of(self.commented), -1)
		self.set_creation("Version", self.version_of(self.closed), -2)
		self.set_creation("Comment", hidden_comment.name, 0)

	def set_creation(self, doctype, name, minutes):
		creation = frappe.utils.add_to_date(frappe.utils.now_datetime(), minutes=minutes)
		frappe.db.set_value(doctype, name, "creation", creation, update_modified=False)

	def version_of(self, doc):
		return frappe.db.get_value("Version", {"ref_doctype": "ToDo", "docname": doc.name})

	def test_newest_action_per_readable_document_first(self):
		activity = get_recent_activity("ToDo")
		self.assertEqual([event.name for event in activity], [self.closed.name, self.commented.name])
		self.assertEqual(activity[0].text, "Set Status to Closed")
		self.assertEqual(activity[1].action, "Commented")

	def test_filters_narrow_the_documents(self):
		activity = get_recent_activity("ToDo", filters=[["ToDo", "status", "=", "Open"]])
		self.assertEqual([event.name for event in activity], [self.commented.name])
		activity = get_recent_activity("ToDo", filters={"status": "Open"})
		self.assertEqual([event.name for event in activity], [self.commented.name])


def layout(role, text, widgets=None):
	return {
		"role": role,
		"content": dumps([block("header", text=text)]),
		"widgets": dumps(widgets or {}),
	}


def block(block_type, name=None, text=None):
	data = {"col": 12}
	if name:
		data[f"{block_type}_name"] = name
	if text:
		data["text"] = text
	return {"id": frappe.generate_hash(length=10), "type": block_type, "data": data}


def make_workspace(title, content=(), public=1, **values):
	frappe.delete_doc_if_exists("Custom Workspace", title)
	for name in frappe.get_all("Workspace", {"title": title}, pluck="name"):
		frappe.delete_doc("Workspace", name, force=True)

	doc = frappe.new_doc("Workspace")
	doc.label = doc.title = title
	doc.module = "Desk"
	doc.public = public
	doc.content = dumps(list(content))
	for key, value in values.items():
		if key in ("charts", "links", "roles", "variants"):
			for row in value:
				doc.append(key, row if isinstance(row, dict) else {"role": row})
		else:
			doc.set(key, value)
	doc.insert()
	return doc


def make_named(doctype, name, **values):
	if frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)
	doc = frappe.get_doc({"doctype": doctype, **values})
	doc.name = name
	# developer mode would export the record into the app
	with patch.dict(frappe.conf, {"developer_mode": 0}):
		return doc.insert()


def make_chart(name, doctype):
	if frappe.db.exists("Dashboard Chart", name):
		return
	frappe.get_doc(
		{
			"doctype": "Dashboard Chart",
			"chart_name": name,
			"chart_type": "Count",
			"document_type": doctype,
			"based_on": "creation",
			"timeseries": 1,
			"timespan": "Last Year",
			"time_interval": "Monthly",
			"type": "Line",
			"filters_json": "[]",
		}
	).insert()


def make_user(email, roles):
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in roles],
		}
	).insert(ignore_permissions=True)
