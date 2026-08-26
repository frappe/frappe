# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import get_visible_modules, is_module_visible

ROLE = "Test Module Grant Role"
USER = "test-module-perms@example.com"
BLOCKED = "Core"
OPEN = "Desk"


class TestModulePermissions(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Role", ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert()
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{"doctype": "User", "email": USER, "first_name": "Module", "send_welcome_email": 0}
			).insert()
		self.reset()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.reset()
		frappe.delete_doc("Role", ROLE, force=True, ignore_missing=True)
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)

	def reset(self):
		user = frappe.get_doc("User", USER)
		user.set("block_modules", [])
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=USER)

	def block(self, module):
		user = frappe.get_doc("User", USER)
		user.append("block_modules", {"module": module})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=USER)

	def give_role(self):
		user = frappe.get_doc("User", USER)
		user.add_roles(ROLE)
		frappe.clear_cache(user=USER)

	def test_an_unblocked_module_is_visible_to_everyone(self):
		"""Blocking is the whole gate: a module nobody blocked is open to all."""
		self.assertTrue(is_module_visible(OPEN, USER))
		self.assertTrue(is_module_visible(BLOCKED, USER))

	def test_block_hides_the_module_it_names_and_nothing_else(self):
		self.block(BLOCKED)
		self.assertFalse(is_module_visible(BLOCKED, USER))
		self.assertTrue(is_module_visible(OPEN, USER))

	def test_get_visible_modules_matches_one_by_one(self):
		self.block(BLOCKED)

		modules = [BLOCKED, OPEN, "Custom"]
		batched = set(get_visible_modules(modules, USER))
		one_by_one = {m for m in modules if is_module_visible(m, USER)}
		self.assertEqual(batched, one_by_one)

	def test_role_gated_workspace_in_a_blocked_module_is_hidden(self):
		"""The bug this phase fixes.

		The module check used to sit inside the no-roles branch, so a workspace with any role bypassed
		the block entirely, and the block did nothing for exactly the workspaces someone had restricted.

		"""
		from frappe.desk.desktop import Workspace

		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "TMP Gated Workspace",
				"label": "TMP Gated Workspace",
				"module": BLOCKED,
				"public": 1,
				"content": "[]",
				"roles": [{"role": ROLE}],
			}
		).insert(ignore_permissions=True)

		try:
			self.give_role()
			self.block(BLOCKED)

			frappe.set_user(USER)
			self.assertFalse(Workspace(workspace).is_permitted())
		finally:
			frappe.set_user("Administrator")
			frappe.delete_doc("Workspace", workspace.name, force=True, ignore_missing=True)

	def test_workspace_roles_can_only_narrow_what_the_module_allows(self):
		"""The relationship between the two gates, stated as a test:

		    reach(workspace) = module visible to user
		                     AND (workspace has no roles OR user holds one)

		They are ANDed, so a workspace's roles are a *narrowing* and never a widening. Here the
		workspace is gated on a role the user certainly holds -- everybody holds `All` -- while
		the module is blocked for them, and the block still has the last word.
		"""
		from frappe.desk.desktop import Workspace

		self.block(BLOCKED)

		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "TMP Widely Gated Workspace",
				"label": "TMP Widely Gated Workspace",
				"module": BLOCKED,
				"public": 1,
				"content": "[]",
				"roles": [{"role": "All"}],
			}
		).insert(ignore_permissions=True)

		try:
			frappe.set_user(USER)
			self.assertIn("All", frappe.get_roles(), "sanity: the workspace's role is one they hold")
			self.assertFalse(Workspace(workspace).is_permitted())
		finally:
			frappe.set_user("Administrator")
			frappe.delete_doc("Workspace", workspace.name, force=True, ignore_missing=True)

	def test_a_module_out_of_reach_takes_its_workspaces_with_it(self):
		"""And the same rule as the desk sees it: `get_workspaces` is what every navigation
		surface is filtered through, so a module the user cannot reach can offer them no page."""
		from frappe.desk.desktop import get_workspaces

		self.block(BLOCKED)

		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "TMP Ungated Workspace In A Blocked Module",
				"label": "TMP Ungated Workspace In A Blocked Module",
				"module": BLOCKED,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)

		try:
			frappe.set_user(USER)
			if getattr(frappe.local, "request_cache", None):
				frappe.local.request_cache.clear()
			self.assertNotIn(workspace.name, [page.name for page in get_workspaces()["pages"]])
		finally:
			frappe.set_user("Administrator")
			frappe.delete_doc("Workspace", workspace.name, force=True, ignore_missing=True)

	def test_resolver_is_not_reachable_from_has_permission(self):
		"""Navigation reach only. If this ever fails, someone has turned a nav preference
		into a security boundary."""
		import inspect

		import frappe.permissions

		source = inspect.getsource(frappe.permissions)
		self.assertNotIn("is_module_visible", source)
		self.assertNotIn("get_visible_modules", source)
