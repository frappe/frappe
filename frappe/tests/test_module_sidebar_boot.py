# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.boot import build_entity_module_map, get_module_sidebars
from frappe.tests import IntegrationTestCase


class TestModuleSidebarBoot(IntegrationTestCase):
	"""The module-keyed boot payload -- now the only navigation payload."""

	def setUp(self):
		frappe.set_user("Administrator")

	def test_keyed_by_exact_case_module_name(self):
		"""The point of the switch: `app_data[].modules` holds exact Module Def names, so it
		must index straight into this payload. The legacy key is `title.lower()`."""
		payload = get_module_sidebars()
		self.assertTrue(payload, "sanity: the site has module sidebars")

		for key, sidebar in payload.items():
			self.assertEqual(key, sidebar["module"])
			self.assertTrue(frappe.db.exists("Module Def", key), f"{key} is not a Module Def")

	def test_every_entry_has_the_documented_shape(self):
		for sidebar in get_module_sidebars().values():
			for field in (
				"module",
				"label",
				"app",
				"header_icon",
				"module_onboarding",
				"home_workspace",
				"generated",
				"workspaces",
				"items",
			):
				self.assertIn(field, sidebar)
			self.assertIsInstance(sidebar["workspaces"], list)
			self.assertIsInstance(sidebar["items"], list)

	def test_items_carry_their_key(self):
		"""Per-user customization anchors on `key`, so the payload has to carry it."""
		for sidebar in get_module_sidebars().values():
			for item in sidebar["items"]:
				self.assertTrue(item.get("key"), f"{sidebar['module']} has an item with no key")

	def test_a_sidebar_of_only_section_breaks_is_dropped(self):
		"""Same rule as the legacy builder, mirrored by `is_icon_permitted`. If these two
		ever disagree, an icon appears for a sidebar that renders empty."""
		module = next(iter(get_module_sidebars()), None)
		self.assertIsNotNone(module, "sanity: at least one module sidebar")

		doc = frappe.get_doc("Module Sidebar", module)
		original = [i.as_dict() for i in doc.items]
		doc.set("items", [])
		doc.append("items", {"type": "Section Break", "label": "Only a section"})
		doc.save(ignore_permissions=True)

		try:
			self.assertNotIn(module, get_module_sidebars())
		finally:
			doc.set("items", [])
			for item in original:
				doc.append("items", item)
			doc.save(ignore_permissions=True)

	def test_legacy_keyspaces_are_gone(self):
		"""One keyspace, exact-case module name. The desk used to reconcile four for the same
		identity, across three overlapping boot payloads."""
		from frappe.boot import get_bootinfo

		frappe.set_user("Administrator")
		boot = get_bootinfo()

		for retired in ("workspace_sidebar_item", "default_workspace_map", "module_wise_workspaces"):
			self.assertNotIn(retired, boot, f"{retired} should have been retired")

		self.assertTrue(boot.get("module_sidebars"))
		self.assertIn("entity_module", boot)

	def test_entity_module_only_names_visible_modules(self):
		"""Built from the already-filtered payload, so it can never point at something the
		user cannot see."""
		modules = get_module_sidebars()
		entity_module = build_entity_module_map(modules)

		for entity, module in entity_module.items():
			self.assertIn(module, modules, f"{entity} -> {module} is not in the payload")

	def test_workspace_payload_carries_the_module_keyspace(self):
		"""Every mutating workspace endpoint returns this for the client to hot-swap."""
		from frappe.desk.doctype.workspace.workspace import workspace_payload

		payload = workspace_payload()
		for key in ("workspace_pages", "app_data", "module_sidebars", "entity_module"):
			self.assertIn(key, payload)
		self.assertNotIn("sidebar_items", payload)
