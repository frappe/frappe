# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.boot import get_bootinfo, get_module_sidebars, get_standalone_modules
from frappe.core.doctype.module_def.test_module_def import custom_module
from frappe.desk.doctype.module_sidebar.test_module_sidebar import (
	make_report,
	make_sidebar,
	system_write,
)
from frappe.installer import release_custom_module_placements
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import clear_module_permission_cache

USER = "test-standalone-modules@example.com"


class StandaloneModuleTestCase(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def entry(self, module: str):
		"""`module`'s tile, or `None` if it has none."""
		standalone = get_standalone_modules(get_module_sidebars())
		return next((m for m in standalone if m["module"] == module), None)

	def make_workspace(self, module: str, name: str, sequence_id: int = 1):
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": name,
				"label": name,
				"module": module,
				"public": 1,
				"content": "[]",
				"sequence_id": sequence_id,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Workspace", doc.name, force=True, ignore_missing=True)
		return doc


class TestAnUnplacedModuleIsTheTile(StandaloneModuleTestCase):
	"""D2 -- there is no site tile and no pseudo-app; the module is the tile."""

	def test_an_unplaced_module_stands_on_the_desktop_as_itself(self):
		"""Its own sidebar title, its own header icon -- nothing borrowed from an app it is
		not in."""
		with custom_module("Test Standalone Module") as module:
			make_sidebar(module, title="Field Service", header_icon="tool")

			entry = self.entry(module)

			self.assertIsNotNone(entry, "an unplaced custom module must have a tile")
			self.assertEqual(entry["title"], "Field Service")
			self.assertEqual(entry["header_icon"], "tool")

	def test_a_placed_module_has_no_tile_of_its_own(self):
		"""Placement is the whole difference: a module listed in an app's dock is reached
		through that app, and a second entrance would be two answers to one question."""
		with custom_module("Test Placed Tile Module", app="frappe") as module:
			make_sidebar(module)

			self.assertIsNone(self.entry(module))

	def test_the_tile_lands_on_the_modules_home_workspace(self):
		"""The same rule the desk navigates by: a module opens on its home workspace."""
		with custom_module("Test Homed Standalone Module") as module:
			workspace = self.make_workspace(module, "Test Standalone Home")
			make_sidebar(module, home_workspace=workspace.name)

			self.assertEqual(self.entry(module)["route"], "/desk/test-standalone-home")

	def test_a_module_with_no_home_lands_on_its_first_workspace(self):
		with custom_module("Test Homeless Standalone Module") as module:
			self.make_workspace(module, "Test Standalone First", sequence_id=1)
			self.make_workspace(module, "Test Standalone Second", sequence_id=2)
			make_sidebar(module)

			self.assertEqual(self.entry(module)["route"], "/desk/test-standalone-first")

	def test_a_module_with_no_workspace_leaves_the_route_to_the_client(self):
		"""The server answers the workspace half of the landing rule, because a workspace
		route is a slug and nothing else. Everything else -- a doc view, a report type,
		filters as query params -- is `generate_route`'s job on the client, and duplicating
		it here would be a second routing implementation to keep in step."""
		with custom_module("Test Routeless Standalone Module") as module:
			make_report(module, "Test Routeless Standalone Report")

			entry = self.entry(module)

			self.assertIsNotNone(entry)
			self.assertIsNone(entry["route"])


class TestTheListIsASiblingOfAppData(StandaloneModuleTestCase):
	"""`app_data` means installed apps, and the desk reads it as exactly that."""

	def test_the_installed_app_list_holds_no_modules(self):
		"""`frappe.utils.get_installed_apps()` maps `app_data` to app names, so a module put
		in there would have the client reporting a module as an installed app."""
		with custom_module("Test Not An App Module") as module:
			make_sidebar(module)

			boot = get_bootinfo()

			self.assertNotIn(module, [app["app_name"] for app in boot["app_data"]])
			self.assertIn(module, [m["module"] for m in boot["standalone_modules"]])

	def test_boot_carries_the_documented_shape(self):
		with custom_module("Test Shaped Standalone Module") as module:
			make_sidebar(module)

			for entry in get_bootinfo()["standalone_modules"]:
				self.assertEqual(set(entry), {"module", "title", "header_icon", "route"})


class TestTheFloorHolds(StandaloneModuleTestCase):
	"""A custom module can never become unreachable."""

	def test_a_module_orphaned_by_an_uninstall_gets_a_tile_with_no_manual_step(self):
		"""Uninstalling the host clears the placement (`release_custom_module_placements`);
		the module then stands on its own, without anyone going and saying so."""
		with custom_module("Test Orphaned Module", app="frappe") as module:
			make_sidebar(module)
			self.assertIsNone(self.entry(module), "sanity: placed, so no tile")

			release_custom_module_placements("frappe")

			self.assertIsNotNone(self.entry(module))

	def test_a_placement_naming_an_absent_app_is_no_placement(self):
		"""`Module Def.validate_placement` clears a stale placement on save, but a row that
		is never saved again must not be stranded by that -- the dock it names is gone."""
		with custom_module("Test Stale Placement Module") as module:
			make_sidebar(module)
			frappe.db.set_value("Module Def", module, "app_name", "no_such_app")

			self.assertIsNotNone(self.entry(module))

	def test_the_list_is_derived_not_read_off_desktop_icon_rows(self):
		"""An Apps-mode site holds no `Desktop Icon` rows at all, so sourcing the floor from
		them would give a fresh install no floor."""
		with custom_module("Test Derived Floor Module") as module:
			make_sidebar(module)

			self.assertFalse(frappe.db.exists("Desktop Icon", {"label": module}))
			self.assertIsNotNone(self.entry(module))


class TestVisibilityIsInherited(StandaloneModuleTestCase):
	"""Standing on its own buys a module no exemption from the rules every module is under."""

	def setUp(self):
		super().setUp()
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": USER,
					"first_name": "Standalone",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.delete_doc("User", USER, force=True, ignore_missing=True)
		clear_module_permission_cache()

	def test_a_module_a_user_may_not_reach_has_no_tile_for_them(self):
		with custom_module("Test Blocked Standalone Module") as module:
			make_sidebar(module)
			self.assertIsNotNone(self.entry(module), "sanity: visible to Administrator")

			user = frappe.get_doc("User", USER)
			user.append("block_modules", {"module": module})
			user.save(ignore_permissions=True)
			frappe.clear_cache(user=USER)

			frappe.set_user(USER)
			self.assertIsNone(self.entry(module))

	def test_a_sidebar_of_only_section_breaks_is_dropped(self):
		"""Same rule that drops the module from `module_sidebars`, inherited rather than
		restated -- the list is an intersection with that payload, so the two cannot drift."""
		with custom_module("Test Sectioned Standalone Module") as module:
			sidebar = make_sidebar(module)
			sidebar.set("items", [])
			sidebar.append("items", {"type": "Section Break", "label": "Only a section"})
			with system_write():
				sidebar.save(ignore_permissions=True)

			self.assertIsNone(self.entry(module))
