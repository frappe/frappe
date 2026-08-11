# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""What a v16 customer gets from `bench update`.

They have the previous navigation in full: a `Workspace Sidebar` per workspace, personal forks
of those sidebars per user, and a container holding everyone's private pages. None of it used
to reach the conversion -- it read a column that version never had -- so on every shipped v16
site the migration found nothing and the personal-sidebar drop stayed silent.

These tests seed that shape, run the conversion, and read the result off the surfaces the desk
actually boots from.
"""

from unittest.mock import patch

import frappe
from frappe.desk.doctype.module_sidebar.module_sidebar import clear_computed_base_cache
from frappe.desk.doctype.module_sidebar.test_module_sidebar import no_developer_mode
from frappe.tests import IntegrationTestCase


def archive(title, items, module=None, for_user=None, standard=0):
	"""A row as v16 left it. Inserted under `in_patch`: the archive takes no new entries, and
	a fixture standing in for what a v16 site already holds is the system's own write."""
	original = frappe.flags.get("in_patch")
	frappe.flags.in_patch = True
	try:
		return frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"title": title,
				"module": module,
				"for_user": for_user,
				"standard": standard,
				"items": items,
			}
		).insert(ignore_permissions=True)
	finally:
		frappe.flags.in_patch = original


def run_conversion() -> list[str]:
	"""The patch, exactly as `bench migrate` runs it, with everything it printed."""
	lines = []
	with patch("click.secho", side_effect=lambda message="", **kwargs: lines.append(message)):
		frappe.get_attr("frappe.patches.v16_0.build_module_sidebars.execute")()
	return lines


class TestV16Upgrade(IntegrationTestCase):
	"""One seeded v16 site, upgraded once -- as a migrate would."""

	MODULE = "Test V16 Module"
	QUIET_MODULE = "Test V16 Unconverted Module"
	REPORT = "V16 Module Report"
	OTHER_REPORT = "V16 Other Report"
	USER = "test-v16-upgrade@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		with no_developer_mode():
			for module in (cls.MODULE, cls.QUIET_MODULE):
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": module, "app_name": "frappe"}
				).insert()
				clear_computed_base_cache(module)

		for name in (cls.REPORT, cls.OTHER_REPORT):
			frappe.get_doc(
				{
					"doctype": "Report",
					"report_name": name,
					"ref_doctype": "ToDo",
					"report_type": "Report Builder",
					"module": cls.MODULE,
					"is_standard": "No",
				}
			).insert()
		clear_computed_base_cache(cls.MODULE)

		frappe.get_doc(
			{
				"doctype": "User",
				"email": cls.USER,
				"first_name": "V16",
				"send_welcome_email": 0,
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_if_duplicate=True)

		# Two sidebars on one module -- the collapse case -- plus one item the module's own
		# contents cannot account for, which is what has to be carried whole.
		archive(
			"V16 Primary",
			[
				{"type": "Link", "link_type": "Report", "link_to": cls.REPORT, "label": "Report"},
				{"type": "Link", "link_type": "DocType", "link_to": "ToDo", "label": "Todos"},
			],
			module=cls.MODULE,
			standard=1,
		)
		archive(
			"V16 Secondary",
			[{"type": "Link", "link_type": "Report", "link_to": cls.OTHER_REPORT, "label": "Other"}],
			module=cls.MODULE,
			standard=1,
		)

		# The normal v16 customization: a whole sidebar forked for one user on any edit.
		archive(
			"V16 Primary-test-v16-upgrade@example.com",
			[{"type": "Link", "link_type": "Report", "link_to": cls.OTHER_REPORT, "label": "Mine"}],
			module=cls.MODULE,
			for_user=cls.USER,
		)

		# The container v16 hung everyone's private pages off. Nothing in it is authored.
		archive(
			"V16 My Workspaces",
			[{"type": "Link", "link_type": "Workspace", "link_to": "Welcome Workspace"}],
			module=cls.MODULE,
		)

		cls.before = frappe.db.count("Workspace Sidebar"), frappe.db.count("Workspace Sidebar Item")
		cls.output = run_conversion()

	@classmethod
	def tearDownClass(cls):
		frappe.clear_cache()
		super().tearDownClass()

	def site_layer(self):
		return frappe.get_doc("Custom Module Sidebar", {"module": self.MODULE, "user": ""})

	def user_layer(self):
		return frappe.get_doc("Custom Module Sidebar", {"module": self.MODULE, "user": self.USER})

	# -- the drop this whole conversion exists to fix -----------------------------------

	def test_a_personal_fork_becomes_that_users_own_layer(self):
		"""It used to be mapped to a private workspace and then filtered out for not being
		public -- no warning, no landing place. It is the *normal* v16 customization."""
		layer = self.user_layer()
		self.assertEqual(layer.user, self.USER)
		self.assertIn(self.OTHER_REPORT, [row.link_to for row in layer.sidebar_items])

	def test_the_conversion_is_no_longer_a_no_op(self):
		self.assertTrue(self.site_layer().sidebar_items)

	# -- nothing is destroyed, so it can all be done again -------------------------------

	def test_the_source_rows_are_untouched(self):
		self.assertEqual(
			self.before,
			(frappe.db.count("Workspace Sidebar"), frappe.db.count("Workspace Sidebar Item")),
		)

	def test_running_it_again_changes_nothing(self):
		layer = self.site_layer()
		before = [(row.link_to, row.added) for row in layer.sidebar_items]

		run_conversion()

		after = self.site_layer()
		self.assertEqual(layer.creation, after.creation)
		self.assertEqual(before, [(row.link_to, row.added) for row in after.sidebar_items])

	def test_a_migrate_does_not_delete_the_archive(self):
		"""The reaper walks a fixed list, and the archive is not on it -- so a standard row
		whose file has gone (they are all going) is left exactly where it is."""
		from frappe.model.sync import APP_LEVEL_ENTITIES, ORPHANABLE_ENTITIES

		self.assertNotIn("Workspace Sidebar", ORPHANABLE_ENTITIES + APP_LEVEL_ENTITIES)
		self.assertTrue(frappe.db.exists("Workspace Sidebar", "V16 Primary"))

	# -- what the customer sees ----------------------------------------------------------

	def test_the_sidebar_carries_the_same_items(self):
		payload = self.payload()
		self.assertIsNotNone(payload)
		links = [item["link_to"] for item in payload["items"]]
		for expected in (self.REPORT, self.OTHER_REPORT, "ToDo"):
			self.assertIn(expected, links)

	def test_an_item_the_module_already_contains_stays_maintained(self):
		"""Stored as a reference, so the label keeps coming from the base underneath it --
		which is the difference between a migrated sidebar and a frozen copy of one."""
		rows = {row.link_to: row.added for row in self.site_layer().sidebar_items}
		self.assertEqual(rows[self.REPORT], 0)
		# nothing in this module accounts for ToDo, so there is nothing to refer to
		self.assertEqual(rows["ToDo"], 1)

	def test_several_sidebars_on_one_module_collapse_without_losing_content(self):
		links = [row.link_to for row in self.site_layer().sidebar_items]
		self.assertIn(self.REPORT, links)
		self.assertIn(self.OTHER_REPORT, links)

	def test_every_merge_is_named(self):
		merges = [line for line in self.output if "V16 Secondary" in line]
		self.assertTrue(merges, f"the merge was not named in output: {self.output}")

	def test_a_private_workspace_container_is_discarded_and_said_so(self):
		self.assertNotIn("Welcome Workspace", [row.link_to for row in self.site_layer().sidebar_items])
		discarded = [line for line in self.output if "private-workspace container" in line]
		self.assertTrue(discarded, f"the discard was not named in output: {self.output}")

	def test_a_module_whose_app_never_re_exported_gets_a_computed_sidebar(self):
		"""App-shipped sidebar fixtures stop arriving. That is only safe because the base is
		computed: the module degrades to a generated sidebar, not to nothing."""
		self.assertFalse(frappe.db.exists("Custom Module Sidebar", {"module": self.QUIET_MODULE}))
		self.assertFalse(frappe.db.exists("Module Sidebar", {"module": self.QUIET_MODULE}))

		from frappe.boot import get_sidebar_bases

		base = get_sidebar_bases([self.QUIET_MODULE])[self.QUIET_MODULE]
		self.assertEqual(base.module, self.QUIET_MODULE)

	def payload(self):
		from frappe.boot import get_module_sidebars

		return get_module_sidebars().get(self.MODULE)


class TestTheArchiveIsInert(IntegrationTestCase):
	"""Nothing reads it at runtime and nothing writes a row to it."""

	def test_nobody_can_create_a_row(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Workspace Sidebar",
					"title": "V16 Hand Authored",
					"items": [{"type": "Link", "link_type": "DocType", "link_to": "ToDo"}],
				}
			).insert(ignore_permissions=True)

	def test_the_doctype_grants_nobody_write(self):
		meta = frappe.get_meta("Workspace Sidebar")
		self.assertFalse([perm for perm in meta.permissions if perm.create or perm.write])

	def test_its_fixtures_are_no_longer_imported(self):
		"""An app ships a `Module Sidebar` now, which rides the ordinary per-module walk."""
		import inspect

		from frappe.model import sync

		self.assertNotIn("app_level_folders", inspect.getsource(sync.sync_for))

	def test_the_reaper_leaves_it_alone(self):
		"""Its files are going away, and the reaper deletes a standard row whose file is gone
		-- left in that list it would delete the very rows the conversion reads."""
		from frappe.model.sync import APP_LEVEL_ENTITIES, ORPHANABLE_ENTITIES

		self.assertNotIn("Workspace Sidebar", ORPHANABLE_ENTITIES + APP_LEVEL_ENTITIES)


class TestTheIntermediateColumnIsGone(IntegrationTestCase):
	"""It never shipped in any release, so it goes outright -- no patch, no notice."""

	def test_the_workspace_has_no_sidebar_items(self):
		self.assertFalse(frappe.get_meta("Workspace").get_field("sidebar_items"))

	def test_no_patch_was_written_for_it(self):
		from frappe.modules.patch_handler import PatchType, get_patches_from_app

		patches = " ".join(get_patches_from_app("frappe", PatchType.post_model_sync))
		self.assertNotIn("sidebar_items", patches)
