# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.core.doctype.module_def.test_module_def import custom_module
from frappe.desk.desktop import get_desktop_page, update_onboarding_step
from frappe.desk.doctype.sidebar.test_sidebar import no_developer_mode
from frappe.tests import IntegrationTestCase

USER = "test-onboarding@example.com"
ROLE = "Test Onboarding Role"
MODULE = "Test Onboarding Module"


class TestWorkspaceOnboarding(IntegrationTestCase):
	"""An onboarding block on a workspace shows its steps to the people the onboarding is for, and
	only they can tick those steps off, since progress is shared by the whole site.
	"""

	def setUp(self):
		# in developer mode each fixture would export itself into the app on disk
		self.enterContext(no_developer_mode())
		self.enterContext(self.change_settings("System Settings", {"enable_onboarding": 1}))
		self.module = self.enterContext(custom_module(MODULE))
		self.role = self.make_role(ROLE)
		self.step = self.make_step("Test Onboarding Step")
		self.onboarding = self.make_onboarding("Test Onboarding", [self.step], roles=[self.role])
		self.workspace = self.make_workspace([self.onboarding])

	def tearDown(self):
		frappe.set_user("Administrator")

	def make_role(self, name: str) -> str:
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name}).insert(ignore_permissions=True)
			self.addCleanup(frappe.delete_doc, "Role", name, force=True, ignore_missing=True)
		return name

	def make_user(self, roles: list[str]) -> str:
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": USER,
				"first_name": "Onboarding",
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "User", USER, force=True, ignore_missing=True)
		return USER

	def make_step(self, title: str) -> str:
		self.addCleanup(frappe.delete_doc, "Onboarding Step", title, force=True, ignore_missing=True)
		return (
			frappe.get_doc(
				{
					"doctype": "Onboarding Step",
					"__newname": title,
					"title": title,
					"action": "Go to Page",
					"path": "/desk/todo",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def make_onboarding(self, title: str, steps: list[str], roles: list[str]) -> str:
		self.addCleanup(frappe.delete_doc, "Module Onboarding", title, force=True, ignore_missing=True)
		return (
			frappe.get_doc(
				{
					"doctype": "Module Onboarding",
					"__newname": title,
					"title": title,
					"module": self.module,
					"steps": [{"step": step} for step in steps],
					"allow_roles": [{"role": role} for role in roles],
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def make_workspace(self, onboardings: list[str]):
		content = [
			{"type": "onboarding", "data": {"onboarding_name": name, "col": 12}} for name in onboardings
		]
		self.addCleanup(
			frappe.delete_doc, "Workspace", "Test Onboarding Workspace", force=True, ignore_missing=True
		)
		return frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "Test Onboarding Workspace",
				"label": "Test Onboarding Workspace",
				"module": self.module,
				"public": 1,
				"content": json.dumps(content),
			}
		).insert(ignore_permissions=True)

	def onboardings_on_workspace(self) -> list[dict]:
		page = get_desktop_page(json.dumps({"name": self.workspace.name, "title": self.workspace.title}))
		return page["onboardings"]["items"]

	def test_a_user_holding_its_role_sees_its_steps(self):
		frappe.set_user(self.make_user(roles=[self.role]))

		(onboarding,) = self.onboardings_on_workspace()
		self.assertEqual(onboarding["label"], self.onboarding)
		self.assertEqual([step.name for step in onboarding["items"]], [self.step])

	def test_a_user_without_its_role_sees_nothing(self):
		frappe.set_user(self.make_user(roles=[self.make_role("Test Other Onboarding Role")]))

		self.assertEqual(self.onboardings_on_workspace(), [])

	def test_a_completed_onboarding_is_not_shown(self):
		frappe.db.set_value("Module Onboarding", self.onboarding, "is_complete", 1)
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual(self.onboardings_on_workspace(), [])

	def test_a_block_naming_a_missing_onboarding_leaves_the_rest_of_the_workspace(self):
		content = json.loads(self.workspace.content)
		content.insert(0, {"type": "onboarding", "data": {"onboarding_name": "Test Missing Onboarding"}})
		self.workspace.db_set("content", json.dumps(content))
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual([o["label"] for o in self.onboardings_on_workspace()], [self.onboarding])

	def test_nothing_is_shown_while_onboarding_is_disabled(self):
		self.enterContext(self.change_settings("System Settings", {"enable_onboarding": 0}))
		frappe.set_user(self.make_user(roles=[self.role]))

		self.assertEqual(self.onboardings_on_workspace(), [])

	def test_a_user_holding_its_role_can_complete_a_step(self):
		frappe.set_user(self.make_user(roles=[self.role]))

		update_onboarding_step(self.step, "is_complete", 1)
		self.assertEqual(frappe.db.get_value("Onboarding Step", self.step, "is_complete"), 1)

	def test_a_user_without_its_role_cannot_complete_or_skip_a_step(self):
		frappe.set_user(self.make_user(roles=[self.make_role("Test Other Onboarding Role")]))

		for field in ("is_complete", "is_skipped"):
			with self.assertRaises(frappe.PermissionError):
				update_onboarding_step(self.step, field, 1)
		self.assertEqual(
			frappe.db.get_value("Onboarding Step", self.step, ["is_complete", "is_skipped"]), (0, 0)
		)

	def test_a_step_no_onboarding_uses_cannot_be_marked(self):
		orphan = self.make_step("Test Orphan Onboarding Step")
		frappe.set_user(self.make_user(roles=[self.role]))

		with self.assertRaises(frappe.PermissionError):
			update_onboarding_step(orphan, "is_complete", 1)

	def test_only_the_progress_fields_can_be_changed(self):
		frappe.set_user(self.make_user(roles=[self.role]))

		update_onboarding_step(self.step, "title", "Renamed")
		self.assertEqual(frappe.db.get_value("Onboarding Step", self.step, "title"), "Test Onboarding Step")
