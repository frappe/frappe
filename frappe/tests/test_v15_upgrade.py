# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""What a v15 customer gets from `bench update`.

They have no `Sidebar`, no `Workspace.module`, no `Desktop Icon` -- the whole
navigation model arrives in one migrate. These tests seed that shape and walk it through the
same patches, in the same order, that `patches.txt` runs them in, then read the result off the
surfaces the desk actually boots from.
"""

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.doctype.desktop_settings.desktop_settings import APPS, DESKTOP_ICONS, get_desktop_page
from frappe.desk.doctype.sidebar.sidebar import clear_computed_base_cache
from frappe.desk.doctype.sidebar.test_sidebar import no_developer_mode
from frappe.modules.patch_handler import PatchType, get_patches_from_app
from frappe.patches.v16_0.backfill_workspace_module import CUSTOM_MODULE as CUSTOM_BUCKET
from frappe.patches.v16_0.backfill_workspace_module import PRIVATE_MODULE as PRIVATE_BUCKET
from frappe.tests import IntegrationTestCase

BACKFILL = "frappe.patches.v16_0.backfill_workspace_module"
PIN_DESKTOP = "frappe.patches.v16_0.keep_existing_sites_on_desktop_icons"
TRUNCATE_ICONS = 'execute:frappe.db.truncate("Desktop Icon")'


def post_model_sync_patches() -> list[str]:
	"""`patches.txt`'s post-sync section as module paths, with re-run markers split off.

	A line carries its re-run marker as a trailing comment (`... #2026-08-12 re-run-patch`),
	which is part of the string `Patch Log` keys on but not part of the module to import --
	the same `split(maxsplit=1)` the patch handler itself does.
	"""
	return [p.split(maxsplit=1)[0] for p in get_patches_from_app("frappe", PatchType.post_model_sync)]


def pre_model_sync_patches() -> list[str]:
	"""`patches.txt`'s pre-sync section, verbatim -- an `execute:` line is the whole line."""
	return get_patches_from_app("frappe", PatchType.pre_model_sync)


def upgrade_sequence() -> list[str]:
	"""The navigation patches, in the order the site will actually run them.

	Read off `patches.txt` rather than listed here on purpose: what the customer lands with is a
	function of the lines that are actually there, so a line that goes missing fails these tests
	rather than a list somebody kept in step by hand.
	"""
	wanted = {BACKFILL}
	return [p for p in post_model_sync_patches() if p in wanted]


def run_patches(patches) -> list[str]:
	"""Run them in order and hand back everything they printed."""
	lines = []
	with patch("click.secho", side_effect=lambda message="", **kwargs: lines.append(message)):
		for patch_module in patches:
			frappe.get_attr(patch_module + ".execute")()
	return lines


class TestNothingBuildsASidebar(IntegrationTestCase):
	"""Nothing derives a module's sidebar on the way in, and nothing is meant to start.

	A module's sidebar is computed from the module's contents on every read, so the upgrade's
	whole job is giving a v15 workspace a module -- there is no second pass that stores the
	result, and each of these patches was one. (`convert_sidebar_forks` is not one of them: it
	carries a v16 user's own *arrangement* across, and a v15 site has none to carry.) Named so a
	reintroduction has to argue with a test rather than land quietly.
	"""

	def test_no_patch_builds_a_sidebar(self):
		post = post_model_sync_patches()
		for retired in (
			"frappe.patches.v16_0.build_module_sidebars",
			"frappe.patches.v16_0.migrate_workspace_sidebar_to_workspace",
			"frappe.patches.v16_0.populate_workspace_sidebar_from_shortcuts",
		):
			self.assertNotIn(retired, post)


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

		# Something in the module for a sidebar item to point at. The backfill does *not* read
		# the module off it: a v15 workspace declares no module and nothing here is allowed to
		# guess one for it. This is what the derived sidebar items end up pointing to.
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
		# workspace itself. `for_user` is the only thing about it the backfill reads.
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

		Shortcuts are what a v15 workspace's navigation *was*, and they stay exactly where they
		are: the page still renders them, and the module's sidebar lists the page.
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

	def sidebar_payload(self, user, module):
		from frappe.boot import get_module_sidebars

		frappe.set_user(user)
		try:
			return get_module_sidebars().get(module)
		finally:
			frappe.set_user("Administrator")

	def items_of(self, user, module) -> list[str]:
		"""What `user`'s sidebar for `module` links to -- empty when it resolves to nothing.

		A module that resolves to nothing for someone is absent from the payload rather than
		present and empty, and "nothing to show you" is the answer these tests want to make
		assertions against either way.
		"""
		payload = self.sidebar_payload(user, module)
		return [item["link_to"] for item in payload["items"]] if payload else []

	# -- the navigation they land with --------------------------------------------------

	def test_a_shared_v15_workspace_lands_in_the_custom_bucket(self):
		"""Not the module its shortcuts point at. Nothing here knows what these pages are about
		-- `Test V15 Module` is where the *report* lives, which is a fact about the link target
		and not about the page -- so they go somewhere honest and stay reachable."""
		for title in (self.PUBLIC, self.OTHER):
			self.assertEqual(frappe.db.get_value("Workspace", title, "module"), CUSTOM_BUCKET)

	def test_a_private_v15_workspace_lands_in_the_private_bucket(self):
		self.assertEqual(frappe.db.get_value("Workspace", self.PRIVATE, "module"), PRIVATE_BUCKET)

	def test_the_buckets_are_the_sites_own_and_placed_nowhere(self):
		"""`custom` is what stops an app's uninstall taking a module full of the site's
		workspaces; no `app_name` is what makes each stand on the desktop as its own tile."""
		for module in (CUSTOM_BUCKET, PRIVATE_BUCKET):
			bucket = frappe.get_doc("Module Def", module)
			self.assertEqual(bucket.custom, 1, f"{module} would be treated as an app's own module")
			self.assertFalse(bucket.app_name, f"{module} was placed into an app's dock")

	def test_the_bucket_gets_a_sidebar_without_anything_storing_one(self):
		"""Nothing is written on the way in. The bucket's sidebar is computed from what the
		bucket now contains -- which is exactly what the backfill just put in it -- so the
		workspaces are listed, and no row anywhere holds a copy of that list."""
		self.assertFalse(frappe.db.exists("Custom Sidebar", {"module": CUSTOM_BUCKET, "user": ""}))
		self.assertFalse(frappe.db.exists("Sidebar", {"module": CUSTOM_BUCKET}))

		items = self.items_of("Administrator", CUSTOM_BUCKET)
		self.assertIn(self.PUBLIC, items)
		self.assertIn(self.OTHER, items)

	def test_the_sidebar_reaches_the_navigation_payload(self):
		payload = self.sidebar_payload("Administrator", CUSTOM_BUCKET)
		self.assertIsNotNone(payload, "the upgraded module is missing from bootinfo.module_sidebars")
		self.assertIn(self.PUBLIC, [item["link_to"] for item in payload["items"]])

	def test_the_shortcuts_are_left_where_they_are(self):
		"""A v15 workspace's shortcuts are its own content and stay on the page. Nothing
		flattens them into the sidebar, so nothing can drop one on the way."""
		workspace = frappe.get_doc("Workspace", self.PUBLIC)
		self.assertEqual([s.link_to for s in workspace.shortcuts], [self.REPORT])

	def test_a_private_workspace_appears_in_its_owners_sidebar(self):
		"""Derived, not stored -- and only derivable once the page has a module."""
		self.assertIn(self.PRIVATE, self.items_of(self.USER, PRIVATE_BUCKET))

		# and stays the owner's: the shared bucket is one module for the whole site, so this is
		# what says a second reader is not handed somebody else's pages through it
		self.assertNotIn(self.PRIVATE, self.items_of("Administrator", PRIVATE_BUCKET))

	def test_running_the_backfill_again_moves_nothing(self):
		"""It reads only module-less workspaces, so a second migrate is a no-op -- including
		over anything a site has since moved out of the bucket by hand."""
		frappe.db.set_value("Workspace", self.OTHER, "module", self.MODULE, update_modified=False)
		self.addCleanup(
			frappe.db.set_value, "Workspace", self.OTHER, "module", CUSTOM_BUCKET, update_modified=False
		)

		run_patches([BACKFILL])

		self.assertEqual(frappe.db.get_value("Workspace", self.OTHER, "module"), self.MODULE)
		self.assertEqual(frappe.db.get_value("Workspace", self.PUBLIC, "module"), CUSTOM_BUCKET)

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

	def test_the_grid_is_emptied_before_the_pin_reads_it(self):
		"""What makes holding icon rows mean the grid and not the v12-era desktop: the table is
		truncated in `[pre_model_sync]`, so anything the pin finds was created after. The pin
		has to stay on the far side of that line -- above it, every v12 site gets pinned."""
		self.assertIn(TRUNCATE_ICONS, pre_model_sync_patches())
		self.assertIn(PIN_DESKTOP, post_model_sync_patches())

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
