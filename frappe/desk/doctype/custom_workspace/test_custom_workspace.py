# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
from json import dumps, loads
from unittest.mock import patch

import frappe
from frappe.desk.doctype.custom_workspace.custom_workspace import (
	apply_customization,
	delete_workspace_layout,
	effective_renderer,
	effective_roles,
	reset_workspace_customization,
	upsert_property_customization,
)
from frappe.tests import IntegrationTestCase

BASE_CONTENT = [
	{"id": "s1", "type": "shortcut", "data": {"shortcut_name": "My ToDos", "col": 4}},
	{"id": "s2", "type": "shortcut", "data": {"shortcut_name": "My Notes", "col": 4}},
]

ADDED_SHORTCUT_BLOCK = {"id": "x", "type": "shortcut", "data": {"shortcut_name": "Audit", "col": 4}}
ADDED_SHORTCUT_ITEM = {"type": "DocType", "link_to": "Activity Log", "label": "Audit"}


def make_base_doc():
	"""An in-memory standard Workspace doc with two shortcut blocks (not inserted)."""
	doc = frappe.new_doc("Workspace")
	doc.label = doc.title = "Customization Test"
	doc.module = "Desk"
	doc.public = 1
	doc.standard = 1
	doc.content = dumps(BASE_CONTENT)
	doc.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "My ToDos"})
	doc.append("shortcuts", {"type": "DocType", "link_to": "Note", "label": "My Notes"})
	doc.append("roles", {"role": "Stock User"})
	doc.append("roles", {"role": "Stock Manager"})
	return doc


def make_customization(**values):
	doc = frappe.new_doc("Custom Workspace")
	doc.workspace = "Customization Test"
	for key, value in values.items():
		if key in ("added_roles", "removed_roles"):
			for role in value:
				doc.append(key, {"role": role})
		elif key in ("content", "widgets"):
			doc.set(key, dumps(value))
		else:
			doc.set(key, value)
	return doc


class TestCustomWorkspaceUnit(IntegrationTestCase):
	"""Pure merge logic on in-memory docs (no DB / link validation)."""

	def test_content_snapshot_is_shown_verbatim(self):
		doc = make_base_doc()
		snapshot = [BASE_CONTENT[0]]  # the site dropped "My Notes" and kept only "My ToDos"
		apply_customization(doc, make_customization(content=snapshot))
		self.assertEqual(loads(doc.content), snapshot)

	def test_site_widgets_are_the_whole_set(self):
		doc = make_base_doc()
		snapshot = [*BASE_CONTENT, ADDED_SHORTCUT_BLOCK]
		apply_customization(
			doc,
			make_customization(content=snapshot, widgets={"shortcut": [ADDED_SHORTCUT_ITEM]}),
		)
		self.assertEqual([s.label for s in doc.shortcuts], ["Audit"])

	def test_content_untouched_when_only_visibility_customized(self):
		doc = make_base_doc()
		apply_customization(doc, make_customization(visibility="Hidden"))
		self.assertEqual(loads(doc.content), BASE_CONTENT)
		self.assertTrue(doc.is_hidden)

	def test_effective_roles_add_and_remove(self):
		customization = make_customization(added_roles=["Boss"], removed_roles=["Stock User"])
		roles = set(effective_roles(["Stock User", "Stock Manager"], customization))
		self.assertEqual(roles, {"Stock Manager", "Boss"})

	def test_roles_flow_through_when_app_adds_a_role(self):
		# the delta only remembers "+Boss / -Stock User"; a role the app later adds to the
		# base must still appear (proves roles layer on the live base, not a frozen copy).
		customization = make_customization(added_roles=["Boss"], removed_roles=["Stock User"])
		roles = set(effective_roles(["Stock User", "Stock Manager", "Stock Auditor"], customization))
		self.assertEqual(roles, {"Stock Manager", "Stock Auditor", "Boss"})

	def test_app_layout_change_reaches_a_workspace_customized_only_for_appearance(self):
		# the app ships a new block; a site that only set an icon / visibility has no snapshot
		# holding it back, so the new layout arrives.
		doc = make_base_doc()
		doc.content = dumps([*BASE_CONTENT, ADDED_SHORTCUT_BLOCK])
		apply_customization(doc, make_customization(icon="star", visibility="Hidden"))
		self.assertEqual(loads(doc.content), [*BASE_CONTENT, ADDED_SHORTCUT_BLOCK])
		self.assertEqual(doc.icon, "star")

	def test_customizing_the_layout_freezes_it_but_not_the_roles(self):
		# the whole split, in one place: the app has since added a block *and* a role. The
		# site's snapshot keeps the block out (content is a snapshot) while the role still
		# arrives (roles are a diff on the live base).
		doc = make_base_doc()
		doc.content = dumps([*BASE_CONTENT, ADDED_SHORTCUT_BLOCK])
		doc.append("roles", {"role": "Stock Auditor"})

		apply_customization(doc, make_customization(content=[BASE_CONTENT[0]], added_roles=["Boss"]))

		self.assertEqual(loads(doc.content), [BASE_CONTENT[0]])
		self.assertIn("Stock Auditor", [r.role for r in doc.roles])

	def test_effective_renderer(self):
		for app in ("Legacy", "Frappe UI"):
			for site, expected in (("Inherit", app), ("Legacy", "Legacy"), ("Frappe UI", "Frappe UI")):
				with self.subTest(app=app, site=site):
					customization = make_customization(renderer=site)
					self.assertEqual(effective_renderer(app, customization), expected)
					doc = make_base_doc()
					doc.renderer = app
					apply_customization(doc, customization)
					self.assertEqual(doc.renderer, expected)

	def test_no_user_layer_exists_for_workspaces(self):
		# a private workspace is already yours to edit directly and a public one is the site's,
		# so this doctype is site-only: one row per workspace, with nowhere to name a user.
		meta = frappe.get_meta("Custom Workspace")
		self.assertEqual(meta.autoname, "field:workspace")
		fieldnames = {df.fieldname for df in meta.fields}
		self.assertNotIn("user", fieldnames)
		self.assertNotIn("for_user", fieldnames)


class TestCustomWorkspaceIntegration(IntegrationTestCase):
	WORKSPACE = "WC Integration Test"

	def setUp(self):
		frappe.set_user("Administrator")
		ws = frappe.new_doc("Workspace")
		ws.label = ws.title = self.WORKSPACE
		ws.module = "Desk"
		ws.public = 1
		ws.standard = 1
		ws.content = dumps(BASE_CONTENT)
		ws.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "My ToDos"})
		ws.append("shortcuts", {"type": "DocType", "link_to": "Note", "label": "My Notes"})
		ws.insert(ignore_if_duplicate=True)

	def tearDown(self):
		frappe.delete_doc_if_exists("Custom Workspace", self.WORKSPACE)
		frappe.db.delete("Workspace", {"name": self.WORKSPACE})

	def test_save_page_stores_snapshot_and_leaves_base_untouched(self):
		from frappe.desk.doctype.workspace.workspace import save_page

		edited = [BASE_CONTENT[0]]  # drop "My Notes"
		# force the site (non-developer) path: a standard workspace edit goes to the delta
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			save_page(self.WORKSPACE, public=1, new_widgets={}, blocks=dumps(edited))

		customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
		self.assertEqual(loads(customization.content), edited)
		# The app-owned record still has both blocks, because it was never edited in place.
		base_content = loads(frappe.db.get_value("Workspace", self.WORKSPACE, "content"))
		self.assertEqual(len(base_content), 2)

	def test_get_workspaces_renders_snapshot_content(self):
		frappe.db.set_value("Workspace", self.WORKSPACE, "renderer", "Legacy")
		frappe.get_doc(
			{
				"doctype": "Custom Workspace",
				"workspace": self.WORKSPACE,
				"content": dumps([BASE_CONTENT[0]]),
			}
		).insert()

		from frappe.desk.desktop import get_workspaces

		page = next(p for p in get_workspaces()["pages"] if p["name"] == self.WORKSPACE)
		self.assertEqual(loads(page["content"]), [BASE_CONTENT[0]])

	def test_get_desktop_page_includes_added_widget(self):
		frappe.get_doc(
			{
				"doctype": "Custom Workspace",
				"workspace": self.WORKSPACE,
				"content": dumps([*BASE_CONTENT, ADDED_SHORTCUT_BLOCK]),
				"widgets": dumps({"shortcut": [ADDED_SHORTCUT_ITEM]}),
			}
		).insert()

		from frappe.desk.desktop import get_desktop_page

		result = get_desktop_page({"name": self.WORKSPACE, "title": self.WORKSPACE, "public": 1})
		self.assertIn("Audit", [s.label for s in result["shortcuts"]["items"]])

	def test_added_widget_persists_across_a_second_save(self):
		from frappe.desk.doctype.workspace.workspace import save_page

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			# session 1: add "Audit"
			save_page(
				self.WORKSPACE,
				public=1,
				new_widgets={"shortcut": [ADDED_SHORTCUT_ITEM]},
				blocks=dumps([*BASE_CONTENT, ADDED_SHORTCUT_BLOCK]),
			)
			# session 2: an unrelated edit reports no new widgets, but "Audit" must survive
			save_page(
				self.WORKSPACE,
				public=1,
				new_widgets={},
				blocks=dumps([BASE_CONTENT[0], ADDED_SHORTCUT_BLOCK]),
			)
		# the first save copied the app's widgets in, and the snapshot keeps the ones still used
		widgets = loads(frappe.db.get_value("Custom Workspace", self.WORKSPACE, "widgets"))
		self.assertEqual([w["label"] for w in widgets["shortcut"]], ["My ToDos", "Audit"])

	def test_reset_removes_customization(self):
		frappe.get_doc(
			{"doctype": "Custom Workspace", "workspace": self.WORKSPACE, "visibility": "Hidden"}
		).insert()
		self.assertTrue(frappe.db.exists("Custom Workspace", self.WORKSPACE))

		reset_workspace_customization(self.WORKSPACE)
		self.assertFalse(frappe.db.exists("Custom Workspace", self.WORKSPACE))

	def test_renderer_is_a_diff_and_reset_clears_it(self):
		from frappe.desk.desktop import Workspace

		upsert_property_customization(self.WORKSPACE, renderer="Legacy")
		customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
		self.assertFalse(customization.content)
		self.assertFalse(customization.widgets)
		self.assertEqual(Workspace({"name": self.WORKSPACE}, minimal=True).doc.renderer, "Legacy")

		reset_workspace_customization(self.WORKSPACE)
		self.assertEqual(Workspace({"name": self.WORKSPACE}, minimal=True).doc.renderer, "Frappe UI")

	def test_a_legacy_save_keeps_every_app_widget(self):
		from frappe.desk.desktop import get_desktop_page
		from frappe.desk.doctype.workspace.workspace import save_page

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			save_page(
				self.WORKSPACE,
				public=1,
				new_widgets={"shortcut": [ADDED_SHORTCUT_ITEM]},
				blocks=dumps([*BASE_CONTENT, ADDED_SHORTCUT_BLOCK]),
			)
		result = get_desktop_page({"name": self.WORKSPACE})
		labels = [s.label for s in result["shortcuts"]["items"]]
		self.assertEqual(labels, ["My ToDos", "My Notes", "Audit"])

	def test_switching_renderer_freezes_nothing(self):
		from frappe.desk.doctype.workspace.workspace import set_workspace_renderer

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			set_workspace_renderer(self.WORKSPACE, "Legacy")
			customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
			self.assertEqual(customization.renderer, "Legacy")
			self.assertFalse(customization.content)

			set_workspace_renderer(self.WORKSPACE, "Frappe UI")
		self.assertEqual(frappe.db.get_value("Custom Workspace", self.WORKSPACE, "renderer"), "Inherit")
		self.assertEqual(loads(frappe.db.get_value("Workspace", self.WORKSPACE, "content")), BASE_CONTENT)

	def test_layout_customization_marks_the_page_as_frozen(self):
		# The desk warns before the save that freezes a layout, so the payload has to say whether
		# this workspace already has a snapshot. An appearance-only delta has frozen nothing and
		# must not be reported as if it had.
		from frappe.desk.desktop import _overlay_customization_properties

		frappe.get_doc({"doctype": "Custom Workspace", "workspace": self.WORKSPACE, "icon": "star"}).insert()

		page = frappe._dict(name=self.WORKSPACE)
		_overlay_customization_properties([page])
		self.assertTrue(page.is_customized)
		self.assertFalse(page.get("is_layout_customized"))

		customization = frappe.get_doc("Custom Workspace", self.WORKSPACE)
		customization.content = dumps([BASE_CONTENT[0]])
		customization.save()

		page = frappe._dict(name=self.WORKSPACE)
		_overlay_customization_properties([page])
		self.assertTrue(page.is_layout_customized)

	def test_customization_requires_standard_workspace(self):
		private = frappe.new_doc("Workspace")
		private.label = private.title = "WC Private Test"
		private.module = "Desk"
		private.public = 0
		private.standard = 0
		private.content = "[]"
		private.insert(ignore_if_duplicate=True)
		try:
			with self.assertRaises(frappe.ValidationError):
				frappe.get_doc({"doctype": "Custom Workspace", "workspace": private.name}).insert()
		finally:
			frappe.db.delete("Workspace", {"name": private.name})


class TestSiteLayouts(IntegrationTestCase):
	WORKSPACE = "CW Layouts Test"
	ONE = "CW Role One"
	TWO = "CW Role Two"
	SITE = "CW Role Site"
	USER = "test-cw-layouts@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		for role in (self.ONE, self.TWO, self.SITE):
			if not frappe.db.exists("Role", role):
				frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert()
		if frappe.db.exists("User", self.USER):
			frappe.delete_doc("User", self.USER, force=True)
		frappe.get_doc(
			{"doctype": "User", "email": self.USER, "first_name": "CW", "send_welcome_email": 0}
		).insert()

		ws = frappe.new_doc("Workspace")
		ws.label = ws.title = self.WORKSPACE
		ws.module = "Desk"
		ws.public = 1
		ws.standard = 1
		ws.content = dumps([header("Default")])
		ws.append("variants", {"role": self.ONE, "content": dumps([header("One")]), "widgets": "{}"})
		ws.append("variants", {"role": self.TWO, "content": dumps([header("Two")]), "widgets": "{}"})
		ws.insert(ignore_if_duplicate=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.delete_doc_if_exists("Custom Workspace", self.WORKSPACE)
		frappe.delete_doc("Workspace", self.WORKSPACE, force=True, ignore_missing=True)

	def save(self, variant, text):
		from frappe.desk.doctype.workspace.workspace import save_page

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			save_page(self.WORKSPACE, public=1, new_widgets={}, blocks=dumps([header(text)]), variant=variant)

	def seen_by(self, *roles):
		from frappe.desk.desktop import get_workspace

		frappe.set_user("Administrator")
		user = frappe.get_doc("User", self.USER)
		user.set("roles", [{"role": role} for role in ("Desk User", *roles)])
		user.save()
		frappe.set_user(self.USER)
		payload = get_workspace(self.WORKSPACE)
		frappe.set_user("Administrator")
		return payload["content"][0]["data"]["text"], payload["is_layout_customized"]

	def ship(self, **changes):
		"""What a migrate does to the app's record."""
		ws = frappe.get_doc("Workspace", self.WORKSPACE)
		ws.update(changes)
		with patch.dict(frappe.conf, {"developer_mode": 1}):
			ws.save()

	def test_editing_one_layout_freezes_only_it(self):
		self.save(self.TWO, "Site Two")
		self.ship(content=dumps([header("New Default")]))
		frappe.db.set_value(
			"Workspace Variant",
			{"parent": self.WORKSPACE, "role": self.ONE},
			"content",
			dumps([header("New One")]),
		)

		self.assertEqual(self.seen_by(self.TWO), ("Site Two", True))
		self.assertEqual(self.seen_by(self.ONE), ("New One", False))
		self.assertEqual(self.seen_by(), ("New Default", False))

	def test_a_site_layout_keeps_its_place_and_site_only_ones_come_last(self):
		self.save(self.SITE, "Site Only")
		self.save(self.TWO, "Site Two")
		self.assertEqual(self.seen_by(self.SITE, self.TWO)[0], "Site Two")
		self.assertEqual(self.seen_by(self.SITE)[0], "Site Only")

	def test_reset_one_layout(self):
		self.save(self.ONE, "Site One")
		self.save(self.TWO, "Site Two")
		reset_workspace_customization(self.WORKSPACE, self.ONE)

		self.assertEqual(self.seen_by(self.ONE), ("One", False))
		self.assertEqual(self.seen_by(self.TWO), ("Site Two", True))

	def test_reset_refuses_a_site_only_layout(self):
		self.save(self.SITE, "Site Only")
		with self.assertRaises(frappe.ValidationError):
			reset_workspace_customization(self.WORKSPACE, self.SITE)

	def test_a_layout_the_app_drops_stays_as_the_sites(self):
		self.save(self.TWO, "Site Two")
		ws = frappe.get_doc("Workspace", self.WORKSPACE)
		ws.set("variants", [row for row in ws.variants if row.role != self.TWO])
		with patch.dict(frappe.conf, {"developer_mode": 1}):
			ws.save()

		self.assertEqual(self.seen_by(self.TWO), ("Site Two", True))
		with self.assertRaises(frappe.ValidationError):
			reset_workspace_customization(self.WORKSPACE, self.TWO)

	def test_a_site_only_layout_can_be_deleted_and_an_app_one_cannot(self):
		self.save(self.SITE, "Site Only")
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			delete_workspace_layout(self.WORKSPACE, self.SITE)
			with self.assertRaises(frappe.ValidationError):
				delete_workspace_layout(self.WORKSPACE, self.ONE)
		self.assertEqual(self.seen_by(self.SITE), ("Default", False))

	def test_the_editor_lists_layouts_with_their_source(self):
		from frappe.desk.desktop import get_workspace

		self.save(self.TWO, "Site Two")
		self.save(self.SITE, "Site Only")
		self.seen_by("Workspace Manager")
		frappe.set_user(self.USER)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			payload = get_workspace(self.WORKSPACE)

		sources = [(layout["role"], layout["source"]) for layout in payload["layouts"]]
		self.assertEqual([role for role, _source in sources], [None, self.ONE, self.TWO, self.SITE])
		self.assertEqual(sources[2][1], "Site copy")
		self.assertEqual(sources[3][1], "Site")
		self.assertEqual(payload["save_target"], "site copy")


def header(text):
	return {"id": frappe.generate_hash(length=8), "type": "header", "data": {"text": text, "col": 12}}
