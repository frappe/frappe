# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
from unittest.mock import patch

import frappe
from frappe.desk.doctype.sidebar.test_sidebar import sidebarless_module
from frappe.tests import IntegrationTestCase


class TestWorkspace(IntegrationTestCase):
	def setUp(self):
		create_module("Test Module")

	def tearDown(self):
		# Deleted as documents, not as rows: a workspace takes its sidebar rows with it in
		# `on_trash`, and a raw delete left rows naming a page that no longer exists.
		for name in frappe.get_all("Workspace", filters={"module": "Test Module"}, pluck="name"):
			frappe.delete_doc("Workspace", name, force=True, ignore_missing=True)
		frappe.db.delete("DocType", {"module": "Test Module"})
		frappe.delete_doc("Module Def", "Test Module")

	def test_workspace_conflicts_with_existing_doctype(self):
		"""Workspace name should not conflict with existing DocType names."""

		create_doctype("Test", "Test Module")
		workspace = create_workspace(name="Test", label="Test", public=1, title="Test")

		with self.assertRaises(frappe.NameError):
			workspace.insert()

	# TODO: FIX ME - flaky test!!!
	# def test_workspace_with_cards_specific_to_a_country(self):
	# 	workspace = create_workspace()
	# 	insert_card(workspace, "Card Label 1", "DocType 1", "DocType 2", "France")
	# 	insert_card(workspace, "Card Label 2", "DocType A", "DocType B")

	# 	workspace.insert(ignore_if_duplicate = True)

	# 	cards = workspace.get_link_groups()

	# 	if frappe.get_system_settings('country') == "France":
	# 		self.assertEqual(len(cards), 2)
	# 	else:
	# 		self.assertEqual(len(cards), 1)

	def test_renderer_defaults_to_legacy(self):
		workspace = create_workspace(
			name="Renderer Test", label="Renderer Test", public=1, title="Renderer Test"
		)
		workspace.insert()
		self.assertEqual(workspace.renderer, "Legacy")

	def test_a_page_first_marked_standard_ships_on_frappe_ui(self):
		def standard_page(title):
			workspace = create_workspace(name=title, label=title, public=1, title=title)
			workspace.module = "Desk"
			workspace.standard = 1
			return workspace

		with patch.dict(frappe.conf, {"developer_mode": 1}):
			authored = standard_page("Renderer Authored").insert()
			self.assertEqual(authored.renderer, "Frappe UI")

			authored.renderer = "Legacy"
			authored.save()
			self.assertEqual(authored.renderer, "Legacy")

			with patch.dict(frappe.flags, {"in_import": True}):
				imported = standard_page("Renderer Imported").insert()
			self.assertEqual(imported.renderer, "Legacy")

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			self.assertEqual(standard_page("Renderer On A Site").insert().renderer, "Legacy")

	def test_a_site_cannot_take_a_page_back_to_legacy(self):
		from frappe.desk.doctype.workspace.workspace import set_workspace_renderer

		workspace = create_workspace(
			name="Renderer One Way", label="Renderer One Way", public=1, title="Renderer One Way"
		)
		workspace.renderer = "Frappe UI"
		workspace.insert()

		with patch.dict(frappe.conf, {"developer_mode": 0}):
			workspace.renderer = "Legacy"
			with self.assertRaises(frappe.ValidationError):
				workspace.save()
			with self.assertRaises(frappe.ValidationError):
				set_workspace_renderer(workspace.name, "Legacy")
		self.assertEqual(frappe.db.get_value("Workspace", workspace.name, "renderer"), "Frappe UI")

		with patch.dict(frappe.conf, {"developer_mode": 1}):
			workspace.reload()
			workspace.renderer = "Legacy"
			workspace.save()
		self.assertEqual(frappe.db.get_value("Workspace", workspace.name, "renderer"), "Legacy")

	def test_save_page_with_new_widgets_as_dict(self):
		"""save_page receives new_widgets already parsed into a dict by the request layer."""
		from frappe.desk.doctype.workspace.workspace import save_page

		workspace = frappe.new_doc("Workspace")
		workspace.label = "New Widget Test Workspace"
		workspace.title = "New Widget Test Workspace"
		workspace.public = 0
		workspace.for_user = frappe.session.user
		# mandatory now: the dock is module-shaped, so a workspace with no module belongs nowhere
		workspace.module = "Test Module"
		workspace.content = "[]"
		workspace.insert()

		blocks = json.dumps(
			[{"id": "abcdef1234", "type": "shortcut", "data": {"shortcut_name": "ToDo", "col": 4}}]
		)

		try:
			save_page(
				name=workspace.name,
				public=0,
				new_widgets={"shortcut": [{"type": "DocType", "link_to": "ToDo", "label": "ToDo"}]},
				blocks=blocks,
			)

			[saved] = json.loads(frappe.db.get_value("Workspace", workspace.name, "content"))
			widget = frappe.get_doc("Widget", saved["data"]["widget"])
			self.assertEqual((widget.type, widget.get_config()["link_to"]), ("Shortcut", "ToDo"))
		finally:
			frappe.delete_doc("Workspace", workspace.name, force=True, ignore_missing=True)

	def test_duplicate_shortcut_labels_are_rejected(self):
		"""Two shortcuts sharing a label would collapse into one row on save, so block it."""
		workspace = frappe.new_doc("Workspace")
		workspace.label = "Duplicate Shortcut Workspace"
		workspace.title = "Duplicate Shortcut Workspace"
		workspace.public = 0
		workspace.for_user = frappe.session.user
		workspace.module = "Test Module"
		workspace.content = "[]"

		for stats_filter in (
			'[["ToDo","status","!=","Open",false]]',
			'[["ToDo","status","=","Closed",false]]',
		):
			workspace.append(
				"shortcuts",
				{"type": "DocType", "link_to": "ToDo", "label": "Tasks", "stats_filter": stats_filter},
			)

		try:
			with self.assertRaises(frappe.ValidationError):
				workspace.insert()
		finally:
			frappe.delete_doc("Workspace", workspace.name, force=True, ignore_missing=True)

	def test_preexisting_duplicate_labels_stay_editable(self):
		"""Duplicates already stored (shipped app data, older sites) must not lock the workspace."""
		workspace = frappe.new_doc("Workspace")
		workspace.label = "Legacy Duplicate Workspace"
		workspace.title = "Legacy Duplicate Workspace"
		workspace.public = 0
		workspace.for_user = frappe.session.user
		workspace.module = "Test Module"
		workspace.content = "[]"
		workspace.insert()

		try:
			# simulate data that predates the check, bypassing validate()
			for idx in (1, 2):
				frappe.get_doc(
					{
						"doctype": "Workspace Shortcut",
						"parent": workspace.name,
						"parenttype": "Workspace",
						"parentfield": "shortcuts",
						"idx": idx,
						"type": "DocType",
						"link_to": "ToDo",
						"label": "Tasks",
					}
				).db_insert()

			workspace.reload()
			self.assertEqual(len(workspace.shortcuts), 2)

			# an unrelated edit still saves; the grandfathered duplicate is not re-raised
			workspace.title = "Legacy Duplicate Workspace Renamed"
			workspace.save()

			# Deepening the existing clash with a third row under the grandfathered label is
			# still a new duplicate, so it is refused.
			workspace.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "Tasks"})
			with self.assertRaises(frappe.ValidationError):
				workspace.save()

			# and so is a fresh clash on a label that was unique before
			workspace.reload()
			for _ in range(2):
				workspace.append("shortcuts", {"type": "DocType", "link_to": "ToDo", "label": "Notes"})
			with self.assertRaises(frappe.ValidationError):
				workspace.save()

			# dropping one of the grandfathered rows is a repair, not a new clash
			workspace.reload()
			workspace.shortcuts.pop()
			workspace.save()
			self.assertEqual(len(workspace.shortcuts), 1)
		finally:
			frappe.db.delete("Workspace Shortcut", {"parent": workspace.name})
			frappe.delete_doc("Workspace", workspace.name, force=True, ignore_missing=True)

	def test_role_restricted_non_public_workspace_visible_to_permitted_user(self):
		"""Non-public workspace with roles should be visible to users with matching role."""
		from frappe.desk.desktop import get_workspaces

		workspace = frappe.new_doc("Workspace")
		workspace.label = "Role Test Workspace"
		workspace.title = "Role Test Workspace"
		workspace.category = "Modules"
		workspace.public = 0
		workspace.module = "Desk"
		workspace.append("roles", {"role": "System Manager"})
		workspace.insert(ignore_if_duplicate=True)

		try:
			result = get_workspaces()
			workspace_titles = [p.title for p in result["pages"]]
			self.assertIn("Role Test Workspace", workspace_titles)
		finally:
			frappe.delete_doc("Workspace", workspace.name, force=True, ignore_missing=True)


class TestWorkspaceAccessLevels(IntegrationTestCase):
	"""All three levels survive, and only a Workspace Manager may reach past the first.

	`public` decides whether a page is in anybody's navigation but its owner's, so it is the level a
	plain Desk User is never offered: nobody publishes a page into everyone's navigation by accident.
	The dialog offers them "Only to you" and nothing else, and this asserts the same answer where it
	is enforced.

	"""

	MODULE = "Test Access Level Module"
	DESK_USER = "test-workspace-desk-user@example.com"
	MANAGER = "test-workspace-page-manager@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		# not `create_module`: in developer mode a `Module Def` writes itself into modules.txt
		# and only undoes that on commit, which a rolled-back test never reaches
		self.enterContext(sidebarless_module(self.MODULE))
		self.make_user(self.DESK_USER, ["Desk User"])
		self.make_user(self.MANAGER, ["Desk User", "Workspace Manager"])
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.delete, "Workspace", {"module": self.MODULE})

	def make_user(self, email, roles):
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
		self.addCleanup(frappe.delete_doc, "User", email, force=True, ignore_missing=True)

	def page(self, title, **extra):
		return {
			"title": title,
			"label": title,
			"content": "[]",
			"module": self.MODULE,
			"type": "Workspace",
			"public": 0,
			"for_user": "",
			**extra,
		}

	def test_a_desk_user_creates_a_private_page(self):
		from frappe.desk.doctype.workspace.workspace import new_page

		frappe.set_user(self.DESK_USER)
		# The label carries the owner, which is what keeps two users' pages of the same name
		# apart, and `Workspace` is named after it.
		name = f"Test Desk User Private Page-{self.DESK_USER}"
		new_page(self.page("Test Desk User Private Page", label=name, for_user=self.DESK_USER))

		self.assertEqual(frappe.db.get_value("Workspace", name, "for_user"), self.DESK_USER)

	def test_a_desk_user_cannot_create_a_page_anybody_else_can_see(self):
		from frappe.desk.doctype.workspace.workspace import new_page

		frappe.set_user(self.DESK_USER)
		with self.assertRaises(frappe.PermissionError):
			new_page(self.page("Test Desk User Public Page", public=1))

		self.assertFalse(frappe.db.exists("Workspace", "Test Desk User Public Page"))

	def test_a_desk_user_cannot_edit_a_public_page(self):
		from frappe.desk.doctype.workspace.workspace import new_page, update_page

		frappe.set_user(self.MANAGER)
		new_page(self.page("Test Manager Public Page", public=1))

		frappe.set_user(self.DESK_USER)
		with self.assertRaises(frappe.PermissionError):
			update_page("Test Manager Public Page", "Stolen", "", "", "", 0)

		self.assertEqual(frappe.db.get_value("Workspace", "Test Manager Public Page", "public"), 1)

	def private_page_of(self, user):
		from frappe.desk.doctype.workspace.workspace import new_page

		frappe.set_user(user)
		name = f"Test Owned Page-{user}"
		new_page(self.page("Test Owned Page", label=name, for_user=user))
		return name

	def test_someone_elses_private_page_is_out_of_reach_of_the_document_api(self):
		name = self.private_page_of(self.MANAGER)

		frappe.set_user(self.DESK_USER)
		for ptype in ("read", "write", "delete"):
			self.assertFalse(frappe.has_permission("Workspace", ptype, doc=name), ptype)
		self.assertNotIn(name, frappe.get_list("Workspace", pluck="name", limit=0))

		frappe.set_user(self.MANAGER)
		self.assertIn(name, frappe.get_list("Workspace", pluck="name", limit=0))

	def test_a_private_page_cannot_be_taken_over_by_renaming_its_owner(self):
		name = self.private_page_of(self.MANAGER)

		frappe.set_user(self.DESK_USER)
		doc = frappe.get_doc("Workspace", name)
		doc.for_user = self.DESK_USER
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

		self.assertEqual(frappe.db.get_value("Workspace", name, "for_user"), self.MANAGER)

	def test_a_workspace_manager_cannot_edit_someone_elses_private_page(self):
		from frappe.desk.doctype.workspace.workspace import (
			delete_page,
			get_manageable_workspaces,
			new_page,
			update_workspace_settings,
		)

		name = self.private_page_of(self.DESK_USER)

		frappe.set_user(self.MANAGER)
		self.assertNotIn(name, [page.name for page in get_manageable_workspaces()])
		with self.assertRaises(frappe.PermissionError):
			update_workspace_settings(name, title="Stolen", access="private")
		with self.assertRaises(frappe.PermissionError):
			delete_page(name)
		with self.assertRaises(frappe.PermissionError):
			new_page(self.page("Test Planted Page", for_user=self.DESK_USER))

		self.assertEqual(frappe.db.get_value("Workspace", name, "title"), "Test Owned Page")

	def test_a_workspace_manager_creates_both_shared_levels(self):
		"""Group and public are one field apart: a shared page with roles is the group, a
		shared page without them is everyone."""
		from frappe.desk.doctype.workspace.workspace import new_page

		frappe.set_user(self.MANAGER)
		new_page(self.page("Test Manager Public Page", public=1))
		new_page(self.page("Test Manager Group Page", public=1, roles=[{"role": "System Manager"}]))

		self.assertEqual(frappe.db.get_value("Workspace", "Test Manager Public Page", "public"), 1)
		self.assertEqual(
			frappe.get_all(
				"Has Role",
				filters={"parenttype": "Workspace", "parent": "Test Manager Group Page"},
				pluck="role",
			),
			["System Manager"],
		)

	def test_creating_a_workspace_cannot_create_a_module(self):
		"""The dialog offers a list of modules rather than a Link that could mint one, and the
		endpoint behind it agrees: a workspace names a module that exists or it is not saved."""
		from frappe.desk.doctype.workspace.workspace import new_page

		frappe.set_user(self.MANAGER)
		with self.assertRaises(frappe.ValidationError):
			new_page(self.page("Test Inventing A Module", module="Test No Such Module At All"))

		self.assertFalse(frappe.db.exists("Module Def", "Test No Such Module At All"))


def create_module(module_name):
	module = frappe.get_doc({"doctype": "Module Def", "module_name": module_name, "app_name": "frappe"})
	module.insert(ignore_if_duplicate=True)

	return module


def create_workspace(**args):
	workspace = frappe.new_doc("Workspace")
	args = frappe._dict(args)

	workspace.name = args.name or "Test Workspace"
	workspace.label = args.label or "Test Workspace"
	workspace.category = args.category or "Modules"
	workspace.is_standard = args.is_standard or 1
	workspace.module = "Test Module"
	workspace.public = args.public or 0
	workspace.title = args.title or "Test Workspace"

	return workspace


def insert_card(workspace, card_label, doctype1, doctype2, country=None):
	workspace.append("links", {"type": "Card Break", "label": card_label, "only_for": country})

	create_doctype(doctype1, "Test Module")
	workspace.append(
		"links",
		{
			"type": "Link",
			"label": doctype1,
			"only_for": country,
			"link_type": "DocType",
			"link_to": doctype1,
		},
	)

	create_doctype(doctype2, "Test Module")
	workspace.append(
		"links",
		{
			"type": "Link",
			"label": doctype2,
			"only_for": country,
			"link_type": "DocType",
			"link_to": doctype2,
		},
	)


def create_doctype(doctype_name, module):
	frappe.get_doc(
		{
			"doctype": "DocType",
			"name": doctype_name,
			"module": module,
			"custom": 1,
			"autoname": "field:title",
			"fields": [
				{"label": "Title", "fieldname": "title", "reqd": 1, "fieldtype": "Data"},
				{"label": "Description", "fieldname": "description", "fieldtype": "Small Text"},
				{"label": "Date", "fieldname": "date", "fieldtype": "Date"},
				{"label": "Duration", "fieldname": "duration", "fieldtype": "Duration"},
				{"label": "Number", "fieldname": "number", "fieldtype": "Int"},
				{"label": "Number", "fieldname": "another_number", "fieldtype": "Int"},
			],
			"permissions": [{"role": "System Manager"}],
		}
	).insert(ignore_if_duplicate=True)


class TestBothDoorsToTheModule(IntegrationTestCase):
	"""`Workspace.module` decides which dock lists a workspace, and two endpoints set it.

	They have to agree. `set_workspace_module` checked the module against the assignable list;
	`update_workspace_settings` took a `module` and wrote it straight through, so the same
	operation was validated or not depending on which one the client called.
	"""

	MODULE = "Test Both Doors Module"
	BLOCKED = "Test Both Doors Blocked Module"
	USER = "test-both-doors@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.enterContext(sidebarless_module(self.MODULE))
		self.enterContext(sidebarless_module(self.BLOCKED))

		if frappe.db.exists("User", self.USER):
			frappe.delete_doc("User", self.USER, force=True, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": self.USER,
				"first_name": "Both Doors",
				"send_welcome_email": 0,
				"roles": [{"role": "Desk User"}, {"role": "Workspace Manager"}],
				# the module is real, and this user simply may not see it
				"block_modules": [{"module": self.BLOCKED}],
			}
		).insert(ignore_permissions=True)

		# Registration order matters: addCleanup runs LIFO, so the user has to be deleted as
		# Administrator rather than as themselves.
		self.addCleanup(frappe.delete_doc, "User", self.USER, force=True, ignore_missing=True)
		self.addCleanup(frappe.set_user, "Administrator")
		self.addCleanup(frappe.db.delete, "Workspace", {"module": self.MODULE})

	def make_page(self):
		from frappe.desk.doctype.workspace.workspace import new_page

		frappe.set_user(self.USER)
		title = "Test Both Doors Page"
		name = f"{title}-{self.USER}"
		new_page(
			{
				"title": title,
				"label": name,
				"content": "[]",
				"module": self.MODULE,
				"type": "Workspace",
				"public": 0,
				"for_user": self.USER,
			}
		)
		return name

	def test_the_move_endpoint_refuses_a_module_the_user_cannot_see(self):
		from frappe.desk.doctype.workspace.workspace import set_workspace_module

		name = self.make_page()

		with self.assertRaises(frappe.ValidationError):
			set_workspace_module(name, self.BLOCKED)

		self.assertEqual(frappe.db.get_value("Workspace", name, "module"), self.MODULE)

	def test_the_settings_endpoint_refuses_it_too(self):
		"""The door that used to let it through. A workspace filed under a module the user cannot see
		is one nothing can navigate to, because `get_navigable_modules` drops the module before its
		sidebar is built.
		"""
		from frappe.desk.doctype.workspace.workspace import update_workspace_settings

		name = self.make_page()

		with self.assertRaises(frappe.ValidationError):
			update_workspace_settings(name, access="private", module=self.BLOCKED)

		self.assertEqual(frappe.db.get_value("Workspace", name, "module"), self.MODULE)

	def test_a_module_the_user_can_see_still_goes_through(self):
		from frappe.desk.doctype.workspace.workspace import update_workspace_settings

		name = self.make_page()
		update_workspace_settings(name, access="private", module=self.MODULE)

		self.assertEqual(frappe.db.get_value("Workspace", name, "module"), self.MODULE)
