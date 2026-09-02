# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from contextlib import contextmanager

import frappe
from frappe.core.doctype.module_def.test_module_def import custom_module
from frappe.desk.doctype.module_onboarding.module_onboarding import get_permitted_onboardings
from frappe.desk.doctype.sidebar.sidebar import resolve_sidebar
from frappe.desk.doctype.sidebar.test_sidebar import (
	make_sidebar,
	no_developer_mode,
	system_write,
)
from frappe.tests import IntegrationTestCase

USER = "test-derived-home@example.com"
ROLE = "Test Derived Home Role"


class DerivedHomeTestCase(IntegrationTestCase):
	"""D5: a module lands you on the first thing you can open, and offers an onboarding only when
	one exists that you are allowed to see. Neither is stored.
	"""

	def setUp(self):
		self.as_user("Administrator")

	def tearDown(self):
		self.as_user("Administrator")

	def as_user(self, user: str):
		"""Switch user, and drop what the previous one cached.

		`get_workspaces` is `@request_cache`d and a test is one long request, so without this
		the second user reads the first user's permitted workspaces."""
		frappe.set_user(user)
		if getattr(frappe.local, "request_cache", None):
			frappe.local.request_cache.clear()

	@contextmanager
	def acting_as(self, user: str):
		"""Look at the desk as `user`, then hand the session back.

		The fixtures these tests build are torn down inside the `custom_module` block they
		were made in, so the session has to be Administrator's again by the time it closes."""
		self.as_user(user)
		try:
			yield user
		finally:
			self.as_user("Administrator")

	def make_user(self, roles: list[str]) -> str:
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)
		frappe.get_doc(
			{
				"doctype": "User",
				"email": USER,
				"first_name": "Derived",
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "User", USER, force=True, ignore_missing=True)
		return USER

	def make_role(self, name: str = ROLE) -> str:
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name}).insert(ignore_permissions=True)
			self.addCleanup(frappe.delete_doc, "Role", name, force=True, ignore_missing=True)
		return name

	def make_workspace(self, module: str, title: str, roles: list[str] | None = None):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": title,
				"module": module,
				"public": 1,
				"content": "[]",
				"roles": [{"role": role} for role in roles or []],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		return doc

	def sidebar_with_items(self, module: str, items: list[dict]):
		sidebar = make_sidebar(module)
		sidebar.set("items", [])
		for item in items:
			sidebar.append("items", item)
		with system_write():
			return sidebar.save(ignore_permissions=True)

	def workspace_item(self, workspace) -> dict:
		return {
			"type": "Link",
			"link_type": "Workspace",
			"link_to": workspace.name,
			"label": workspace.title,
		}

	def resolved(self, module: str):
		"""What `module` resolves to for the session user: label, icon, landing and entries."""
		return resolve_sidebar(module, frappe.session.user)

	def home(self, module: str) -> str | None:
		"""Where `module` opens for the session user, by the rule the desk navigates by."""
		resolved = self.resolved(module)
		return resolved.landing if resolved else None

	def item_keys(self, module: str) -> list[str]:
		return [item["key"] for item in self.resolved(module).items]

	def reorder(self, module: str, keys: list[str], user: str | None = None):
		"""A sidebar arrangement, at the site layer or one user's own."""
		doc = frappe.get_doc(
			{
				"doctype": "Custom Sidebar",
				"module": module,
				"user": user or "",
				"sidebar_items": [{"key": key} for key in keys],
			}
		).insert(ignore_permissions=True)
		# `on_trash` clears the cached `(module, user)` set, which a DB rollback would not
		self.addCleanup(doc.delete, ignore_permissions=True)
		return doc


class TestHomeIsTheFirstNavigableItem(DerivedHomeTestCase):
	def test_the_stored_pointers_are_gone_from_the_model(self):
		"""They are removed rather than moved to the customization. Both questions are now answered
		from what the module already holds, so there is nothing left to store, validate, hand off when
		its target is deleted, or keep in step with permissions.
		"""
		fieldnames = {df.fieldname for df in frappe.get_meta("Sidebar").fields}

		self.assertNotIn("home_workspace", fieldnames)
		self.assertNotIn("module_onboarding", fieldnames)

	def test_a_module_opens_on_the_first_item_of_its_sidebar(self):
		with custom_module("Test Derived Home Module") as module:
			first = self.make_workspace(module, "Test Derived Home First")
			second = self.make_workspace(module, "Test Derived Home Second")
			self.sidebar_with_items(module, [self.workspace_item(first), self.workspace_item(second)])

			self.assertEqual(self.home(module), "/desk/test-derived-home-first")

	def test_a_user_who_cannot_see_the_first_item_lands_on_the_first_they_can(self):
		"""The point of deriving it: home resolves after permission filtering, so it can only name
		something this user can open. A stored pointer resolved before the filter and could send
		someone to a page that then refused them.
		"""
		role = self.make_role()
		user = self.make_user(roles=[role])

		with custom_module("Test Derived Home Permission Module") as module:
			restricted = self.make_workspace(module, "Test Derived Home Restricted", roles=["System Manager"])
			open_to_all = self.make_workspace(module, "Test Derived Home Open")
			self.sidebar_with_items(
				module, [self.workspace_item(restricted), self.workspace_item(open_to_all)]
			)

			self.assertEqual(self.home(module), "/desk/test-derived-home-restricted")

			with self.acting_as(user):
				self.assertEqual(self.home(module), "/desk/test-derived-home-open")

	def test_a_deleted_workspace_needs_no_hand_off(self):
		"""What the stored pointer needed a release step for. An item naming a workspace that is gone
		fails the same permission filter every other item goes through, so the module opens on the
		next one, with nothing written when it was deleted.

		Administrator bypasses that filter by definition and still sees the dead item. It leads nowhere
		either way: the server declines to route it rather than handing out a path to a page that is
		not there.

		"""
		user = self.make_user(roles=[self.make_role()])

		with custom_module("Test Derived Home Deletion Module") as module:
			doomed = self.make_workspace(module, "Test Derived Home Doomed")
			successor = self.make_workspace(module, "Test Derived Home Successor")
			self.sidebar_with_items(module, [self.workspace_item(doomed), self.workspace_item(successor)])
			with self.acting_as(user):
				self.assertEqual(self.home(module), "/desk/test-derived-home-doomed")

			frappe.delete_doc("Workspace", doomed.name, force=True)

			with self.acting_as(user):
				self.assertEqual(self.home(module), "/desk/test-derived-home-successor")
			self.assertIsNone(self.home(module))


class TestReorderingMovesTheLandingPage(DerivedHomeTestCase):
	"""Customizable at every layer for free: reordering is the mechanism, and it already exists at
	both layers.
	"""

	def test_the_site_layer_moves_it_for_everyone(self):
		role = self.make_role()
		user = self.make_user(roles=[role])

		with custom_module("Test Derived Home Site Order Module") as module:
			first = self.make_workspace(module, "Test Derived Site First")
			second = self.make_workspace(module, "Test Derived Site Second")
			self.sidebar_with_items(module, [self.workspace_item(first), self.workspace_item(second)])
			keys = self.item_keys(module)

			self.reorder(module, [keys[1], keys[0]])

			self.assertEqual(self.home(module), "/desk/test-derived-site-second")
			with self.acting_as(user):
				self.assertEqual(self.home(module), "/desk/test-derived-site-second")

	def test_a_users_own_arrangement_moves_it_for_them_alone(self):
		role = self.make_role()
		user = self.make_user(roles=[role])

		with custom_module("Test Derived Home User Order Module") as module:
			first = self.make_workspace(module, "Test Derived User First")
			second = self.make_workspace(module, "Test Derived User Second")
			self.sidebar_with_items(module, [self.workspace_item(first), self.workspace_item(second)])
			keys = self.item_keys(module)

			self.reorder(module, [keys[1], keys[0]], user=user)

			self.assertEqual(self.home(module), "/desk/test-derived-user-first")
			with self.acting_as(user):
				self.assertEqual(self.home(module), "/desk/test-derived-user-second")


class TestOnboardingIsOfferedByRole(DerivedHomeTestCase):
	"""Whether a module onboarding exists whose roles you hold, rather than a stored pointer that
	named one regardless of who was looking.
	"""

	def make_onboarding(self, name: str, module: str, roles: list[str]):
		with no_developer_mode():
			doc = frappe.get_doc(
				{
					"doctype": "Module Onboarding",
					"name": name,
					"title": name,
					"module": module,
					"allow_roles": [{"role": role} for role in roles],
				}
			).insert(ignore_permissions=True, ignore_mandatory=True)
		self.addCleanup(frappe.delete_doc, "Module Onboarding", name, force=True, ignore_missing=True)
		return doc

	def set_creation(self, name: str, creation: str):
		"""Pin creation order rather than trusting how fast two inserts ran."""
		frappe.db.set_value("Module Onboarding", name, "creation", creation, update_modified=False)

	def onboarding_of(self, module: str) -> str | None:
		resolved = self.resolved(module)
		return resolved.module_onboarding if resolved else None

	def test_a_module_with_no_onboarding_offers_none(self):
		with custom_module("Test No Onboarding Module") as module:
			make_sidebar(module)

			self.assertIsNone(self.onboarding_of(module))
			self.assertNotIn(module, get_permitted_onboardings())

	def test_it_appears_only_for_a_user_holding_one_of_its_roles(self):
		role = self.make_role()
		holder = self.make_user(roles=[role])

		with custom_module("Test Role Gated Onboarding Module") as module:
			make_sidebar(module)
			self.make_onboarding("Test Role Gated Onboarding", module, roles=[role])

			with self.acting_as(holder):
				self.assertEqual(self.onboarding_of(module), "Test Role Gated Onboarding")

	def test_a_user_holding_none_of_its_roles_is_offered_nothing(self):
		"""The check the stored pointer bypassed: it named the onboarding for everybody, and the panel
		then loaded empty for anyone the onboarding itself refused.
		"""
		gate = self.make_role("Test Onboarding Gate Role")
		outsider = self.make_user(roles=[self.make_role()])

		with custom_module("Test Refused Onboarding Module") as module:
			make_sidebar(module)
			self.make_onboarding("Test Refused Onboarding", module, roles=[gate])

			with self.acting_as(outsider):
				self.assertIsNone(self.onboarding_of(module))

	def test_a_system_manager_is_always_allowed(self):
		"""`get_allowed_roles` adds System Manager to whatever an onboarding lists, and this is the
		same rule read for the whole site at once. The two must stay in step.
		"""
		gate = self.make_role("Test Onboarding Gate Role")
		manager = self.make_user(roles=["System Manager"])

		with custom_module("Test Manager Onboarding Module") as module:
			make_sidebar(module)
			self.make_onboarding("Test Manager Onboarding", module, roles=[gate])

			with self.acting_as(manager):
				self.assertEqual(self.onboarding_of(module), "Test Manager Onboarding")

	def test_the_earlier_created_permitted_one_wins(self):
		"""A module may have two, since `Module Onboarding` is named by prompt rather than by module,
		so the choice has to be deterministic rather than whichever row came back first.
		"""
		role = self.make_role()
		holder = self.make_user(roles=[role])

		with custom_module("Test Two Onboardings Module") as module:
			make_sidebar(module)
			# inserted in the opposite order to the one that must win
			self.make_onboarding("Test Later Onboarding", module, roles=[role])
			self.make_onboarding("Test Earlier Onboarding", module, roles=[role])
			self.set_creation("Test Earlier Onboarding", "2020-01-01 00:00:00")
			self.set_creation("Test Later Onboarding", "2021-01-01 00:00:00")

			with self.acting_as(holder):
				self.assertEqual(self.onboarding_of(module), "Test Earlier Onboarding")

	def test_an_earlier_one_the_user_may_not_see_does_not_shadow_a_later_one(self):
		"""Permitted first, earliest second. Ordering before filtering would leave a user with no
		onboarding at all whenever the module's first was for somebody else.
		"""
		gate = self.make_role("Test Onboarding Gate Role")
		role = self.make_role()
		holder = self.make_user(roles=[role])

		with custom_module("Test Shadowed Onboarding Module") as module:
			make_sidebar(module)
			self.make_onboarding("Test Shadowing Onboarding", module, roles=[gate])
			self.make_onboarding("Test Shadowed Onboarding", module, roles=[role])
			self.set_creation("Test Shadowing Onboarding", "2020-01-01 00:00:00")
			self.set_creation("Test Shadowed Onboarding", "2021-01-01 00:00:00")

			with self.acting_as(holder):
				self.assertEqual(self.onboarding_of(module), "Test Shadowed Onboarding")
