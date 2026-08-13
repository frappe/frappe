# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""What a v15 customer gets from `bench update`.

They have no `Module Sidebar`, no `Workspace.module`, no `Desktop Icon` -- the whole
navigation model arrives in one migrate. These tests seed that shape and walk it through the
same patches, in the same order, that `patches.txt` runs them in, then read the result off the
surfaces the desk actually boots from.
"""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.desktop import get_user_dock_modules
from frappe.desk.doctype.desktop_settings.desktop_settings import APPS, DESKTOP_ICONS, get_desktop_page
from frappe.desk.doctype.module_sidebar.module_sidebar import clear_computed_base_cache
from frappe.desk.doctype.module_sidebar.test_module_sidebar import no_developer_mode
from frappe.modules.patch_handler import PatchType, get_patches_from_app
from frappe.tests import IntegrationTestCase

BACKFILL = "frappe.patches.v16_0.backfill_workspace_module"
BUILD_SIDEBARS = "frappe.patches.v16_0.build_module_sidebars"
MIGRATE_DOCK = "frappe.patches.v16_0.migrate_user_workspaces_to_dock_modules"
PIN_DESKTOP = "frappe.patches.v16_0.keep_existing_sites_on_desktop_icons"


def post_model_sync_patches() -> list[str]:
	"""`patches.txt`'s post-sync section as module paths, with re-run markers split off.

	A line carries its re-run marker as a trailing comment (`... #2026-08-12 re-run-patch`),
	which is part of the string `Patch Log` keys on but not part of the module to import --
	the same `split(maxsplit=1)` the patch handler itself does.
	"""
	return [p.split(maxsplit=1)[0] for p in get_patches_from_app("frappe", PatchType.post_model_sync)]


def upgrade_sequence() -> list[str]:
	"""The navigation patches, in the order the site will actually run them.

	Read off `patches.txt` rather than listed here on purpose: a line drifting back below its
	consumers then fails what the customer loses -- their sidebars, their dock -- and not only
	the order assertion in `TestPatchOrder`.
	"""
	wanted = {BACKFILL, BUILD_SIDEBARS, MIGRATE_DOCK}
	return [p for p in post_model_sync_patches() if p in wanted]


def run_patches(patches) -> list[str]:
	"""Run them in order and hand back everything they printed."""
	lines = []
	with patch("click.secho", side_effect=lambda message="", **kwargs: lines.append(message)):
		for patch_module in patches:
			frappe.get_attr(patch_module + ".execute")()
	return lines


class TestPatchOrder(IntegrationTestCase):
	"""The reorder itself, stated where a line drifting back would be noticed."""

	def test_the_backfill_runs_before_its_consumers(self):
		# Both consumers read `Workspace.module` and can only skip a workspace that has none,
		# which on a v15 site is all of them -- behind the backfill they are silent no-ops.
		post = post_model_sync_patches()
		self.assertLess(post.index(BACKFILL), post.index(BUILD_SIDEBARS))
		self.assertLess(post.index(BACKFILL), post.index(MIGRATE_DOCK))

	def test_nothing_fills_a_column_ahead_of_the_merge(self):
		"""The two patches that used to write `Workspace.sidebar_items` for the merge to read
		back are gone with the column. Their inputs are read where they actually live now --
		the archive, and a workspace's own shortcuts."""
		post = post_model_sync_patches()
		for retired in (
			"frappe.patches.v16_0.migrate_workspace_sidebar_to_workspace",
			"frappe.patches.v16_0.populate_workspace_sidebar_from_shortcuts",
		):
			self.assertNotIn(retired, post)

	def test_both_consumers_are_marked_to_re_run(self):
		"""The reorder only reaches a site that has already run them if they run again.

		Both are guarded -- the merge skips a module that already has a sidebar, the dock
		migration skips a user who already has rows -- so a second pass repairs the sites
		that skipped everything and leaves the rest, including anyone who has since curated
		their own dock, exactly as they are.
		"""
		lines = get_patches_from_app("frappe", PatchType.post_model_sync)
		for consumer in (BUILD_SIDEBARS, MIGRATE_DOCK):
			line = next(p for p in lines if p.split(maxsplit=1)[0] == consumer)
			self.assertIn("re-run-patch", line, f"{consumer} would not reach an already-migrated site")


class TestV15Upgrade(IntegrationTestCase):
	"""One seeded v15 site, upgraded once -- as a migrate would."""

	MODULE = "Test V15 Module"
	CUSTOM_MODULE = "Test V15 Custom Module"
	REPORT = "V15 Module Report"
	PUBLIC = "V15 Public Page"
	OTHER = "V15 Other Page"
	PRIVATE = "V15 Private Page"
	USER = "test-v15-upgrade@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		with no_developer_mode():
			frappe.get_doc(
				{"doctype": "Module Def", "module_name": cls.MODULE, "app_name": "frappe"}
			).insert()
		clear_computed_base_cache(cls.MODULE)

		# Something in the module for a sidebar item to point at -- which is also what the
		# backfill reads the module *off*, since a v15 workspace doesn't declare one.
		frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": cls.REPORT,
				"ref_doctype": "ToDo",
				"report_type": "Report Builder",
				"module": cls.MODULE,
				"is_standard": "No",
			}
		).insert()

		frappe.get_doc(
			{
				"doctype": "User",
				"email": cls.USER,
				"first_name": "V15",
				"send_welcome_email": 0,
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_if_duplicate=True)

		cls.seed_workspace(cls.PUBLIC, public=1)
		cls.seed_workspace(cls.OTHER, public=1)

		# A private page contributes no sidebar of its own: its link is derived on read from the
		# workspace itself. What it does carry is `links`, which is the rung of the backfill's
		# ladder these land on.
		cls.seed_workspace(cls.PRIVATE, public=0, for_user=cls.USER, shortcuts=False)

		# Things this upgrade must leave alone, seeded before it runs.
		frappe.db.set_value("Workspace", cls.PUBLIC, "standard", 1, update_modified=False)
		cls.customization = frappe.get_doc(
			{"doctype": "Custom Workspace", "workspace": cls.PUBLIC, "icon": "star"}
		).insert()
		with no_developer_mode():
			cls.custom_module = frappe.get_doc(
				{"doctype": "Module Def", "module_name": cls.CUSTOM_MODULE, "custom": 1}
			).insert()

		# v15's per-user dock curation: workspace names, in the order the user left them.
		for idx, workspace in enumerate((cls.PUBLIC, cls.OTHER, "V15 Deleted Page"), start=1):
			frappe.get_doc(
				{
					"doctype": "User Workspaces",
					"parenttype": "User",
					"parentfield": "workspaces",
					"parent": cls.USER,
					"workspace": workspace,
					"idx": idx,
				}
			).db_insert()

		cls.output = run_patches(upgrade_sequence())

	@classmethod
	def tearDownClass(cls):
		# The upgrade builds sidebars for the whole site, so the computed bases cached while
		# reading the payload are not only this module's -- and redis outlives the rollback.
		frappe.clear_cache()
		super().tearDownClass()

	@classmethod
	def seed_workspace(cls, title, public, for_user=None, shortcuts=True):
		"""A workspace as v15 left it: widgets pointing into the module, and no module.

		`module` is `reqd`, so the only way to reach the state the backfill exists for is to
		insert a valid document and blank the column underneath it -- which is exactly what a
		v15 row looks like once the field lands on it.

		Shortcuts are what a v15 workspace's navigation *was*: it had no sidebar of any kind,
		so the conversion derives one from them.
		"""
		workspace = frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": title,
				"module": cls.MODULE,
				"public": public,
				"for_user": for_user,
				"content": "[]",
				"links": [{"type": "Link", "label": title, "link_type": "Report", "link_to": cls.REPORT}],
				"shortcuts": [{"type": "Report", "label": title, "link_to": cls.REPORT}] if shortcuts else [],
			}
		).insert()
		frappe.db.set_value("Workspace", workspace.name, "module", "", update_modified=False)
		return workspace.name

	def sidebar_payload(self, user):
		from frappe.boot import get_module_sidebars

		frappe.set_user(user)
		try:
			return get_module_sidebars().get(self.MODULE)
		finally:
			frappe.set_user("Administrator")

	# -- the navigation they land with --------------------------------------------------

	def test_every_v15_workspace_reaches_a_module(self):
		for title in (self.PUBLIC, self.OTHER, self.PRIVATE):
			self.assertEqual(frappe.db.get_value("Workspace", title, "module"), self.MODULE)

	def test_the_module_gets_a_sidebar_carrying_what_the_workspaces_authored(self):
		"""Behind the backfill this layer did not exist at all: the merge saw no sources."""
		layer = frappe.get_doc("Custom Module Sidebar", {"module": self.MODULE, "user": ""})
		self.assertIn(self.REPORT, [item.link_to for item in layer.sidebar_items])

	def test_the_sidebar_reaches_the_navigation_payload(self):
		payload = self.sidebar_payload("Administrator")
		self.assertIsNotNone(payload, "the upgraded module is missing from bootinfo.module_sidebars")
		self.assertIn(self.REPORT, [item["link_to"] for item in payload["items"]])

	def test_a_private_workspace_appears_in_its_owners_sidebar(self):
		"""Derived, not stored -- and only derivable once the page has a module."""
		payload = self.sidebar_payload(self.USER)
		self.assertIsNotNone(payload)
		self.assertIn(self.PRIVATE, [item["link_to"] for item in payload["items"]])

		# and stays the owner's: nobody else's sidebar carries it
		payload = self.sidebar_payload("Administrator")
		self.assertNotIn(self.PRIVATE, [item["link_to"] for item in payload["items"]])

	# -- the dock they curated ----------------------------------------------------------

	def test_per_user_dock_curation_survives_the_upgrade(self):
		"""The skip this ticket removes: behind the backfill every row here mapped to nothing."""
		rows = frappe.get_all(
			"Dock Module",
			filters={"parenttype": "User", "parent": self.USER},
			fields=["module"],
			order_by="idx asc",
		)
		self.assertEqual([row.module for row in rows], [self.MODULE])

		frappe.set_user(self.USER)
		try:
			self.assertIn(self.MODULE, [row["module"] for row in get_user_dock_modules()])
		finally:
			frappe.set_user("Administrator")

	def test_the_migration_says_how_much_curation_moved(self):
		self.assertIn("Migrated 1 dock module(s) for 1 user(s).", self.output)

	def test_the_migration_names_what_it_deduplicated(self):
		"""Two curated workspaces sharing a module is one dock entry -- said, not swallowed."""
		folded = [line for line in self.output if "deduplicated" in line and self.OTHER in line]
		self.assertTrue(folded, f"deduplication not named in output: {self.output}")

	def test_the_migration_names_what_it_could_not_map(self):
		dropped = [line for line in self.output if "dropped" in line and "V15 Deleted Page" in line]
		self.assertTrue(dropped, f"unmapped curation not named in output: {self.output}")

	def test_a_second_run_reports_nothing_it_did_not_do(self):
		"""A user already holding dock rows is left out of the run, not filtered out of the
		report -- otherwise a re-run names their drops again and describes loss twice."""
		again = run_patches([MIGRATE_DOCK])
		self.assertEqual([line for line in again if self.USER in line], [])

	# -- what the upgrade must not touch ------------------------------------------------

	def test_a_workspace_customization_carries_over_untouched(self):
		self.assertEqual(
			frappe.db.get_value("Custom Workspace", self.customization.name, ["workspace", "icon"]),
			(self.PUBLIC, "star"),
		)

	def test_a_custom_module_is_left_alone(self):
		"""It is the site's, not an app's -- nothing in the upgrade gets to place or claim it."""
		module = frappe.get_doc("Module Def", self.CUSTOM_MODULE)
		self.assertEqual(module.custom, 1)
		self.assertFalse(module.app_name)


@contextmanager
def desktop_icons(rows: int):
	"""The site's grid, emptied or stocked, and put back afterwards.

	A savepoint rather than the class rollback, because these rows are the site's own: on a
	development site the grid is real, and a test that leaves it emptied has broken something
	the person running it uses.
	"""
	frappe.db.savepoint("desktop_icons")
	try:
		frappe.db.delete("Desktop Icon")
		for i in range(rows):
			frappe.get_doc(
				{
					"doctype": "Desktop Icon",
					"label": f"V16 Grid Icon {i}",
					"icon_type": "App",
					"link_type": "External",
					"link": "/app",
				}
			).insert()
		yield
	finally:
		frappe.db.rollback(save_point="desktop_icons")
		frappe.clear_cache()


class TestDesktopOnUpgrade(IntegrationTestCase):
	"""Which desktop an upgrading site lands on, and what decides it."""

	def setUp(self):
		frappe.set_user("Administrator")
		self.original = frappe.db.get_single_value("Desktop Settings", "desktop_page")

	def tearDown(self):
		frappe.db.set_single_value("Desktop Settings", "desktop_page", self.original)
		frappe.clear_cache()

	def test_a_site_with_no_icon_rows_lands_on_apps(self):
		"""A v15 site never saw a grid and has nothing to fill one with, so pinning it there
		hands the customer an empty screen."""
		frappe.db.set_single_value("Desktop Settings", "desktop_page", APPS)

		with desktop_icons(0):
			run_patches([PIN_DESKTOP])
			self.assertEqual(get_desktop_page(), APPS)

	def test_a_site_holding_icon_rows_is_pinned_to_the_grid(self):
		"""Nothing seeds those rows unless the site is already on that page, so holding them
		is the site's own answer to which desktop it had."""
		frappe.db.set_single_value("Desktop Settings", "desktop_page", APPS)

		with desktop_icons(1):
			run_patches([PIN_DESKTOP])
			self.assertEqual(get_desktop_page(), DESKTOP_ICONS)
