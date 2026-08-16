# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.app_state import get_disabled_modules
from frappe.boot import get_app_modules
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.doctype.sidebar.sidebar import clear_computed_base_cache, resolve_sidebar
from frappe.desk.doctype.sidebar.test_sidebar import make_report, make_sidebar
from frappe.installer import (
	get_app_owned_modules,
	reclaim_module_name_for_its_app,
	release_custom_module_placements,
	rename_conflicting_custom_module,
)
from frappe.tests import IntegrationTestCase
from frappe.utils.modules import get_module_placement


@contextmanager
def module_declared_by(module: str, app: str):
	"""`app`'s modules.txt claiming `module`, in memory only.

	Registering it in `frappe.local.module_app` is what an app declaring a module amounts to
	at runtime, and writing the file instead would leave the working tree dirty.
	"""
	key = frappe.scrub(module)
	frappe.local.module_app[key] = app
	try:
		yield
	finally:
		frappe.local.module_app.pop(key, None)


def doctype_in(module: str, name: str):
	"""A DocType owned by `module`.

	Single, so that syncing it needs no table of its own: creating a table commits, and a
	committed fixture outlives the test's rollback -- stranding both the doctype and the module
	it names for the next run to collide with. Nothing here reads a row; what is under test is
	which module owns the doctype.
	"""
	return new_doctype(name, module=module, issingle=1).insert()


@contextmanager
def custom_module(name: str, app: str | None = None):
	"""A site-owned module, placed in `app`'s dock or nowhere at all.

	Nothing is written to disk on the way in or out: `on_update` and `on_trash` both skip
	their modules.txt and folder work for a custom module, which is the whole point of one.

	A test that renames the module cleans up the name it renamed to; this only knows the one
	it created.
	"""
	frappe.get_doc({"doctype": "Module Def", "module_name": name, "custom": 1, "app_name": app}).insert()
	clear_computed_base_cache(name)

	try:
		yield name
	finally:
		frappe.delete_doc("Module Def", name, force=True, ignore_missing=True)
		# redis outlives the DB rollback, so a base computed from fixtures that are about to
		# vanish would leak into whatever runs next
		clear_computed_base_cache(name)


class TestCustomModuleIsSiteOwned(IntegrationTestCase):
	"""`custom` governs lifecycle, `app_name` governs placement -- and nothing else."""

	def test_a_custom_module_needs_no_placement(self):
		"""`app_name` is a hint about which dock lists the module, so a module that has not
		chosen one is a legitimate module rather than an incomplete record."""
		with custom_module("Test Unplaced Module") as module:
			self.assertFalse(frappe.db.get_value("Module Def", module, "app_name"))

	def test_an_unplaced_module_resolves_to_no_app_rather_than_throwing(self):
		"""A custom module is in no app's modules.txt and may name no app at all. Asking which
		app it belongs to is then a question with the answer `None`, not an error -- the throw
		is what used to leave a freshly created module out of the desk entirely."""
		with custom_module("Test Unresolvable Module") as module:
			self.assertIsNone(get_module_placement(module))

			make_report(module, "Test Unresolvable Module Report")
			sidebar = resolve_sidebar(module, frappe.session.user)

			self.assertIsNotNone(sidebar, "an unplaced module must still resolve to a sidebar")
			self.assertIsNone(sidebar.app)

	def test_a_placed_custom_module_is_listed_in_the_dock_of_the_app_it_names(self):
		"""Creating it is the whole of the work: the module appears in the desk with no sidebar
		to author, no migrate and no restart."""
		with custom_module("Test Placed Module", app="frappe") as module:
			make_report(module, "Test Placed Module Report")

			self.assertIn(module, get_app_modules("frappe"))

			sidebar = resolve_sidebar(module, frappe.session.user)
			self.assertIsNotNone(sidebar)
			self.assertEqual(sidebar.app, "frappe")
			self.assertIn("Test Placed Module Report", [item["link_to"] for item in sidebar.items])

	def test_a_custom_module_can_own_doctypes(self):
		"""Owning doctypes is *why* custom modules exist -- `DocType.module` has always been
		mandatory, so a module that could not hold one would be an empty gesture."""
		with custom_module("Test Owning Module") as module:
			doctype = doctype_in(module, "Test Custom Module DocType")

			self.assertEqual(frappe.db.get_value("DocType", doctype.name, "module"), module)

	def test_creating_a_module_stays_administrator_and_system_manager_only(self):
		"""Minting a top-level navigation unit is an administrator's act. Everyone else reads."""
		creators = {perm.role for perm in frappe.get_meta("Module Def").permissions if perm.create}

		self.assertEqual(creators, {"Administrator", "System Manager"})


class TestUninstallLeavesCustomModulesAlone(IntegrationTestCase):
	"""Uninstalling an app takes the app's own modules. The site's are the site's."""

	def test_uninstall_takes_only_the_apps_own_modules(self):
		with custom_module("Test Surviving Module", app="frappe") as module:
			owned = get_app_owned_modules("frappe")

			self.assertNotIn(module, owned)
			self.assertIn("Core", owned)

	def test_uninstall_releases_a_custom_modules_placement(self):
		"""The placement pointed at an app that is no longer here; the module is not. Clearing
		it is what keeps the module reachable -- it falls back to standing on its own."""
		with custom_module("Test Released Module", app="frappe") as module:
			release_custom_module_placements("frappe")

			self.assertIsNone(frappe.db.get_value("Module Def", module, "app_name"))

	def test_releasing_placements_leaves_the_apps_own_modules_alone(self):
		release_custom_module_placements("frappe")

		self.assertEqual(frappe.db.get_value("Module Def", "Core", "app_name"), "frappe")


class TestDisablingTheHostAppLeavesTheModule(IntegrationTestCase):
	"""Turning an app off is the same split as uninstalling it: the app's modules go, the
	site's stay. A custom module can never become unreachable."""

	def disabled_modules_with(self, app: str) -> set[str]:
		# the answer is request-cached, and something earlier in the process has already asked
		if getattr(frappe.local, "request_cache", None):
			frappe.local.request_cache.clear()

		# filtering is off while a maintenance flag is set, and the test runner sets one
		with (
			patch("frappe.get_disabled_apps", return_value=[app]),
			patch("frappe.app_state.is_disabled_app_filtering_active", return_value=True),
		):
			return get_disabled_modules()

	def test_a_disabled_app_hides_its_own_modules_only(self):
		with custom_module("Test Hosted Module", app="frappe") as module:
			disabled = self.disabled_modules_with("frappe")

			self.assertIn("Core", disabled, "sanity: the app's own modules go")
			self.assertNotIn(module, disabled)


class TestAnAppWinsTheName(IntegrationTestCase):
	"""An app install is never blocked by a site's naming choice."""

	def test_an_app_module_takes_its_name_from_a_custom_module(self):
		with custom_module("Test Contested Module") as module:
			doctype = doctype_in(module, "Test Contested DocType")

			renamed = rename_conflicting_custom_module(module, "frappe")
			self.addCleanup(frappe.delete_doc, "Module Def", renamed, force=True, ignore_missing=True)

			self.assertEqual(renamed, f"{module} (Custom)")
			self.assertFalse(frappe.db.exists("Module Def", module), "the name is free for the app")
			self.assertTrue(frappe.db.get_value("Module Def", renamed, "custom"))
			self.assertEqual(
				frappe.db.get_value("DocType", doctype.name, "module"),
				renamed,
				"the module's doctypes follow it",
			)

	def test_a_taken_fallback_name_does_not_collide(self):
		with custom_module("Test Twice Contested Module") as first:
			with custom_module(f"{first} (Custom)"):
				renamed = rename_conflicting_custom_module(first, "frappe")
				self.addCleanup(frappe.delete_doc, "Module Def", renamed, force=True, ignore_missing=True)

				self.assertEqual(renamed, f"{first} (Custom 2)")

	def test_the_modules_sidebar_moves_with_it(self):
		"""A `Sidebar` is named after its module, so the link cascade is not enough: left
		on the old name, it is what the app's own sidebar collides with on import."""
		with custom_module("Test Sidebarred Module") as module:
			make_sidebar(module)

			renamed = rename_conflicting_custom_module(module, "frappe")
			self.addCleanup(frappe.delete_doc, "Module Def", renamed, force=True, ignore_missing=True)

			self.assertFalse(frappe.db.exists("Sidebar", module), "the name is free for the app")
			self.assertEqual(frappe.db.get_value("Sidebar", renamed, "module"), renamed)

	def test_an_apps_own_module_is_left_where_it_is(self):
		"""Only a *custom* module moves aside. A module the app already owns is the app
		re-declaring what it shipped, and renaming it would rename the app's own content."""
		self.assertIsNone(rename_conflicting_custom_module("Core", "frappe"))
		self.assertTrue(frappe.db.exists("Module Def", "Core"))

	def test_a_free_name_is_left_alone(self):
		self.assertIsNone(rename_conflicting_custom_module("Test Module Nobody Holds", "frappe"))

	def test_a_module_an_app_declares_takes_its_name_back(self):
		"""The sideways route: a doctype imported by `bench migrate` brings its module with it,
		and never names the app. `modules.txt` is what says the name is the app's."""
		with custom_module("Test Declared Module") as module:
			with module_declared_by(module, "frappe"):
				renamed = reclaim_module_name_for_its_app(module)
			self.addCleanup(frappe.delete_doc, "Module Def", renamed, force=True, ignore_missing=True)

			self.assertEqual(renamed, f"{module} (Custom)")

	def test_a_module_no_app_declares_is_the_sites_own(self):
		with custom_module("Test Undeclared Module") as module:
			self.assertIsNone(reclaim_module_name_for_its_app(module))
			self.assertTrue(frappe.db.exists("Module Def", module))
