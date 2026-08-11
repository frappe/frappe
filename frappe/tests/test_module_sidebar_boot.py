# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.boot import (
	build_entity_module_map,
	get_module_sidebars,
	get_navigable_modules,
	get_sidebar_bases,
)
from frappe.desk.doctype.module_sidebar.test_module_sidebar import (
	make_report,
	sidebarless_module,
	system_write,
)
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import get_visible_modules


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

	def test_resolution_walks_modules_not_rows(self):
		"""The set being resolved is the site's modules. Under today's 1:1 rows that produces
		the same payload the row-walk produced -- every module it reaches still has a row -- but
		the walk is no longer bounded by which rows happen to exist."""
		modules = set(get_navigable_modules())
		self.assertTrue(modules, "sanity: the site has modules")

		row_backed = {
			row.module
			for row in frappe.get_all("Module Sidebar", fields=["module"])
			if frappe.db.exists("Module Def", row.module)
		}
		row_backed = set(get_visible_modules(list(row_backed)))
		self.assertTrue(row_backed, "sanity: the site has module sidebars")
		self.assertTrue(row_backed <= modules, f"{row_backed - modules} would be dropped by the switch")
		self.assertTrue(set(get_module_sidebars()) <= modules)

	def test_a_module_with_no_sidebar_document_is_still_navigable(self):
		"""Nothing shipped this module a sidebar, so the system computes one from its contents
		-- the other of D4's two base origins, and the one that persists nothing."""
		with sidebarless_module("Test Computed Base Module") as module:
			make_report(module, "Test Computed Boot Report")

			self.assertIn(module, get_navigable_modules())
			sidebar = get_module_sidebars().get(module)

			self.assertIsNotNone(sidebar, "a module with no document must still resolve")
			self.assertEqual(sidebar["label"], module)
			self.assertEqual(sidebar["app"], "frappe")
			self.assertIn("Test Computed Boot Report", [item["link_to"] for item in sidebar["items"]])

	def test_deleting_a_sidebar_document_leaves_the_module_navigable(self):
		"""In the same request: no migrate, no restart. This is the defect the computed base
		dissolves -- an app that stops shipping a sidebar used to un-navigate its module."""
		with sidebarless_module("Test Deleted Document Module") as module:
			make_report(module, "Test Surviving Report")
			shipped = frappe.get_doc({"doctype": "Module Sidebar", "module": module})
			shipped.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
			# `system_write`, here and below: a sidebar document is app content, so the way one
			# reaches a site is the app's import -- which is exactly what these tests stage
			with system_write():
				shipped.insert(ignore_permissions=True)

			before = get_module_sidebars()[module]
			self.assertEqual([item["link_to"] for item in before["items"]], ["ToDo"])

			shipped.delete(ignore_permissions=True)

			after = get_module_sidebars()[module]
			self.assertIn("Test Surviving Report", [item["link_to"] for item in after["items"]])

	def test_a_shipped_document_wins_over_the_computed_base(self):
		"""The document is the base when there is one; nothing is merged into it. An app's
		sidebar is exactly what the app authored."""
		with sidebarless_module("Test Shipped Document Module") as module:
			make_report(module, "Test Uninvited Report")
			shipped = frappe.get_doc({"doctype": "Module Sidebar", "module": module, "title": "Shipped"})
			shipped.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
			with system_write():
				shipped.insert(ignore_permissions=True)

			sidebar = get_module_sidebars()[module]

			self.assertEqual(sidebar["label"], "Shipped")
			self.assertEqual([item["link_to"] for item in sidebar["items"]], ["ToDo"])

	def test_a_document_with_no_items_falls_back_to_computed_ones(self):
		"""An empty items table is not navigation -- it would drop the module from the payload,
		which is indistinguishable from shipping no sidebar at all. So it computes, same as a
		missing document."""
		with sidebarless_module("Test Empty Document Module") as module:
			make_report(module, "Test Filled In Report")
			with system_write():
				frappe.get_doc({"doctype": "Module Sidebar", "module": module}).insert(
					ignore_permissions=True
				)

			sidebar = get_module_sidebars()[module]

			self.assertIn("Test Filled In Report", [item["link_to"] for item in sidebar["items"]])

	def test_an_empty_document_still_speaks_for_itself(self):
		"""Only the rows are computed. What the document says about the module is authored
		content, so a stub someone created to name it keeps the name and gains contents."""
		with sidebarless_module("Test Stub Document Module") as module:
			make_report(module, "Test Stub Report")
			with system_write():
				frappe.get_doc(
					{"doctype": "Module Sidebar", "module": module, "title": "Stub", "header_icon": "box"}
				).insert(ignore_permissions=True)

			sidebar = get_module_sidebars()[module]

			self.assertEqual(sidebar["label"], "Stub")
			self.assertEqual(sidebar["header_icon"], "box")
			self.assertIn("Test Stub Report", [item["link_to"] for item in sidebar["items"]])

	def test_a_module_that_computes_to_nothing_is_dropped(self):
		"""A module holding no navigable content computes to an empty sidebar, and an empty
		sidebar is dropped by the same rule that drops one of only Section Breaks."""
		with sidebarless_module("Test Empty Computed Module") as module:
			self.assertIn(module, get_navigable_modules())
			self.assertNotIn(module, get_module_sidebars())

	def test_a_site_of_shipped_documents_pays_nothing_for_the_computed_route(self):
		"""The fallback runs only for the modules the documents query did not return, so a
		site whose modules all ship a sidebar reads exactly what it read before: the bases,
		then their items."""
		rowed = frappe.get_all("Module Sidebar", pluck="module", limit=5)
		self.assertTrue(rowed, "sanity: the site has module sidebars")

		with self.assertQueryCount(2):
			get_sidebar_bases(rowed)

	def test_a_customization_reshapes_a_computed_base(self):
		"""A delta reshapes a base; it is not one. With every module now given a base, a
		customization whose `Module Sidebar` was deleted out from under it lands on the
		computed one -- so the entry it produces carries a title and an app like any other,
		rather than the empty shell a baseless module would have conjured."""
		with sidebarless_module("Test Stranded Delta Module") as module:
			delta = frappe.get_doc(
				{
					"doctype": "Module Sidebar Customization",
					"module": module,
					"added_items": [{"type": "Link", "link_type": "DocType", "link_to": "ToDo"}],
				}
			).insert(ignore_permissions=True)
			# `on_trash` clears the cached `(module, user)` set, which a DB rollback would not
			self.addCleanup(delta.delete, ignore_permissions=True)

			sidebar = get_module_sidebars()[module]

			self.assertEqual(sidebar["label"], module)
			self.assertEqual(sidebar["app"], "frappe")
			self.assertEqual([item["link_to"] for item in sidebar["items"]], ["ToDo"])

	def test_every_entry_has_the_documented_shape(self):
		for sidebar in get_module_sidebars().values():
			for field in (
				"module",
				"label",
				"app",
				"header_icon",
				"module_onboarding",
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
		with system_write():
			doc.save(ignore_permissions=True)

		try:
			self.assertNotIn(module, get_module_sidebars())
		finally:
			doc.set("items", [])
			for item in original:
				doc.append("items", item)
			with system_write():
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
