# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import (
	clear_module_permission_cache,
	get_governed_modules,
	get_visible_modules,
	is_module_visible,
)

ROLE = "Test Module Grant Role"
USER = "test-module-perms@example.com"
GOVERNED = "Core"
UNGOVERNED = "Desk"


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
		clear_module_permission_cache()

	def reset(self):
		role = frappe.get_doc("Role", ROLE)
		role.set("modules", [])
		role.save()
		user = frappe.get_doc("User", USER)
		user.set("block_modules", [])
		user.save(ignore_permissions=True)
		clear_module_permission_cache()
		frappe.clear_cache(user=USER)

	def grant(self, module):
		role = frappe.get_doc("Role", ROLE)
		role.append("modules", {"module": module})
		role.save()
		clear_module_permission_cache()

	def block(self, module):
		user = frappe.get_doc("User", USER)
		user.append("block_modules", {"module": module})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=USER)

	def give_role(self):
		user = frappe.get_doc("User", USER)
		user.add_roles(ROLE)
		frappe.clear_cache(user=USER)

	def test_ungoverned_module_is_visible_to_everyone(self):
		"""This is what makes the feature safe to ship: on an existing site no role grants
		anything, so nothing is governed and visibility is exactly as before."""
		self.assertEqual(get_governed_modules(), set())
		self.assertTrue(is_module_visible(UNGOVERNED, USER))
		self.assertTrue(is_module_visible(GOVERNED, USER))

	def test_grant_scopes_a_module_to_its_holders(self):
		self.grant(GOVERNED)

		# governed now, and this user holds no granting role
		self.assertIn(GOVERNED, get_governed_modules())
		self.assertFalse(is_module_visible(GOVERNED, USER))

		self.give_role()
		self.assertTrue(is_module_visible(GOVERNED, USER))

	def test_granting_one_module_does_not_govern_the_others(self):
		self.grant(GOVERNED)
		self.assertTrue(is_module_visible(UNGOVERNED, USER))

	def test_block_beats_grant(self):
		"""Deny wins -- a user's own block is the last word, whatever their roles say."""
		self.grant(GOVERNED)
		self.give_role()
		self.assertTrue(is_module_visible(GOVERNED, USER))

		self.block(GOVERNED)
		self.assertFalse(is_module_visible(GOVERNED, USER))

	def test_get_visible_modules_matches_one_by_one(self):
		self.grant(GOVERNED)
		self.block(UNGOVERNED)

		modules = [GOVERNED, UNGOVERNED, "Custom"]
		batched = set(get_visible_modules(modules, USER))
		one_by_one = {m for m in modules if is_module_visible(m, USER)}
		self.assertEqual(batched, one_by_one)

	def test_role_gated_workspace_in_a_blocked_module_is_hidden(self):
		"""The bug this phase fixes.

		The module check used to sit inside the *no-roles* branch, so a workspace with any
		role bypassed the block entirely -- the block silently did nothing for exactly the
		workspaces someone had bothered to restrict.
		"""
		from frappe.desk.desktop import Workspace

		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "TMP Gated Workspace",
				"label": "TMP Gated Workspace",
				"module": GOVERNED,
				"public": 1,
				"content": "[]",
				"roles": [{"role": ROLE}],
			}
		).insert(ignore_permissions=True)

		try:
			self.give_role()
			self.block(GOVERNED)

			frappe.set_user(USER)
			self.assertFalse(Workspace(workspace).is_permitted())
		finally:
			frappe.set_user("Administrator")
			frappe.delete_doc("Workspace", workspace.name, force=True, ignore_missing=True)

	def test_workspace_roles_can_only_narrow_what_the_module_grants(self):
		"""The relationship between the two gates, stated as a test:

		    reach(workspace) = module visible to user
		                     AND (workspace has no roles OR user holds one)

		They are ANDed, so a workspace's roles are a *narrowing* and never a widening. Here the
		workspace is gated on a role the user certainly holds -- everybody holds `All` -- while
		the module is granted to one they do not, and the module still has the last word.
		"""
		from frappe.desk.desktop import Workspace

		self.grant(GOVERNED)

		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "TMP Widely Gated Workspace",
				"label": "TMP Widely Gated Workspace",
				"module": GOVERNED,
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

		self.grant(GOVERNED)

		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "TMP Ungated Workspace In A Governed Module",
				"label": "TMP Ungated Workspace In A Governed Module",
				"module": GOVERNED,
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
		into a security boundary -- one a user could widen by acquiring any granting role."""
		import inspect

		import frappe.permissions

		source = inspect.getsource(frappe.permissions)
		self.assertNotIn("is_module_visible", source)
		self.assertNotIn("get_visible_modules", source)
