# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.boot import (
	build_entity_module_map,
	get_module_sidebars,
	get_navigable_modules,
	get_sidebar_bases,
)
from frappe.desk.doctype.custom_module_sidebar.test_custom_module_sidebar import make_user
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
		"""The set being resolved is the site's modules, and the modules that happen to have a
		row are a subset of it -- so nothing the old row-walk reached is dropped by the switch,
		and the walk is no longer bounded by which rows exist.

		The row is staged: nothing ships a `Module Sidebar`, so on a stock site the old walk
		had nothing to reach and the comparison would hold vacuously.
		"""
		with sidebarless_module("Test Row Backed Module") as rowed_module:
			with system_write():
				frappe.get_doc(
					{"doctype": "Module Sidebar", "module": rowed_module, "title": "Rowed"}
				).insert(ignore_permissions=True)

			modules = set(get_navigable_modules())
			self.assertTrue(modules, "sanity: the site has modules")

			row_backed = {
				row.module
				for row in frappe.get_all("Module Sidebar", fields=["module"])
				if frappe.db.exists("Module Def", row.module)
			}
			row_backed = set(get_visible_modules(list(row_backed)))
			self.assertIn(rowed_module, row_backed, "sanity: the staged row is visible")
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
		then their items.

		Staged rather than read off the site: nothing ships a `Module Sidebar`, so a stock site
		has no rows at all and the assertion would be measuring the computed route instead.
		"""
		with sidebarless_module("Test All Rowed Module") as module:
			with system_write():
				shipped = frappe.get_doc({"doctype": "Module Sidebar", "module": module})
				shipped.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
				shipped.insert(ignore_permissions=True)

			with self.assertQueryCount(2):
				get_sidebar_bases([module])

	def test_a_customization_reshapes_a_computed_base(self):
		"""A delta reshapes a base; it is not one. With every module now given a base, a
		customization whose `Module Sidebar` was deleted out from under it lands on the
		computed one -- so the entry it produces carries a title and an app like any other,
		rather than the empty shell a baseless module would have conjured."""
		with sidebarless_module("Test Stranded Delta Module") as module:
			delta = frappe.get_doc(
				{
					"doctype": "Custom Module Sidebar",
					"module": module,
					"sidebar_items": [
						{"added": 1, "type": "Link", "link_type": "DocType", "link_to": "ToDo"}
					],
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
		"""Per-user customization anchors on the item's identity, so the payload has to carry
		it -- it is what a saved arrangement sends back."""
		for sidebar in get_module_sidebars().values():
			for item in sidebar["items"]:
				self.assertTrue(item.get("key"), f"{sidebar['module']} has an item with no key")

	def test_the_payload_names_each_item_once(self):
		"""What the deleted uniqueness validator used to promise, kept where it can be: rows
		arrive here from a shipped document, a computed base and a layer's added rows alike, so
		the resolution is the only place that sees the whole list. Two items sharing a key
		would be one item a customization cannot name without naming the other."""
		for sidebar in get_module_sidebars().values():
			keys = [item["key"] for item in sidebar["items"]]
			self.assertEqual(len(set(keys)), len(keys), f"{sidebar['module']} repeats an item")

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

	def test_a_private_page_is_not_in_anyone_elses_module_workspaces(self):
		"""`workspaces` is the workspaces of a module this *reader* may open, which is what the
		desk asks it: given a route naming a workspace, which module's shell does it belong to?
		The reader's own private pages answer that question; nobody else's do."""
		from frappe.boot import get_module_workspaces

		for module, names in get_module_workspaces().items():
			for name in names:
				public, for_user = frappe.db.get_value("Workspace", name, ["public", "for_user"])
				self.assertTrue(
					public or for_user == frappe.session.user,
					f"{module} lists {name}, which belongs to {for_user}",
				)

	def test_workspace_payload_carries_the_module_keyspace(self):
		"""Every mutating workspace endpoint returns this for the client to hot-swap."""
		from frappe.desk.doctype.workspace.workspace import workspace_payload

		payload = workspace_payload()
		for key in ("workspace_pages", "app_data", "module_sidebars", "entity_module"):
			self.assertIn(key, payload)
		self.assertNotIn("sidebar_items", payload)


class TestPrivateWorkspacesAreDerived(IntegrationTestCase):
	"""D3: a private workspace's sidebar link is not stored anywhere.

	The workspace already carries its module, its owner, its title and its icon, so the sidebar
	appends "my private workspaces in this module" on read. What that removes is the layer
	pollution: the shared document used to accumulate a row per private page, so an admin
	curating the site's sidebar found strangers' pages in the document they were editing -- and
	every one of those rows was a second copy of four columns that could change underneath it.
	"""

	OWNER = "test-derived-private-owner@example.com"
	STRANGER = "test-derived-private-stranger@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.module = self.enterContext(sidebarless_module("Test Private Workspace Module"))
		for email in (self.OWNER, self.STRANGER):
			make_user(email, ["System Manager"])
			self.addCleanup(frappe.delete_doc, "User", email, force=True, ignore_missing=True)
		self.addCleanup(frappe.set_user, "Administrator")

	def as_user(self, user):
		frappe.set_user(user)
		# `get_workspaces` is request-cached and `set_user` does not clear it, so without this
		# the second reader in a test would be answered with the first one's workspaces
		if getattr(frappe.local, "request_cache", None):
			frappe.local.request_cache.clear()

	def make_private_workspace(self, title, for_user, module=None):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": f"{title}-{for_user}",
				"module": module or self.module,
				"public": 0,
				"for_user": for_user,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		return doc

	def items_for(self, user):
		self.as_user(user)
		return get_module_sidebars().get(self.module, {}).get("items", [])

	def test_the_owner_gets_a_link_to_their_private_page(self):
		workspace = self.make_private_workspace("Test Derived Private Page", self.OWNER)

		links = [item["link_to"] for item in self.items_for(self.OWNER)]

		self.assertIn(workspace.name, links)

	def test_creating_one_stores_no_row_anywhere(self):
		"""The write path branches on public and the private branch writes nothing -- so there
		is no customization holding the link, and no item row naming it in any document."""
		from frappe.desk.doctype.workspace.workspace import new_page

		with system_write():
			frappe.get_doc(
				{
					"doctype": "Module Sidebar",
					"module": self.module,
					"items": [{"type": "Link", "link_type": "DocType", "link_to": "ToDo"}],
				}
			).insert(ignore_permissions=True)

		self.as_user(self.OWNER)
		new_page(
			{
				"title": "Test Unstored Private Page",
				"label": f"Test Unstored Private Page-{self.OWNER}",
				"content": "[]",
				"public": 0,
				"for_user": self.OWNER,
				"module": self.module,
				"type": "Workspace",
			}
		)
		name = f"Test Unstored Private Page-{self.OWNER}"
		self.addCleanup(frappe.delete_doc, "Workspace", name, force=True, ignore_missing=True)

		frappe.set_user("Administrator")
		self.assertFalse(
			frappe.db.exists("Custom Module Sidebar", {"module": self.module}),
			"a private page must not open a customization on the module",
		)
		self.assertFalse(
			frappe.db.exists("Module Sidebar Item", {"link_type": "Workspace", "link_to": name}),
			"no item row anywhere may name a private page",
		)
		# and the derived one is there all the same
		self.assertIn(name, [item["link_to"] for item in self.items_for(self.OWNER)])

	def test_nobody_else_sees_it(self):
		"""Owner-scoped by the query that derives it, so it is not a filter that could be
		forgotten -- a stranger's sidebar is never handed the row in the first place."""
		make_report(self.module, "Test Derived Private Neighbour Report")
		workspace = self.make_private_workspace("Test Somebody Elses Page", self.OWNER)

		links = [item["link_to"] for item in self.items_for(self.STRANGER)]

		self.assertIn("Test Derived Private Neighbour Report", links, "sanity: the module resolves")
		self.assertNotIn(workspace.name, links)

	def test_a_module_whose_only_page_is_private_is_still_navigable(self):
		"""The derivation runs before the "nothing navigable here" rule drops a module, so a
		page somebody created in an otherwise empty module does not land on no dock."""
		workspace = self.make_private_workspace("Test Only Page In The Module", self.OWNER)

		self.assertNotIn(self.module, self.stranger_payload(), "sanity: empty for everyone else")

		self.as_user(self.OWNER)
		sidebar = get_module_sidebars().get(self.module)
		self.assertIsNotNone(sidebar)
		self.assertEqual([item["link_to"] for item in sidebar["items"]], [workspace.name])

	def stranger_payload(self):
		self.as_user(self.STRANGER)
		return get_module_sidebars()

	def test_the_link_says_it_is_derived(self):
		"""What the desk needs in order not to offer it as something to arrange: no document
		holds it, so no arrangement can name it."""
		self.make_private_workspace("Test Marked Private Page", self.OWNER)

		item = next(i for i in self.items_for(self.OWNER) if i["link_type"] == "Workspace")

		self.assertEqual(item["derived"], 1)

	def test_a_row_stored_before_the_derivation_is_not_rendered_twice(self):
		"""A site that stored these links keeps rendering one link, in the position its layer
		put it -- the derived one is the duplicate, and it is the one that gives way."""
		from frappe.desk.doctype.custom_module_sidebar.custom_module_sidebar import (
			CUSTOMIZED_KEYS_CACHE_KEY,
			add_site_sidebar_item,
		)

		workspace = self.make_private_workspace("Test Legacy Stored Page", self.OWNER)
		# stored while it was still public, which is the only way such a row was ever written
		frappe.db.set_value("Workspace", workspace.name, {"public": 1, "for_user": ""})
		add_site_sidebar_item(
			self.module,
			{"type": "Link", "label": "Stored", "link_type": "Workspace", "link_to": workspace.name},
		)
		layer = frappe.db.get_value("Custom Module Sidebar", {"module": self.module})
		self.addCleanup(frappe.cache.delete_value, CUSTOMIZED_KEYS_CACHE_KEY)
		self.addCleanup(
			frappe.delete_doc, "Custom Module Sidebar", layer, force=True, ignore_permissions=True
		)
		frappe.db.set_value("Workspace", workspace.name, {"public": 0, "for_user": self.OWNER})

		links = [item["link_to"] for item in self.items_for(self.OWNER)]

		self.assertEqual(links.count(workspace.name), 1)
