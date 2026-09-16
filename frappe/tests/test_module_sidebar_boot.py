# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from unittest.mock import patch

import frappe
from frappe.boot import build_entity_module_map, get_bootinfo, get_module_sidebars
from frappe.core.doctype.module_def.test_module_def import custom_module
from frappe.desk.doctype.custom_sidebar.test_custom_sidebar import make_user
from frappe.desk.doctype.sidebar.sidebar import (
	SidebarContext,
	filter_sidebar_items,
	get_module_landing_route,
	get_navigable_modules,
	get_sidebar_bases,
	resolve_sidebar,
)
from frappe.desk.doctype.sidebar.test_sidebar import (
	make_report,
	make_sidebar,
	no_developer_mode,
	sidebarless_module,
	system_write,
)
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import get_visible_modules


class TestTheResolverSeam(IntegrationTestCase):
	"""`resolve_sidebar`: what a Scope resolves to, for one user.

	Everything that shapes an answer lives behind this one call: the permission filter, the layers,
	the private-page append, and the rule that drops a Scope holding nothing navigable. The boot
	payload is assembly on top of it, and every other reader of a resolved arrangement, such as the
	desktop tile or a Scope fetched on arrival, asks the same question the same way instead of
	reaching into a payload built for somebody else.

	"""

	def setUp(self):
		frappe.set_user("Administrator")

	def test_the_payload_is_the_seams_answers_and_nothing_else(self):
		"""The builder chooses the set and assembles; it decides nothing. So every key in the payload
		is one resolution, and every shell missing from it resolved to `None`.
		"""
		user = frappe.session.user
		payload = get_module_sidebars()

		for shell in get_sidebar_bases(get_navigable_modules()):
			resolved = resolve_sidebar(shell, user)
			if resolved is None:
				self.assertNotIn(shell, payload, f"{shell} resolved to nothing but is in the payload")
			else:
				self.assertEqual(payload[shell], resolved.as_boot_entry())

	def test_a_scope_resolves_the_same_alone_as_it_does_in_a_batch(self):
		"""The context is a batching detail only: resolving seventy Scopes must not answer differently
		from resolving one.
		"""
		with sidebarless_module("Test Seam Batching Module") as module:
			make_report(module, "Test Seam Batching Report")
			user = frappe.session.user

			batched = resolve_sidebar(module, user, SidebarContext.for_modules([module], user))
			alone = resolve_sidebar(module, user)

			self.assertEqual(alone.as_boot_entry(), batched.as_boot_entry())

	def test_a_context_cannot_answer_for_a_second_reader(self):
		"""Some of what a context batches belongs to one user, such as their private pages and the
		onboardings their roles allow, so lending it to another user would hand out someone else's
		private workspaces. This is checked rather than documented.
		"""
		with sidebarless_module("Test Seam Borrowed Context Module") as module:
			make_report(module, "Test Seam Borrowed Context Report")
			context = SidebarContext.for_modules([module], "Administrator")

			with self.assertRaises(ValueError):
				resolve_sidebar(module, "somebody-else@example.com", context)

	def test_a_scope_holding_nothing_navigable_resolves_to_nothing(self):
		"""`None` is how the resolver says dropped, which is what the payload's missing key means. It
		is stated once here rather than by each reader re-checking the items.
		"""
		with sidebarless_module("Test Seam Empty Module") as module:
			self.assertIsNone(resolve_sidebar(module, frappe.session.user))

	def test_the_seam_answers_where_the_scope_opens(self):
		"""Landing is part of the arrangement rather than something a caller derives afterwards: it can
		only be read correctly off the list this user resolved.
		"""
		with sidebarless_module("Test Seam Landing Module") as module:
			workspace = frappe.get_doc(
				{
					"doctype": "Workspace",
					"title": "Test Seam Landing Page",
					"label": "Test Seam Landing Page",
					"module": module,
					"public": 1,
					"content": "[]",
				}
			).insert(ignore_permissions=True)
			self.addCleanup(frappe.delete_doc, "Workspace", workspace.name, force=True, ignore_missing=True)

			doc = frappe.get_doc({"doctype": "Sidebar", "module": module})
			doc.append(
				"items",
				{"type": "Link", "link_type": "Workspace", "link_to": workspace.name, "label": "Home"},
			)
			with system_write():
				doc.insert(ignore_permissions=True)

			resolved = resolve_sidebar(module, frappe.session.user)

			self.assertEqual(resolved.landing, "/desk/test-seam-landing-page")
			self.assertEqual(resolved.landing, get_module_landing_route(resolved.items))

	def test_a_module_opening_on_a_doctype_lands_on_its_list(self):
		"""A sidebar need not start on a workspace. `Bulk Transaction` has no workspace at all, and
		answering `None` for it left its tile with nowhere to go, so a module whose first entry is a
		list opens on that list.
		"""
		self.assertEqual(
			get_module_landing_route([{"type": "Link", "link_type": "DocType", "link_to": "ToDo"}]),
			"/desk/todo",
		)

	def test_a_single_opens_on_the_document_itself(self):
		"""There is no list to send anyone to."""
		self.assertEqual(
			get_module_landing_route(
				[{"type": "Link", "link_type": "DocType", "link_to": "System Settings"}]
			),
			"/desk/system-settings/System Settings",
		)

	def test_a_child_table_is_not_somewhere_to_land(self):
		"""It has no list view, so a tile pointing at one would open on nothing. Better to fall back
		to the client, which knows the rest of the routing rules.
		"""
		child = frappe.get_all("DocType", filters={"istable": 1}, limit=1, pluck="name")[0]

		self.assertIsNone(
			get_module_landing_route([{"type": "Link", "link_type": "DocType", "link_to": child}])
		)

	def test_a_report_is_still_left_to_the_client(self):
		"""Report types and filters live in `generate_route`, and a second copy of those rules here
		would be one to keep in step."""
		self.assertIsNone(
			get_module_landing_route(
				[{"type": "Link", "link_type": "Report", "link_to": "Permitted Documents For User"}]
			)
		)

	def test_the_landing_is_derived_rather_than_carried(self):
		"""Boot never asks for it, since seventy modules would be seventy lookups to answer a question
		the desk asks about the one it is opening. So it is not in the payload, and the tile list
		derives it for the few modules it lists.
		"""
		for entry in get_module_sidebars().values():
			self.assertNotIn("landing", entry)


class TestSidebarBoot(IntegrationTestCase):
	"""The module-keyed boot payload, now the only navigation payload."""

	def setUp(self):
		frappe.set_user("Administrator")

	def test_keyed_by_exact_case_shell_identity(self):
		"""One keyspace, in exact case: a `Sidebar` document's own name, or the module's name where the
		base was computed. The legacy key is `title.lower()`.

		An entry carries its own key, so nothing has to recover it by position.

		"""
		payload = get_module_sidebars()
		self.assertTrue(payload, "sanity: the site has sidebars")

		for key, sidebar in payload.items():
			self.assertEqual(key, sidebar["name"])
			self.assertTrue(frappe.db.exists("Module Def", sidebar["module"]))
			if key != sidebar["module"]:
				self.assertTrue(
					frappe.db.exists("Sidebar", {"name": key, "module": sidebar["module"]}),
					f"{key} is neither its module's name nor a document under it",
				)

	def test_a_modules_second_sidebar_is_in_the_payload_beside_its_first(self):
		"""The point of the re-key. Keyed by module, a dict keeps one value per key, so the second
		sidebar under a module was overwritten by whichever was read last and disappeared from the
		desk with no error.
		"""
		with sidebarless_module("Test Two Shells Module") as module:
			with system_write():
				for title, link in (("Test Two Shells Module", "ToDo"), ("Test Two Shells Deals", "User")):
					doc = frappe.get_doc({"doctype": "Sidebar", "module": module, "title": title})
					doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": link})
					doc.insert(ignore_permissions=True)

			payload = get_module_sidebars()

			self.assertIn("Test Two Shells Module", payload)
			self.assertIn("Test Two Shells Deals", payload)
			self.assertEqual(payload["Test Two Shells Deals"]["module"], module)
			self.assertEqual(
				[item["link_to"] for item in payload["Test Two Shells Deals"]["items"]], ["User"]
			)

	def test_a_sidebar_named_otherwise_is_keyed_by_its_own_name(self):
		"""Shell identity is the document's name, so a module named by none of its sidebars is not a
		key at all. What the desk shows is the sidebar, and the sidebar is called what its author
		called it.
		"""
		with sidebarless_module("Test Renamed Shell Module") as module:
			with system_write():
				doc = frappe.get_doc({"doctype": "Sidebar", "module": module, "title": "Test Renamed Shell"})
				doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
				doc.insert(ignore_permissions=True)

			payload = get_module_sidebars()

			self.assertIn("Test Renamed Shell", payload)
			self.assertNotIn(module, payload)
			self.assertEqual(payload["Test Renamed Shell"]["module"], module)

	def test_frappes_eleven_keys_do_not_move(self):
		"""The re-key is meant to be invisible wherever an author did not diverge. Frappe ships eleven
		sidebars and titles every one after its module, so none of the keys changes.
		"""
		payload = get_module_sidebars()
		shipped = frappe.get_all(
			"Sidebar", filters={"standard": 1, "app": "frappe"}, fields=["name", "module"]
		)
		self.assertTrue(shipped, "sanity: frappe's sidebars are imported")

		moved = [row.name for row in shipped if row.name != row.module and row.name in payload]
		self.assertEqual(moved, [])
		for row in shipped:
			self.assertIn(row.name, payload)

	def test_resolution_walks_modules_not_rows(self):
		"""The set being resolved is the site's modules, and the modules that have a row are a subset
		of it, so nothing the old row-walk reached is dropped by the switch and the walk is no longer
		bounded by which rows exist.

		The row is staged: nothing ships a `Sidebar`, so on a stock site the old walk had nothing to
		reach and the comparison would hold vacuously.

		"""
		with sidebarless_module("Test Row Backed Module") as rowed_module:
			with system_write():
				frappe.get_doc({"doctype": "Sidebar", "module": rowed_module, "title": "Rowed"}).insert(
					ignore_permissions=True
				)

			modules = set(get_navigable_modules())
			self.assertTrue(modules, "sanity: the site has modules")

			row_backed = {
				row.module
				for row in frappe.get_all("Sidebar", fields=["module"])
				if frappe.db.exists("Module Def", row.module)
			}
			row_backed = set(get_visible_modules(list(row_backed)))
			self.assertIn(rowed_module, row_backed, "sanity: the staged row is visible")
			self.assertTrue(row_backed <= modules, f"{row_backed - modules} would be dropped by the switch")
			# The payload is keyed by shell, so it must stay inside the modules those shells
			# belong to. The walk is still bounded by the module set.
			self.assertTrue({entry["module"] for entry in get_module_sidebars().values()} <= modules)

	def test_a_module_with_no_sidebar_document_is_still_navigable(self):
		"""Nothing shipped this module a sidebar, so the system computes one from its contents. That
		is the other of D4's two base origins, and the one that persists nothing.
		"""
		with sidebarless_module("Test Computed Base Module") as module:
			make_report(module, "Test Computed Boot Report")

			self.assertIn(module, get_navigable_modules())
			sidebar = get_module_sidebars().get(module)

			self.assertIsNotNone(sidebar, "a module with no document must still resolve")
			self.assertEqual(sidebar["label"], module)
			self.assertEqual(sidebar["app"], "frappe")
			self.assertIn("Test Computed Boot Report", [item["link_to"] for item in sidebar["items"]])

	def test_deleting_a_sidebar_document_leaves_the_module_navigable(self):
		"""In the same request: no migrate and no restart. This is the defect the computed base fixes,
		since an app that stopped shipping a sidebar used to leave its module un-navigable.
		"""
		with sidebarless_module("Test Deleted Document Module") as module:
			make_report(module, "Test Surviving Report")
			shipped = frappe.get_doc({"doctype": "Sidebar", "module": module})
			shipped.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
			# `system_write`, here and below: a sidebar document is app content, so the only way
			# one reaches a site is the app's import, which is what these tests stage.
			with system_write():
				shipped.insert(ignore_permissions=True)

			before = get_module_sidebars()[module]
			self.assertEqual([item["link_to"] for item in before["items"]], ["ToDo"])

			shipped.delete(ignore_permissions=True)

			after = get_module_sidebars()[module]
			self.assertIn("Test Surviving Report", [item["link_to"] for item in after["items"]])

	def test_a_shipped_document_wins_over_the_computed_base(self):
		"""The document is the base when there is one; nothing is merged into it. An app's sidebar is
		exactly what the app authored.
		"""
		with sidebarless_module("Test Shipped Document Module") as module:
			make_report(module, "Test Uninvited Report")
			shipped = frappe.get_doc({"doctype": "Sidebar", "module": module, "title": "Shipped"})
			shipped.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
			with system_write():
				shipped.insert(ignore_permissions=True)

			# Keyed by the document's own name, which is its title. The module is not a shell
			# here, because none of its sidebars is named after it.
			sidebar = get_module_sidebars()["Shipped"]

			self.assertEqual(sidebar["label"], "Shipped")
			self.assertEqual([item["link_to"] for item in sidebar["items"]], ["ToDo"])

	def test_a_document_with_no_items_falls_back_to_computed_ones(self):
		"""An empty items table is not navigation. It would drop the module from the payload, which is
		indistinguishable from shipping no sidebar, so it computes, the same as a missing document.
		"""
		with sidebarless_module("Test Empty Document Module") as module:
			make_report(module, "Test Filled In Report")
			with system_write():
				frappe.get_doc({"doctype": "Sidebar", "module": module}).insert(ignore_permissions=True)

			sidebar = get_module_sidebars()[module]

			self.assertIn("Test Filled In Report", [item["link_to"] for item in sidebar["items"]])

	def test_an_empty_document_still_speaks_for_itself(self):
		"""Only the rows are computed. What the document says about the module is authored content, so
		a stub someone created to name it keeps the name and gains contents.
		"""
		with sidebarless_module("Test Stub Document Module") as module:
			make_report(module, "Test Stub Report")
			with system_write():
				frappe.get_doc(
					{"doctype": "Sidebar", "module": module, "title": "Stub", "header_icon": "box"}
				).insert(ignore_permissions=True)

			sidebar = get_module_sidebars()["Stub"]

			self.assertEqual(sidebar["label"], "Stub")
			self.assertEqual(sidebar["header_icon"], "box")
			self.assertIn("Test Stub Report", [item["link_to"] for item in sidebar["items"]])

	def test_a_module_that_computes_to_nothing_is_dropped(self):
		"""A module holding no navigable content computes to an empty sidebar, and an empty sidebar is
		dropped by the same rule that drops one holding only Section Breaks.
		"""
		with sidebarless_module("Test Empty Computed Module") as module:
			self.assertIn(module, get_navigable_modules())
			self.assertNotIn(module, get_module_sidebars())

	def test_a_site_of_shipped_documents_pays_nothing_for_the_computed_route(self):
		"""The fallback runs only for the modules the documents query did not return, so a site whose
		modules all ship a sidebar reads exactly what it read before: the bases, then their items.

		It is staged rather than read off the site: nothing ships a `Sidebar`, so a stock site has no
		rows at all and the assertion would measure the computed route instead.

		"""
		with sidebarless_module("Test All Rowed Module") as module:
			with system_write():
				shipped = frappe.get_doc({"doctype": "Sidebar", "module": module})
				shipped.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
				shipped.insert(ignore_permissions=True)

			# once first, so the count below is the route's own queries and not a cold
			# schema cache: a table's column list is looked up once per site and cached
			get_sidebar_bases([module])

			with self.assertQueryCount(2):
				get_sidebar_bases([module])

	def test_computing_every_base_costs_the_same_as_computing_one(self):
		"""The point of the batch. A boot on a site where nothing ships a sidebar has to compute a base
		per module, and the cost must not grow with the module count.

		Five queries, one per kind of thing a module can hold, whether it is asked about one module or
		all of them.

		"""
		from frappe.desk.doctype.sidebar.sidebar import get_module_contents

		modules = get_navigable_modules()
		self.assertGreater(len(modules), 5, "sanity: a real set of modules to batch")

		# once first, so the counts below are the reads themselves and not a cold schema cache
		get_module_contents(modules)

		with self.assertQueryCount(5):
			get_module_contents(modules[:1])

		with self.assertQueryCount(5):
			get_module_contents(modules)

	def test_reading_a_sidebar_does_not_write_to_the_cache(self):
		"""`frappe.cache.hget` keeps a copy in `frappe.local.cache` and returns the same object every
		time within a request. `get_sidebar_bases` stamps `computed` on every sidebar it returns, so
		without a copy it would be stamping the cache.
		"""
		from frappe.desk.doctype.sidebar.sidebar import COMPUTED_BASE_CACHE_KEY

		with sidebarless_module("Test Cache Isolation Module") as module:
			base = get_sidebar_bases([module])[module]
			self.assertEqual(base.computed, 1, "sanity: the caller was handed a stamped copy")

			cached = frappe.cache.hget(COMPUTED_BASE_CACHE_KEY, module)
			self.assertNotIn("computed", cached, "the cached sidebar must not carry the stamp")

	def test_a_computed_base_says_it_is_computed(self):
		"""So the desk can tell an app leaving something out from the display limit doing so. An entity
		missing from a shipped sidebar was left out on purpose; one missing from a computed sidebar
		may have fallen past `COMPUTED_DOCTYPE_LIMIT`, and routing must not read the two the same
		way.
		"""
		with sidebarless_module("Test Says Computed Module") as module:
			self.assertEqual(get_sidebar_bases([module])[module].computed, 1)

			with system_write():
				shipped = frappe.get_doc({"doctype": "Sidebar", "module": module})
				shipped.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
				shipped.insert(ignore_permissions=True)

			self.assertEqual(get_sidebar_bases([module])[module].computed, 0)

	def test_an_empty_document_is_computed_even_though_it_exists(self):
		"""Its rows came from the module's contents, so its membership answers are the computed kind
		however the document itself got there.
		"""
		with sidebarless_module("Test Empty Doc Computed Module") as module:
			with system_write():
				frappe.get_doc({"doctype": "Sidebar", "module": module, "title": "Named"}).insert(
					ignore_permissions=True
				)

			base = get_sidebar_bases([module])["Named"]

			self.assertEqual(base.title, "Named", "what the document says about itself stands")
			self.assertEqual(base.computed, 1, "but its rows were computed")

	def test_a_customization_reshapes_a_computed_base(self):
		"""A delta reshapes a base; it is not one. With every module given a base, a customization
		whose `Sidebar` was deleted underneath it lands on the computed one, so the entry it produces
		carries a title and an app like any other rather than the empty shell a baseless module would
		have produced.
		"""
		with sidebarless_module("Test Stranded Delta Module") as module:
			delta = frappe.get_doc(
				{
					"doctype": "Custom Sidebar",
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
				"name",
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
		"""Per-user customization anchors on the item's identity, so the payload has to carry it. It is
		what a saved arrangement sends back.
		"""
		for sidebar in get_module_sidebars().values():
			for item in sidebar["items"]:
				self.assertTrue(item.get("key"), f"{sidebar['module']} has an item with no key")

	def test_the_payload_names_each_item_once(self):
		"""What the deleted uniqueness validator used to promise, kept where it can be. Rows arrive
		here from a shipped document, a computed base and a layer's added rows alike, so the
		resolution is the only place that sees the whole list. Two items sharing a key would be one
		item a customization cannot name without naming the other.
		"""
		for sidebar in get_module_sidebars().values():
			keys = [item["key"] for item in sidebar["items"]]
			self.assertEqual(len(set(keys)), len(keys), f"{sidebar['module']} repeats an item")

	def test_a_sidebar_of_only_section_breaks_is_dropped(self):
		"""The same rule as the legacy builder, mirrored by `is_icon_permitted`. If those two disagree,
		an icon appears for a sidebar that renders empty.

		It is staged on a module of its own: nothing writes a `Sidebar` on a site's behalf, so
		borrowing whichever one happened to be there would be borrowing nothing.

		"""
		with sidebarless_module("Test Sectioned Module") as module:
			with system_write():
				doc = frappe.get_doc({"doctype": "Sidebar", "module": module})
				doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
				doc.insert(ignore_permissions=True)

			self.assertIn(module, get_module_sidebars())

			doc.set("items", [])
			doc.append("items", {"type": "Section Break", "label": "Only a section"})
			with system_write():
				doc.save(ignore_permissions=True)

			self.assertNotIn(module, get_module_sidebars())

	def test_a_module_is_dropped_when_the_user_can_open_nothing_in_it(self):
		"""A shell needs one item the user can open; being in reach does not earn one.

		So module visibility follows item permissions, with the known cost that a doctype curated
		into a foreign module makes that module visible to anyone who can read it (#39868).

		Staged with a doctype only System Manager may read, so the permission filter is what
		empties the base.

		Asked as each user rather than only about them: the item filter reads the session user's
		permissions, so the `user` argument alone would still be answered as whoever is logged in,
		and every item would pass for an Administrator running the test.
		"""
		user = make_user("test-shell-nothing-open@example.com", ["Desk User"])
		with sidebarless_module("Test Shell Nothing Open Module") as module:
			with system_write():
				doc = frappe.get_doc({"doctype": "Sidebar", "module": module})
				doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "Role"})
				doc.insert(ignore_permissions=True)

			self.assertIsNotNone(
				resolve_sidebar(module, "Administrator"),
				"the shell exists for someone who can open its item",
			)
			with self.set_user(user.name):
				self.assertIsNone(
					resolve_sidebar(module, user.name),
					"and is dropped for someone who cannot, rather than rendering blank",
				)

	def test_a_module_out_of_reach_loses_its_shell_even_with_items(self):
		"""The other half of the same rule: blocking is what hides a module, and it hides one
		whose items the user could otherwise have seen."""
		user = make_user("test-shell-out-of-reach@example.com", ["Desk User"])
		with sidebarless_module("Test Shell Out Of Reach Module") as module:
			with system_write():
				doc = frappe.get_doc({"doctype": "Sidebar", "module": module})
				doc.append("items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo"})
				doc.insert(ignore_permissions=True)

			self.assertIsNotNone(resolve_sidebar(module, user.name))

			blocked = frappe.get_doc("User", user.name)
			blocked.append("block_modules", {"module": module})
			blocked.save(ignore_permissions=True)
			frappe.clear_cache(user=user.name)

			self.assertNotIn(module, get_visible_modules([module], user.name))

	def test_legacy_keyspaces_are_gone(self):
		"""One keyspace, the exact-case module name. The desk used to reconcile four for the same
		identity, across three overlapping boot payloads.
		"""
		from frappe.boot import get_bootinfo

		frappe.set_user("Administrator")
		boot = get_bootinfo()

		for retired in ("workspace_sidebar_item", "default_workspace_map", "module_wise_workspaces"):
			self.assertNotIn(retired, boot, f"{retired} should have been retired")

		self.assertTrue(boot.get("module_sidebars"))
		self.assertIn("entity_module", boot)

	def test_entity_module_only_names_shells_in_the_payload(self):
		"""Built from the already-filtered payload and keyed the same way, so what it names indexes
		straight back in and can never be something the user cannot see.
		"""
		shells = get_module_sidebars()
		entity_module = build_entity_module_map(shells)

		for entity, shell in entity_module.items():
			self.assertIn(shell, shells, f"{entity} -> {shell} is not in the payload")

	def test_a_private_page_is_not_in_anyone_elses_module_workspaces(self):
		"""`workspaces` is the workspaces of a module this user may open, which is what the desk asks:
		given a route naming a workspace, which module's shell does it belong to? The user's own
		private pages answer that; nobody else's do.
		"""
		from frappe.desk.doctype.sidebar.sidebar import get_module_workspaces

		for module, names in get_module_workspaces().items():
			for name in names:
				public, for_user = frappe.db.get_value("Workspace", name, ["public", "for_user"])
				self.assertTrue(
					public or for_user == frappe.session.user,
					f"{module} lists {name}, which belongs to {for_user}",
				)

	def test_workspace_payload_carries_the_module_keyspace(self):
		"""Every mutating workspace endpoint returns this for the client to swap in."""
		from frappe.desk.doctype.workspace.workspace import workspace_payload

		payload = workspace_payload()
		for key in ("workspace_pages", "app_data", "module_sidebars", "entity_module"):
			self.assertIn(key, payload)
		self.assertNotIn("sidebar_items", payload)


class TestCodeOnlyModuleHeirs(IntegrationTestCase):
	"""The other half of the `code_only_modules` declaration: not only that a module ships no
	navigation, but where the navigation went.

	The client resolves an entity against the heirs (see `sidebar_from_module`); the server only
	states them and ships them. What is pinned here is that the hook's change of shape did not take
	the dock gate with it, and that the declaration has not gone stale.

	"""

	def setUp(self):
		frappe.set_user("Administrator")

	def test_the_dock_gate_still_reads_the_same_names(self):
		"""`get_code_only_modules` is `set()` over the hook, and `set()` over a dict yields its keys,
		which is why the list could become a mapping with no caller change.
		"""
		from frappe.utils.modules import get_code_only_module_heirs, get_code_only_modules

		heirs = get_code_only_module_heirs()
		self.assertEqual(get_code_only_modules(), set(heirs))

		navigable = get_navigable_modules()
		for module in heirs:
			self.assertNotIn(module, navigable, f"{module} declares no navigation but is in the dock")

	def test_every_heir_is_a_module_that_can_actually_be_landed_in(self):
		"""The ongoing cost of declaring where navigation went instead of inferring it: a mapping can
		go stale. It already had: `Communication` is a `Core` doctype that only `Email` links, and
		`Email` was missing from the day the declaration was written. This catches the other
		direction, an heir that was renamed, deleted, or is itself code-only. A name nobody inherited
		still needs a sweep.

		It is checked against `module_app`, every installed app's `modules.txt`, rather than against
		the `Module Def` table, so both sides are repo facts. A site that has not migrated since the
		modules were added is missing the rows, and this would fail for staleness rather than for rot.

		"""
		from frappe.utils.modules import get_code_only_module_heirs, get_code_only_modules

		code_only = get_code_only_modules()
		declared = frappe.local.module_app
		for module, heirs in get_code_only_module_heirs().items():
			self.assertTrue(heirs, f"{module} is code-only and names no heir, so its entities dead-end")
			for heir in heirs:
				self.assertIn(frappe.scrub(heir), declared, f"{module} -> {heir}, which no app ships")
				self.assertNotIn(heir, code_only, f"{module} -> {heir}, which ships no navigation either")

	def test_the_heirs_are_ordered_and_stay_ordered(self):
		"""`append_hook` turns each value into a list and extends in app order, so the declaration
		order is the read order, which the resolver depends on twice: for the tie-break and for the
		default home.
		"""
		from frappe.utils.modules import get_code_only_module_heirs

		heirs = get_code_only_module_heirs()
		self.assertIsInstance(heirs.get("Core"), list)
		self.assertEqual(heirs["Core"][0], "System", "the first heir is Core's default home")

	def test_the_mapping_reaches_the_desk_raw(self):
		"""One boot key beside `module_app`, unfiltered. The client tests each heir against
		`module_sidebars`, which is already the per-user payload, so filtering here would put the same
		rule in two places.
		"""
		from frappe.boot import get_bootinfo
		from frappe.utils.modules import get_code_only_module_heirs

		boot = get_bootinfo()
		self.assertEqual(boot.get("code_only_module_heirs"), get_code_only_module_heirs())


class TestPrivateWorkspacesAreDerived(IntegrationTestCase):
	"""D3: a private workspace's sidebar link is not stored anywhere.

	The workspace already carries its module, owner, title and icon, so the sidebar appends the
	user's private workspaces in that module on read. That removes the layer pollution: the shared
	document used to accumulate a row per private page, so an admin curating the site's sidebar found
	other users' pages in the document they were editing, and each of those rows was a second copy of
	four columns that could change underneath it.

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
		"""The write path branches on public, and the private branch writes nothing, so there is no
		customization holding the link and no item row naming it in any document.
		"""
		from frappe.desk.doctype.workspace.workspace import new_page

		with system_write():
			frappe.get_doc(
				{
					"doctype": "Sidebar",
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
			frappe.db.exists("Custom Sidebar", {"module": self.module}),
			"a private page must not open a customization on the module",
		)
		self.assertFalse(
			frappe.db.exists("Sidebar Item", {"link_type": "Workspace", "link_to": name}),
			"no item row anywhere may name a private page",
		)
		# and the derived one is there all the same
		self.assertIn(name, [item["link_to"] for item in self.items_for(self.OWNER)])

	def test_nobody_else_sees_it(self):
		"""It is owner-scoped by the query that derives it, so it is not a filter that could be
		forgotten: another user's sidebar is never handed the row.
		"""
		make_report(self.module, "Test Derived Private Neighbour Report")
		workspace = self.make_private_workspace("Test Somebody Elses Page", self.OWNER)

		links = [item["link_to"] for item in self.items_for(self.STRANGER)]

		self.assertIn("Test Derived Private Neighbour Report", links, "sanity: the module resolves")
		self.assertNotIn(workspace.name, links)

	def test_a_module_whose_only_page_is_private_is_still_navigable(self):
		"""The derivation runs before the rule that drops a module holding nothing navigable, so a page
		someone created in an otherwise empty module does not land on no dock.
		"""
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
		"""What the desk needs in order not to offer it as something to arrange: no document holds it,
		so no arrangement can name it.
		"""
		self.make_private_workspace("Test Marked Private Page", self.OWNER)

		item = next(i for i in self.items_for(self.OWNER) if i["link_type"] == "Workspace")

		self.assertEqual(item["derived"], 1)

	def test_a_row_stored_before_the_derivation_is_not_rendered_twice(self):
		"""A site that stored these links keeps rendering one link, in the position its layer put it.
		The derived one is the duplicate, and it is the one dropped.
		"""
		from frappe.desk.doctype.custom_sidebar.custom_sidebar import add_site_sidebar_item

		workspace = self.make_private_workspace("Test Legacy Stored Page", self.OWNER)
		# stored while it was still public, which is the only way such a row was ever written
		frappe.db.set_value("Workspace", workspace.name, {"public": 1, "for_user": ""})
		add_site_sidebar_item(
			self.module,
			{"type": "Link", "label": "Stored", "link_type": "Workspace", "link_to": workspace.name},
		)
		layer = frappe.db.get_value("Custom Sidebar", {"module": self.module})
		self.addCleanup(frappe.delete_doc, "Custom Sidebar", layer, force=True, ignore_permissions=True)
		frappe.db.set_value("Workspace", workspace.name, {"public": 0, "for_user": self.OWNER})

		links = [item["link_to"] for item in self.items_for(self.OWNER)]

		self.assertEqual(links.count(workspace.name), 1)


class TestAClaimOnAnAbsentEntityIsInert(IntegrationTestCase):
	"""Nothing validates `is_default_module`, so its inertness has to be structural.

	An app claims an entity by flagging the row that links it, and it may ship that claim knowing the
	defining app is optional, such as HRMS claiming `Employee` on a site without erpnext. No
	validator guards it, on purpose: `ignore_links` at import and `is_item_allowed` at boot already
	make such a claim a non-event at both ends, so these tests do the work instead of a check that
	would have to be kept correct.

	"""

	MISSING = "Test Entity From An Absent App"
	MODULE = "Test Absent Claim Module"
	USER = "absent-app-claim@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("DocType", self.MISSING), "sanity: the entity is absent")

	def tearDown(self):
		frappe.set_user("Administrator")

	def claim_row(self):
		"""The row an app ships: a link to an entity it does not define, flagged as owned."""
		return {
			"type": "Link",
			"link_type": "DocType",
			"link_to": self.MISSING,
			"label": "Absent",
			"is_default_module": 1,
		}

	def test_a_claim_on_an_absent_entity_imports(self):
		"""`bench update` must not fail on a site that lacks the optional app. `import_doc` sets
		`ignore_links`, so the DynamicLink is never resolved at import time.
		"""
		from frappe.modules.import_file import import_doc

		with sidebarless_module(self.MODULE) as module, no_developer_mode():
			doc = import_doc(
				{
					"doctype": "Sidebar",
					"module": module,
					"title": "Absent",
					"standard": 1,
					"items": [self.claim_row()],
				}
			)

		self.assertEqual(doc.items[0].link_to, self.MISSING)
		self.assertTrue(doc.items[0].is_default_module, "the flag survives the import")

	def test_the_claim_never_reaches_the_boot_payload(self):
		"""Having imported, it is dropped by the permission filter before ownership is built, so the
		claim is invisible rather than dangling. That is the behaviour when HRMS is not installed.

		It is read as a real user: `is_item_allowed` short-circuits to True for Administrator, so
		Administrator is the one session that cannot observe this.

		"""
		make_user(self.USER, ["System Manager"])
		frappe.set_user(self.USER)

		# a readable row alongside it, so an empty result is attributable to the absent entity
		# rather than to a user who can see nothing at all
		present = frappe._dict(
			type="Link", link_type="DocType", link_to="ToDo", label="ToDo", is_default_module=1
		)
		filtered = filter_sidebar_items(
			[frappe._dict(self.claim_row()), present], frappe.new_doc("Workspace")
		)

		self.assertEqual(
			[item["link_to"] for item in filtered],
			["ToDo"],
			"the absent entity's row is dropped and the readable one is not",
		)
		self.assertEqual(build_entity_module_map({self.MODULE: {"items": filtered}}), {"ToDo": self.MODULE})


class TestTwoAppsClaimTheSameEntity(IntegrationTestCase):
	"""The claim comparator: highest install index, then module name ascending.

	The rule replaces a last-write-wins over a dict ordered by module name, so every case below is
	chosen where the two orders disagree, or it would pass against the defect.

	The cases are staged as payloads rather than fixtures, because that is the function's interface,
	which takes the whole `module_sidebars` payload, and because a test site cannot install a second
	app: the install order the rule is about only exists under `patch`. The consequence that is about
	the payload rather than the comparator, ownership being per-user, is staged for real below.

	"""

	ENTITY = "Test Contested Entity"

	def resolve(self, claims, installed=("frappe", "erpnext", "hrms")):
		"""`claims` is `(module, app)` pairs, each a sidebar claiming the same entity."""
		payload = {
			module: {
				"module": module,
				"app": app,
				"items": [
					{
						"type": "Link",
						"link_type": "DocType",
						"link_to": self.ENTITY,
						"label": "Contested",
						"is_default_module": 1,
					}
				],
			}
			for module, app in claims
		}
		with patch("frappe.get_installed_apps", return_value=list(installed)):
			return build_entity_module_map(payload).get(self.ENTITY)

	def test_the_last_installed_app_wins(self):
		"""The `Employee` case: `hrms` requires `erpnext`, so it is installed after it and its claim
		wins. Alphabetically `Setup` sorts last, so the dict-order last-write-wins this replaces gave
		the entity to `Setup`, which is the bug as it shipped.
		"""
		self.assertEqual(self.resolve([("Setup", "erpnext"), ("HR Setup", "hrms")]), "HR Setup")

	def test_the_winner_does_not_depend_on_payload_order(self):
		"""Determinism is the fix, so the same two claims in the other order give the same answer. The
		payload's own order is `name asc`, and relying on it for precedence was the accident being
		removed.
		"""
		self.assertEqual(self.resolve([("HR Setup", "hrms"), ("Setup", "erpnext")]), "HR Setup")

	def test_two_claims_from_one_app_are_separated_by_module_name(self):
		"""There is no install order to appeal to, so the tie-break decides: lowest module name. Again
		the orders disagree, since last-write-wins would have said `Payroll`.
		"""
		self.assertEqual(self.resolve([("HR Setup", "hrms"), ("Payroll", "hrms")]), "HR Setup")

	def test_an_app_that_is_not_installed_loses_to_one_that_is(self):
		"""A module placed by `get_module_placement` can name an app this site never installed. It
		ranks below every installed app rather than raising, so `erpnext` wins here even though
		`Ghost Module` sorts first.
		"""
		self.assertEqual(self.resolve([("Setup", "erpnext"), ("Ghost Module", "ghost_app")]), "Setup")

	def test_an_unknown_app_still_resolves_rather_than_raising(self):
		"""Uncontested, it keeps the entity: an index nobody can compute is a reason to sort last, not
		a reason to lose. Boot must not raise on any of it.
		"""
		self.assertEqual(self.resolve([("Ghost Module", "ghost_app")]), "Ghost Module")
		self.assertEqual(self.resolve([("Appless Module", None)]), "Appless Module")


class TestOwnershipIsPerUser(IntegrationTestCase):
	"""The comparator runs over an already permission-filtered payload, so the winner is the
	last-installed app among the claims this user can see.

	Two users can therefore resolve one entity to different modules and both be right. It is pinned
	because it looks like a bug from the outside, and the fix someone would reach for, resolving
	ownership before filtering, would name modules the user cannot open.

	"""

	ENTITY = "ToDo"
	USER = "per-user-ownership@example.com"

	def setUp(self):
		frappe.set_user("Administrator")
		# same app, so the module-name tie-break decides between them, and `Alpha` wins
		self.winner = self.enterContext(sidebarless_module("Test Claim Alpha Module"))
		self.runner_up = self.enterContext(sidebarless_module("Test Claim Zeta Module"))
		for module in (self.winner, self.runner_up):
			sidebar = frappe.get_doc({"doctype": "Sidebar", "module": module, "title": module})
			sidebar.append(
				"items",
				{
					"type": "Link",
					"link_type": "DocType",
					"link_to": self.ENTITY,
					"label": "ToDo",
					"is_default_module": 1,
				},
			)
			with system_write():
				sidebar.insert(ignore_permissions=True)

		make_user(self.USER, ["System Manager"])
		self.addCleanup(frappe.delete_doc, "User", self.USER, force=True, ignore_missing=True)
		self.addCleanup(frappe.set_user, "Administrator")

	def owner_for(self, user):
		frappe.set_user(user)
		# `get_module_sidebars` is request-cached and `set_user` does not clear it, so the second
		# reader would otherwise be answered with the first one's payload
		if getattr(frappe.local, "request_cache", None):
			frappe.local.request_cache.clear()
		return build_entity_module_map(get_module_sidebars()).get(self.ENTITY)

	def test_the_lower_module_name_wins_for_a_reader_who_sees_both(self):
		self.assertEqual(self.owner_for("Administrator"), self.winner)

	def test_a_reader_who_cannot_see_the_winner_gets_the_next_claim_down(self):
		user = frappe.get_doc("User", self.USER)
		user.append("block_modules", {"module": self.winner})
		user.save(ignore_permissions=True)
		frappe.clear_cache(user=self.USER)

		self.assertEqual(self.owner_for(self.USER), self.runner_up)
		self.assertEqual(
			self.owner_for("Administrator"), self.winner, "same fixtures, and the answer differs by reader"
		)


class TestAModuleInNoAppHasNoAppContext(IntegrationTestCase):
	"""D15: app context answers exactly one question, what supplies the rail's items, and for a
	module no app claims it answers nothing. That answer is complete rather than degraded, and the
	boot payload states it rather than leaving the desk to guess:

	    placed    logo = app icon      items = the app's other modules
	    unplaced  logo = module icon   items = (empty)

	"""

	def setUp(self):
		frappe.set_user("Administrator")

	def sidebar(self, shell: str):
		return resolve_sidebar(shell, frappe.session.user)

	def app_entry(self, app_name: str):
		return next(app for app in get_bootinfo()["app_data"] if app["app_name"] == app_name)

	def dock_modules(self, app: dict) -> list[str]:
		"""The shells an app's dock list names, which are its modules. A `Sidebar` row is the shell
		itself; a row of any other kind opens a page and derives its shell, so it is not one of
		these.
		"""
		return [row["link_to"] for row in app["dock"] if row.get("link_type") == "Sidebar"]

	def test_a_placed_module_names_the_app_that_supplies_the_rails_items(self):
		"""Placed: the payload has to say which app supplies the rail, and that app has to be a real
		one. What is on that rail is the app's own `Dock` record, so a module the site has just added
		is navigable without being on it. See `TestAnAppWithNoDock`.
		"""
		with custom_module("Test Placed Rail Module", app="frappe") as module:
			make_sidebar(module)

			self.assertEqual(self.sidebar(module).app, "frappe")
			self.assertTrue(self.dock_modules(self.app_entry("frappe")))

	def test_a_placement_the_document_never_declares_still_gives_a_rail(self):
		"""`app` used to come straight off the `Sidebar` document, an authored field a stub can leave
		blank, so a module placed in an app by a document that never filled it in got no rail at all.
		Placement answers when the document does not.
		"""
		with custom_module("Test Silent App Field Module", app="frappe") as module:
			sidebar = make_sidebar(module)
			self.assertFalse(sidebar.app, "sanity: the document declares no app")

			self.assertEqual(self.sidebar(module).app, "frappe")

	def test_an_authored_app_declaration_wins_over_placement(self):
		"""The fallback is a fallback. A companion app ships its module's sidebar mounted into the host
		app's rail, and that declaration is what the field is for.
		"""
		with custom_module("Test Declared App Module", app="frappe") as module:
			make_sidebar(module, app="some_other_app")

			self.assertEqual(self.sidebar(module).app, "some_other_app")

	def test_an_unplaced_module_names_no_app(self):
		with custom_module("Test Appless Rail Module") as module:
			make_sidebar(module, title="Field Service", header_icon="tool")

			self.assertFalse(self.sidebar("Field Service").app)

	def test_nothing_supplies_an_unplaced_modules_rail_items(self):
		"""The empty items region is a consequence of the data rather than a special case in the
		client: no installed app claims the module, so the set the rail renders is empty whichever app
		it is asked about.
		"""
		with custom_module("Test Unclaimed Rail Module") as module:
			make_sidebar(module)

			for app in get_bootinfo()["app_data"]:
				self.assertNotIn(module, self.dock_modules(app))

	def test_the_icon_needs_no_new_boot_payload(self):
		"""The rail resolves an unplaced module's icon from the sidebar it already reads: an authored
		`header_icon`, otherwise a letter icon built from the label. Both are on the entry, so nothing
		had to be added to boot to give the slot an icon.
		"""
		with custom_module("Test Iconed Rail Module") as module:
			make_sidebar(module, title="Field Service", header_icon="tool")

			sidebar = self.sidebar("Field Service")

			self.assertEqual(sidebar.header_icon, "tool")
			self.assertEqual(sidebar.label, "Field Service")

	def test_a_module_with_no_authored_icon_still_carries_the_label_one_is_built_from(self):
		"""The letter-icon fallback has nothing to work with without a label, so the computed base has
		to name the module even when nobody titled it.
		"""
		with custom_module("Test Iconless Rail Module") as module:
			make_sidebar(module)

			sidebar = self.sidebar(module)

			self.assertFalse(sidebar.header_icon)
			self.assertEqual(sidebar.label, module)
