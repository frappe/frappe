# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""What a v16 customer gets from `bench update`.

They have the previous navigation in full: a `Workspace Sidebar` per workspace, personal forks of
those sidebars per user, and a container holding everyone's private pages. The site-level rows
become each module's `Sidebar`, the base the desk reads, which is what they were, and a fork
becomes a `Custom Sidebar` for its owner, which is what it was. Writing the base is also what lets
an app take its own sidebar back later: a `Sidebar` is named by its title, so an app titling its
sidebar what the site's was called lands on that row, and one titling it after the module wins by
the naming rule instead.

These tests seed that shape, run the patch as a migrate would, and read the result off the
surfaces the desk boots from.

"""

from unittest.mock import patch

import frappe
from frappe.desk.doctype.sidebar.sidebar import clear_computed_base_cache, resolve_sidebar
from frappe.desk.doctype.sidebar.test_sidebar import make_sidebar, no_developer_mode
from frappe.tests import IntegrationTestCase

CONVERT = "frappe.patches.v16_0.convert_sidebars"


def archive(title, items, module=None, for_user=None, standard=0):
	"""A row as v16 left it. It is inserted under `in_patch`, because the archive takes no new
	entries and a fixture standing in for what a v16 site already holds is the system's own write.
	"""
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
	"""Run the patch exactly as `bench migrate` does, returning everything it printed.

	It runs under `in_patch` because that is what the patch handler sets around every patch, and the
	conversion writes a `Sidebar`, which is app content that a customer site only accepts from the
	system (`Sidebar.validate_app_content`).

	"""
	lines = []
	original = frappe.flags.get("in_patch")
	frappe.flags.in_patch = True
	try:
		with patch("click.secho", side_effect=lambda message="", **kwargs: lines.append(message)):
			frappe.get_attr(CONVERT + ".execute")()
	finally:
		frappe.flags.in_patch = original
	return lines


class TestV16Upgrade(IntegrationTestCase):
	"""One seeded v16 site, and what its modules resolve to afterwards."""

	MODULE = "Test V16 Module"
	QUIET_MODULE = "Test V16 Unconverted Module"
	SHIPPED_MODULE = "Test V16 Re-exported Module"
	REPORT = "V16 Module Report"
	OTHER_REPORT = "V16 Other Report"
	SHIPPED_REPORT = "V16 Re-exported Report"
	PRIVATE_PAGE = "V16 Personal Page"
	USER = "test-v16-upgrade@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		with no_developer_mode():
			for module in (cls.MODULE, cls.QUIET_MODULE, cls.SHIPPED_MODULE):
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
				"doctype": "Report",
				"report_name": cls.SHIPPED_REPORT,
				"ref_doctype": "ToDo",
				"report_type": "Report Builder",
				"module": cls.SHIPPED_MODULE,
				"is_standard": "No",
			}
		).insert()
		clear_computed_base_cache(cls.SHIPPED_MODULE)

		frappe.get_doc(
			{
				"doctype": "User",
				"email": cls.USER,
				"first_name": "V16",
				"send_welcome_email": 0,
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_if_duplicate=True)

		# The kind of page the private container below hangs off: one a person owns.
		frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": cls.PRIVATE_PAGE,
				"label": cls.PRIVATE_PAGE,
				"module": cls.MODULE,
				"public": 0,
				"for_user": cls.USER,
				"content": "[]",
			}
		).insert(ignore_permissions=True)

		# Two sidebars on one module, a personal fork of one of them, and the container v16 hung
		# everyone's private pages off: the whole shape a v16 site arrives carrying.
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
		archive(
			"V16 Primary-test-v16-upgrade@example.com",
			[{"type": "Link", "link_type": "Report", "link_to": cls.OTHER_REPORT, "label": "Mine"}],
			module=cls.MODULE,
			for_user=cls.USER,
		)
		archive(
			"V16 My Workspaces",
			[{"type": "Link", "link_type": "Workspace", "link_to": cls.PRIVATE_PAGE}],
			module=cls.MODULE,
		)
		archive(
			f"My Workspaces-{cls.USER}",
			[{"type": "Link", "link_type": "Workspace", "link_to": cls.PRIVATE_PAGE}],
			module=cls.MODULE,
			for_user=cls.USER,
		)

		# An app that *has* re-exported: it ships the module's sidebar in the current model, and
		# its old fixture is still sitting in the archive saying something different.
		cls.shipped = make_sidebar(cls.SHIPPED_MODULE)
		archive(
			"V16 Re-exported",
			[{"type": "Link", "link_type": "Report", "link_to": cls.SHIPPED_REPORT, "label": "Old"}],
			module=cls.SHIPPED_MODULE,
			standard=1,
		)

		cls.before = frappe.db.count("Workspace Sidebar"), frappe.db.count("Workspace Sidebar Item")
		cls.output = run_conversion()

	@classmethod
	def tearDownClass(cls):
		frappe.clear_cache()
		super().tearDownClass()

	def resolved(self, user=None):
		"""What the module resolves to for this user, asked of the resolver itself."""
		return resolve_sidebar(self.MODULE, user or frappe.session.user)

	def user_layer(self):
		return frappe.get_doc("Custom Sidebar", {"module": self.MODULE, "user": self.USER})

	def base(self, module=None):
		return frappe.get_doc("Sidebar", module or self.MODULE)

	# -- the base: what everybody was being shown ----------------------------------------

	def test_the_site_level_rows_become_the_modules_sidebar(self):
		"""Not a `Custom Sidebar`: a layer means the site disagrees with the base, and this content is
		not a disagreement. It is the base, recovered from where v16 kept it.
		"""
		self.assertFalse(frappe.db.exists("Custom Sidebar", {"module": self.MODULE, "user": ""}))

		links = [row.link_to for row in self.base().items]
		self.assertIn(self.REPORT, links)
		self.assertIn("ToDo", links)

	def test_the_converted_base_is_not_standard(self):
		"""`standard` means a file in an app backs the row, and none does, since the fixture it came
		from stops being imported with this release. Marked standard, orphan removal would delete it
		on the next migrate, because that is exactly what it reaps.

		The sweep itself is covered by `test_site_owned_row_survives_orphan_removal`. It is not run
		here because `remove_orphan_entities` commits, which would push this class's fixtures past its
		own rollback and leave them on the site.

		"""
		from frappe.model.sync import ORPHANABLE_ENTITIES

		self.assertEqual(self.base().standard, 0)
		self.assertIn("Sidebar", ORPHANABLE_ENTITIES)

	def test_several_sidebars_on_one_module_collapse_without_losing_content(self):
		"""v16 held one per workspace and a module now holds one, so the rest become sections, which is
		a demotion rather than a deletion.
		"""
		base = self.base()
		self.assertIn(self.OTHER_REPORT, [row.link_to for row in base.items])

		sections = [row.label for row in base.items if row.type == "Section Break"]
		self.assertIn("V16 Secondary", sections)

	def test_the_items_are_carried_whole(self):
		"""A base row is an item, with nothing underneath it to take a label from, so what v16 called
		things is what the desk keeps calling them.
		"""
		labels = {row.link_to: row.label for row in self.base().items if row.link_to}
		self.assertEqual(labels["ToDo"], "Todos")
		self.assertEqual(labels[self.REPORT], "Report")

	def test_the_base_keeps_the_v16_title(self):
		"""What the customer was reading yesterday. A merge takes the module name, since the union of
		two sidebars is not either one of them.
		"""
		self.assertEqual(self.base().title, self.MODULE)
		self.assertEqual(self.resolved("Administrator").label, self.MODULE)

	def test_it_is_stamped_with_when_v16_last_wrote_it(self):
		"""Not with today's date. `import_file` skips a file older than the row it would overwrite, so
		a row stamped now would outrank an export its author made last month, and the app could never
		take its own sidebar back.
		"""
		# The newest of the rows it was merged from, which is when this content was last true.
		archived = max(
			frappe.get_all(
				"Workspace Sidebar",
				filters={"name": ["in", ["V16 Primary", "V16 Secondary"]]},
				pluck="modified",
			)
		)
		self.assertEqual(frappe.db.get_value("Sidebar", self.MODULE, "modified"), archived)

	def test_an_app_shipping_its_sidebar_later_takes_over(self):
		"""Why this is a base and not a layer: the module ends up answering with the author's file
		rather than with what the conversion wrote, and nothing has to notice the conversion happened.

		A sidebar is named by its title now, so the two are not always the same record. This module's
		one v16 sidebar was called "V16 Late" and keeps that label, while the app titles its own after
		the module, so the app's lands beside the converted row and the naming rule hands the module to
		it.

		It uses a module of its own, because it deliberately replaces what the conversion wrote and the
		rest of this class reads that.

		"""
		import json
		import os

		from frappe.desk.doctype.sidebar.test_sidebar import module_resolvable_on_disk
		from frappe.modules.import_file import import_file_by_path
		from frappe.utils import add_days, now

		module = "Test V16 Late Export Module"
		with no_developer_mode():
			frappe.get_doc({"doctype": "Module Def", "module_name": module, "app_name": "frappe"}).insert()
		# deleting the module takes its sidebar with it; the archive row is counted by
		# `test_the_source_rows_are_untouched`, so that goes back too
		self.addCleanup(frappe.delete_doc, "Module Def", module, force=True, ignore_missing=True)
		self.addCleanup(frappe.delete_doc, "Workspace Sidebar", "V16 Late", force=True, ignore_missing=True)

		archive(
			"V16 Late",
			[{"type": "Link", "link_type": "DocType", "link_to": "ToDo", "label": "Their Todos"}],
			module=module,
		)
		run_conversion()
		converted = frappe.get_doc("Sidebar", "V16 Late")
		self.assertEqual(converted.module, module, "the conversion kept the v16 label as its name")
		self.assertEqual([row.label for row in converted.items], ["Their Todos"])

		shipped = {
			"doctype": "Sidebar",
			"name": module,
			"module": module,
			"title": module,
			"standard": 1,
			"modified": add_days(now(), 14),
			"items": [
				{
					"doctype": "Sidebar Item",
					"parenttype": "Sidebar",
					"parentfield": "items",
					"idx": 1,
					"type": "Link",
					"link_type": "DocType",
					"link_to": "User",
					"label": "Curated Users",
				}
			],
		}

		with module_resolvable_on_disk(module) as path:
			folder = os.path.join(path, "sidebar", frappe.scrub(module))
			os.makedirs(folder, exist_ok=True)
			f = os.path.join(folder, f"{frappe.scrub(module)}.json")
			with open(f, "w") as handle:
				handle.write(json.dumps(shipped))

			imported = import_file_by_path(f, force=False, ignore_version=True)

		self.assertTrue(imported, "the app's own file was not imported")
		self.assertEqual([row.label for row in self.base(module).items], ["Curated Users"])
		self.assertEqual(
			[item["label"] for item in resolve_sidebar(module, "Administrator").items], ["Curated Users"]
		)

	# -- user layers: what one person did to that -----------------------------------------

	def test_a_personal_fork_becomes_that_users_own_layer(self):
		"""This is the normal v16 customization, since that version forked a whole sidebar per user on
		any edit, and it is the only thing in the archive nothing derives again.
		"""
		layer = self.user_layer()
		self.assertEqual(layer.user, self.USER)
		self.assertIn(self.OTHER_REPORT, [row.link_to for row in layer.sidebar_items])

	def test_an_item_the_module_already_contains_stays_maintained(self):
		"""Stored as a reference, so the label and the link keep coming from the base underneath, which
		is the difference between a converted arrangement and a frozen copy of one.
		"""
		rows = {row.link_to: row.added for row in self.user_layer().sidebar_items if row.link_to}
		self.assertEqual(rows[self.OTHER_REPORT], 0)

	def test_what_the_user_removed_stays_removed(self):
		"""A fork is the whole list, so a removal is an absence. A layer is a delta, where an absence
		says nothing. Converting one into the other is what this row does.
		"""
		self.assertNotIn(self.REPORT, [item["link_to"] for item in self.resolved(self.USER).items])

		# ...and it is *this* person's opinion, not the site's
		self.assertIn(self.REPORT, [item["link_to"] for item in self.resolved("Administrator").items])

	def test_an_item_they_were_never_offered_is_not_hidden(self):
		"""The other half. An item today's base has that v16 never showed them is not something they
		decided against, and hiding it would leave a v16 customer with a permanently smaller sidebar
		than a colleague who never touched theirs.
		"""
		hidden = {row.link_to for row in self.user_layer().sidebar_items if row.hidden}
		self.assertNotIn(self.OTHER_REPORT, hidden)

	def test_the_fork_does_not_rename_the_module(self):
		"""A fork's title is `<sidebar>-<user>`. It is a preference about arrangement and must not
		become a preference about what the module is called.
		"""
		layer = self.user_layer()
		self.assertFalse(layer.label)
		self.assertNotIn(self.USER, self.resolved(self.USER).label)

	def test_a_private_workspace_container_is_passed_over(self):
		"""Every row in one is a link to a page its owner owns, and those are derived on read now, so
		there is nothing in it to convert.
		"""
		self.assertNotIn(self.PRIVATE_PAGE, [row.link_to for row in self.user_layer().sidebar_items])

	# -- nothing is destroyed, so it can all be done again -------------------------------

	def test_running_it_again_changes_nothing(self):
		layer = self.user_layer()
		before = [(row.link_to, row.added, row.hidden) for row in layer.sidebar_items]

		base = self.base()
		base_before = [(row.link_to, row.label) for row in base.items]

		run_conversion()

		after = self.user_layer()
		self.assertEqual(layer.creation, after.creation)
		self.assertEqual(before, [(row.link_to, row.added, row.hidden) for row in after.sidebar_items])

		base_after = self.base()
		self.assertEqual(base.creation, base_after.creation)
		self.assertEqual(base_before, [(row.link_to, row.label) for row in base_after.items])

	def test_the_source_rows_are_untouched(self):
		self.assertEqual(
			self.before,
			(frappe.db.count("Workspace Sidebar"), frappe.db.count("Workspace Sidebar Item")),
		)

	def test_a_migrate_does_not_delete_the_archive(self):
		"""The reaper walks a fixed list and the archive is not on it, so a standard row whose file has
		gone, as they all are going, is left where it is.
		"""
		from frappe.model.sync import APP_LEVEL_ENTITIES, ORPHANABLE_ENTITIES

		self.assertNotIn("Workspace Sidebar", ORPHANABLE_ENTITIES + APP_LEVEL_ENTITIES)
		self.assertTrue(frappe.db.exists("Workspace Sidebar", "V16 Primary"))

	# -- what the customer sees ----------------------------------------------------------

	def test_the_sidebar_carries_the_same_items(self):
		"""For everyone who never customized anything: what v16 was showing them, still there."""
		resolved = self.resolved("Administrator")
		self.assertIsNotNone(resolved)

		links = [item["link_to"] for item in resolved.items]
		for expected in (self.REPORT, self.OTHER_REPORT, "ToDo"):
			self.assertIn(expected, links)

	def test_the_conversion_names_each_fork_it_carried(self):
		"""One line per user whose arrangement moved, naming the rows it was computed from, every one
		of which is still there to check it against.
		"""
		named = [line for line in self.output if self.USER in line]
		self.assertTrue(named, f"the fork was not named in output: {self.output}")

		merges = [line for line in self.output if "V16 Secondary" in line]
		self.assertTrue(merges, f"the merge was not named in output: {self.output}")

	def test_a_module_whose_app_never_re_exported_gets_a_computed_sidebar(self):
		"""App-shipped sidebar fixtures stop arriving. That is only safe because the base is computed:
		the module falls back to a generated sidebar rather than to nothing.
		"""
		self.assertFalse(frappe.db.exists("Custom Sidebar", {"module": self.QUIET_MODULE}))
		self.assertFalse(frappe.db.exists("Sidebar", {"module": self.QUIET_MODULE}))

		from frappe.desk.doctype.sidebar.sidebar import get_sidebar_bases

		base = get_sidebar_bases([self.QUIET_MODULE])[self.QUIET_MODULE]
		self.assertEqual(base.module, self.QUIET_MODULE)


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
		"""An app ships a `Sidebar` now, which rides the ordinary per-module walk."""
		import inspect

		from frappe.model import sync

		self.assertNotIn("app_level_folders", inspect.getsource(sync.sync_for))

	def test_the_reaper_leaves_it_alone(self):
		"""Its files are going away, and the reaper deletes a standard row whose file is gone. Left in
		that list it would delete a site's whole record of its old navigation.
		"""
		from frappe.model.sync import APP_LEVEL_ENTITIES, ORPHANABLE_ENTITIES

		self.assertNotIn("Workspace Sidebar", ORPHANABLE_ENTITIES + APP_LEVEL_ENTITIES)


class TestTheIntermediateColumnIsGone(IntegrationTestCase):
	"""It never shipped in any release, so it goes outright, with no patch and no notice."""

	def test_the_workspace_has_no_sidebar_items(self):
		self.assertFalse(frappe.get_meta("Workspace").get_field("sidebar_items"))

	def test_no_patch_was_written_for_it(self):
		from frappe.modules.patch_handler import PatchType, get_patches_from_app

		patches = " ".join(get_patches_from_app("frappe", PatchType.post_model_sync))
		self.assertNotIn("sidebar_items", patches)
