# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""D14: the icon grid is contained behind its flag.

The grid works exactly as it does today for the customers who have it, and does not exist at all
for the customers who do not. Containment is what makes coexistence safe: an Apps-mode site holds
no icon rows, generated or shipped, so the retiring surface cannot contradict the module-first
model.

Whatever turns the grid on is responsible for there being a grid, so switching to it seeds one.
Switching to Apps deletes nothing, which is what makes the move reversible.

"""

import json
import os
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import (
	add_workspace_to_desktop,
	clear_desktop_icons_cache,
	get_desktop_icons,
	import_desktop_icon_fixtures,
)
from frappe.desk.doctype.desktop_layout.desktop_layout import save_layout
from frappe.desk.doctype.desktop_settings.desktop_settings import (
	APPS,
	DESKTOP_ICONS,
	seed_desktop_icons,
)
from frappe.tests import IntegrationTestCase
from frappe.utils.install import create_desktop_icons_for_app

SHIPPED = "Test Shipped Grid Icon"
MODULE = "Core"
USER = "test-icon-grid@example.com"


@contextmanager
def desktop_page(page: str):
	"""The site on `page` with an empty grid, and everything put back afterwards.

	It uses a savepoint rather than the class rollback, because these rows are the site's own: on a
	development site the grid is real, and a test that leaves it emptied, or seeded with every
	workspace it holds, has broken something the person running it uses. The seeding commits its own
	work, which would release the savepoint, so `commit` is stubbed for the duration and the rollback
	stays reachable.

	"""
	frappe.db.savepoint("icon_grid_containment")
	try:
		with patch.object(frappe.local.db, "commit"):
			frappe.db.delete("Desktop Icon")
			frappe.db.set_single_value("Desktop Settings", "desktop_page", page)
			# Flipping goes through the document, so every other field on the single has to
			# validate too, and a development site can be carrying an `icon_style` from a
			# branch whose options no longer exist. That is not this ticket's subject, so it is
			# normalised here rather than being allowed to decide whether these tests run.
			frappe.db.set_single_value("Desktop Settings", "icon_style", "Subtle")
			frappe.clear_cache()
			clear_desktop_icons_cache()
			yield
	finally:
		frappe.db.rollback(save_point="icon_grid_containment")
		frappe.clear_cache()
		clear_desktop_icons_cache()


@contextmanager
def shipped_icon_fixture(app: str = "frappe"):
	"""An app shipping one icon fixture, for the length of the test.

	It is written to disk rather than mocked, because the import reads the app's folder and the
	question here is whether that folder is looked at at all.

	"""
	from frappe.modules.utils import get_app_level_directory_path

	folder = get_app_level_directory_path("desktop_icon", app)
	created_folder = not os.path.exists(folder)
	if created_folder:
		os.makedirs(folder)

	path = os.path.join(folder, "test_shipped_grid_icon.json")
	with open(path, "w") as fixture:
		fixture.write(
			json.dumps(
				{
					"app": app,
					"doctype": "Desktop Icon",
					"icon_type": "Folder",
					"label": SHIPPED,
					"link": "https://frappe.io",
					"link_type": "External",
					"modified": "2026-01-01 00:00:00.000000",
					"name": SHIPPED,
					"standard": 1,
				}
			)
		)
	try:
		yield
	finally:
		os.remove(path)
		if created_folder:
			os.rmdir(folder)


@contextmanager
def enqueued_work_runs_now():
	"""Run what the settings save hands to the queue, here, so its effect is observable."""

	def run(method, **kwargs):
		frappe.call(method)

	with patch("frappe.enqueue", side_effect=run) as enqueue:
		yield enqueue


class IconGridTestCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")

	def flip(self, page: str):
		"""Change the desktop page the way a System Manager does, through the document."""
		settings = frappe.get_doc("Desktop Settings")
		settings.desktop_page = page
		settings.save()
		frappe.clear_cache()
		clear_desktop_icons_cache()

	def make_icon(self, label: str, **kwargs):
		icon = frappe.get_doc(
			{
				"doctype": "Desktop Icon",
				"label": label,
				"icon_type": "Folder",
				"link_type": "External",
				**kwargs,
			}
		).insert()
		return icon

	def make_public_workspace(self, title: str):
		return frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": title,
				"module": MODULE,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)

	def visible_icons(self, module_sidebars: dict | None = None) -> set[str]:
		"""The labels the desktop payload carries for the current user."""
		clear_desktop_icons_cache()
		bootinfo = frappe._dict(module_sidebars=module_sidebars or {})
		return {icon.label for icon in get_desktop_icons(bootinfo=bootinfo)}


class TestAnAppsModeSiteHoldsNoIconRows(IconGridTestCase):
	"""Containment: the producers are gated, not the readers."""

	def test_an_app_install_seeds_nothing(self):
		with desktop_page(APPS):
			create_desktop_icons_for_app("frappe")

			self.assertEqual(frappe.db.count("Desktop Icon"), 0)

	def test_a_fixture_import_lands_nothing(self):
		"""The guard the generator already carried, now on the shipped rows too. Otherwise containment
		holds for what the site generates and not for what its apps ship.
		"""
		with desktop_page(APPS), shipped_icon_fixture():
			import_desktop_icon_fixtures("frappe")

			self.assertEqual(frappe.db.count("Desktop Icon"), 0)


class TestAGridModeSiteStillGetsItsIcons(IconGridTestCase):
	"""The other half: nothing about containment may reach a customer who has the grid."""

	def test_an_app_install_seeds_the_apps_and_the_workspaces_icons(self):
		with desktop_page(DESKTOP_ICONS):
			workspace = self.make_public_workspace("Test Grid Workspace")

			create_desktop_icons_for_app("frappe")

			self.assertTrue(frappe.db.exists("Desktop Icon", workspace.name))
			self.assertTrue(
				frappe.db.exists("Desktop Icon", {"icon_type": "App", "app": "frappe"}),
				"the installed app itself has no icon",
			)

	def test_a_fixture_import_lands_the_shipped_rows(self):
		with desktop_page(DESKTOP_ICONS), shipped_icon_fixture():
			import_desktop_icon_fixtures("frappe")

			self.assertTrue(frappe.db.exists("Desktop Icon", SHIPPED))

	def test_a_generated_workspace_icon_records_the_app_it_came_from(self):
		"""Without it the row is invisible to the reaper, and to anything else that asks an icon which
		app it belongs to. The generator was setting a field the doctype has no column for, so every
		generated row landed with no app.
		"""
		with desktop_page(DESKTOP_ICONS):
			workspace = self.make_public_workspace("Test Attributed Workspace")

			create_desktop_icons_for_app("frappe")

			self.assertEqual(frappe.db.get_value("Desktop Icon", workspace.name, "app"), "frappe")


class TestTheFlagIsWhatSeedsTheGrid(IconGridTestCase):
	"""Whatever turns the grid on is responsible for there being a grid."""

	def test_flipping_to_the_grid_seeds_it(self):
		"""Gating the producers without this reproduces the empty-grid defect on a path any
		System Manager can reach."""
		with desktop_page(APPS), shipped_icon_fixture():
			self.assertEqual(frappe.db.count("Desktop Icon"), 0, "sanity: nothing to start with")

			with enqueued_work_runs_now():
				self.flip(DESKTOP_ICONS)

			self.assertTrue(frappe.db.count("Desktop Icon") > 0, "the site landed on an empty grid")
			self.assertTrue(frappe.db.exists("Desktop Icon", SHIPPED), "shipped rows did not arrive")

	def test_the_seeding_does_not_block_the_settings_save(self):
		with desktop_page(APPS):
			with patch("frappe.enqueue") as enqueue:
				self.flip(DESKTOP_ICONS)

			self.assertTrue(enqueue.called, "the flip seeds nothing")
			self.assertEqual(frappe.db.count("Desktop Icon"), 0, "the save waited on the seeding")

	def test_seeding_busts_the_empty_grid_anyone_cached_while_it_was_queued(self):
		"""The save clears every cache, but the job runs after it, so a user who boots in between
		caches an empty grid and keeps it. The rows cannot clear it themselves: a generated icon is
		not `standard`, so its own `on_update` reaches only the job's user.

		"""
		with desktop_page(DESKTOP_ICONS), shipped_icon_fixture():
			frappe.cache.hset("desktop_icons", USER, [])

			seed_desktop_icons()

			self.assertIsNone(frappe.cache.hget("desktop_icons", USER))

	def test_flipping_to_apps_deletes_nothing(self):
		"""What makes the nudge honestly reversible: the rows and the arrangement survive."""
		with desktop_page(DESKTOP_ICONS):
			icon = self.make_icon("Test Surviving Icon", idx=7)
			layout = frappe.get_doc(
				{"doctype": "Desktop Layout", "user": "Administrator", "layout": '["Test Surviving Icon"]'}
			).insert()

			with enqueued_work_runs_now():
				self.flip(APPS)

			self.assertEqual(frappe.db.get_value("Desktop Icon", icon.name, "idx"), 7)
			self.assertEqual(frappe.db.get_value("Desktop Layout", layout.name, "layout"), layout.layout)

	def test_flipping_back_leaves_the_arrangement_exactly_as_it_was(self):
		with desktop_page(DESKTOP_ICONS):
			icon = self.make_icon("Test Round Trip Icon", idx=3)

			with enqueued_work_runs_now():
				self.flip(APPS)
				self.flip(DESKTOP_ICONS)

			self.assertEqual(frappe.db.get_value("Desktop Icon", icon.name, "idx"), 3)

	def test_repeated_flips_accumulate_no_duplicate_rows(self):
		"""Both producers are idempotent, so seeding a grid that already exists is a no-op."""
		with desktop_page(APPS), shipped_icon_fixture():
			with enqueued_work_runs_now():
				self.flip(DESKTOP_ICONS)
				seeded = frappe.db.count("Desktop Icon")

				self.flip(APPS)
				self.flip(DESKTOP_ICONS)

			self.assertEqual(frappe.db.count("Desktop Icon"), seeded)


class TestTheGridWorksExactlyAsItDoesToday(IconGridTestCase):
	"""Rows stay authored rather than derived: they own existence and presentation, and the module
	model owns visibility and routing. The two gates compose with AND and are never reconciled.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("User", USER):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": USER,
					"first_name": "Icon Grid",
					"send_welcome_email": 0,
					"roles": [{"role": "System Manager"}],
				}
			).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_a_folder_and_the_icons_inside_it_reach_the_desktop(self):
		"""A fully-derived grid was rejected because it destroys exactly this: a folder has no module
		to be derived from.
		"""
		with desktop_page(DESKTOP_ICONS):
			self.make_icon("Test Icon Folder", icon_type="Folder")
			self.make_icon("Test Foldered Icon", icon_type="Folder", parent_icon="Test Icon Folder")

			visible = self.visible_icons()

			self.assertIn("Test Icon Folder", visible)
			self.assertIn("Test Foldered Icon", visible)

	def test_an_external_url_icon_reaches_the_desktop(self):
		"""It resolves to a URL rather than to a sidebar, so nothing about the module model decides
		whether it belongs there.
		"""
		with desktop_page(DESKTOP_ICONS):
			self.make_icon("Test External Icon", link="https://frappe.io")

			self.assertIn("Test External Icon", self.visible_icons())

	def test_icon_roles_narrow_what_a_user_sees(self):
		with desktop_page(DESKTOP_ICONS):
			self.make_icon("Test Open Icon")
			self.make_icon("Test Restricted Icon", roles=[{"role": "Prepared Report User"}])

			frappe.set_user(USER)
			visible = self.visible_icons()

			self.assertIn("Test Open Icon", visible)
			self.assertNotIn("Test Restricted Icon", visible)

	def test_a_folder_with_no_module_is_still_hidden_by_its_roles(self):
		"""What the icon gate is for: the module model cannot hide a folder, because a folder has no
		module.
		"""
		with desktop_page(DESKTOP_ICONS):
			self.make_icon(
				"Test Restricted Folder", icon_type="Folder", roles=[{"role": "Prepared Report User"}]
			)

			frappe.set_user(USER)

			self.assertNotIn("Test Restricted Folder", self.visible_icons())

	def test_a_restricted_icon_can_still_be_deleted(self):
		"""`restrict_removal` means what it always did: it hides the remove control in the grid's edit
		mode. `check_for_restrict_removal` stays available for a caller that is genuinely removing an
		icon from the grid, but wiring it into document deletion would make a workspace that deletes
		fine today start throwing.
		"""
		with desktop_page(DESKTOP_ICONS):
			icon = self.make_icon("Test Restricted Removal Icon", restrict_removal=1)

			frappe.delete_doc("Desktop Icon", icon.name)

			self.assertFalse(frappe.db.exists("Desktop Icon", icon.name))


class TestTheWorkspaceIconDeletePathIsGated(IconGridTestCase):
	"""By construction, rather than by the table happening to be empty in Apps mode."""

	def test_deleting_a_workspace_in_grid_mode_takes_its_icon(self):
		with desktop_page(DESKTOP_ICONS):
			workspace = self.make_public_workspace("Test Grid Deleted Page")
			self.make_icon(workspace.name, icon_type="Link", link_type="Workspace Sidebar")

			frappe.delete_doc("Workspace", workspace.name, force=True)

			self.assertFalse(frappe.db.exists("Desktop Icon", workspace.name))

	def test_a_private_page_does_not_take_a_public_ones_icon(self):
		"""The grid labels an icon with the workspace's name, and a private page's name carries an
		owner suffix its title does not, so matching on the title takes down a public page's icon
		whenever someone deletes a private page with the same title.
		"""
		with desktop_page(DESKTOP_ICONS):
			public = self.make_public_workspace("Test Shared Title Page")
			self.make_icon(public.name, icon_type="Link", link_type="Workspace Sidebar")

			private = frappe.get_doc(
				{
					"doctype": "Workspace",
					"title": public.title,
					"label": f"{public.title}-{USER}",
					"module": MODULE,
					"public": 0,
					"for_user": USER,
					"content": "[]",
				}
			).insert(ignore_permissions=True)
			frappe.delete_doc("Workspace", private.name, force=True)

			self.assertTrue(frappe.db.exists("Desktop Icon", public.name))

	def test_deleting_a_workspace_in_apps_mode_touches_no_icon_row(self):
		"""An Apps-mode site holds no icon rows, so this never had anything to delete, but it ran
		anyway, which is containment holding by accident rather than by design.
		"""
		with desktop_page(APPS):
			workspace = self.make_public_workspace("Test Apps Deleted Page")
			self.make_icon(workspace.name, icon_type="Link", link_type="Workspace Sidebar")

			frappe.delete_doc("Workspace", workspace.name, force=True)

			self.assertTrue(frappe.db.exists("Desktop Icon", workspace.name))


class TestNothingWritesToTheArchivedSidebarDoctype(IconGridTestCase):
	"""The v16 sidebar doctype retires as an inert archive and the migration converts it, so a
	surface still creating rows on it would change the conversion's input.
	"""

	def test_adding_a_workspace_to_the_desktop_creates_no_archive_row(self):
		with desktop_page(DESKTOP_ICONS):
			workspace = self.make_public_workspace("Test Undocumented Page")

			add_workspace_to_desktop(workspace.name)

			self.assertTrue(frappe.db.exists("Desktop Icon", workspace.name))
			self.assertFalse(frappe.db.exists("Workspace Sidebar", workspace.name))

	def test_the_grids_own_save_path_creates_no_archive_row(self):
		"""The desktop write path a user actually reaches: dropping a new workspace onto the
		grid and saving the layout."""
		with desktop_page(DESKTOP_ICONS):
			title = "Test Layout Page"
			new_icons = json.dumps([{"workspace": {"label": title, "public": 1, "module": MODULE}}])

			save_layout(user="Administrator", layout="[]", new_icons=new_icons)

			self.addCleanup(frappe.delete_doc, "Workspace", title, force=True, ignore_missing=True)
			self.assertTrue(frappe.db.exists("Desktop Icon", title))
			self.assertFalse(frappe.db.exists("Workspace Sidebar", title))
