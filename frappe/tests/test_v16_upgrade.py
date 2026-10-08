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

import json
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.doctype.sidebar.sidebar import clear_computed_base_cache, resolve_sidebar
from frappe.desk.doctype.sidebar.test_sidebar import make_sidebar, no_developer_mode
from frappe.desk.doctype.workspace.workspace import PRIVATE_MODULE
from frappe.patches.v16_0.sidebar_archive import layer_rows, write_user_layer
from frappe.tests import IntegrationTestCase

# in the order `patches.txt` runs them
CONVERSION = (
	"frappe.patches.v16_0.convert_sidebars",
	"frappe.patches.v16_0.convert_custom_sidebars",
	"frappe.patches.v16_0.move_custom_sidebar_workspaces",
	"frappe.patches.v16_0.convert_personal_sidebars",
	"frappe.patches.v16_0.remove_modules_made_from_generated_sidebars",
)


@contextmanager
def in_patch():
	"""Write as the patch handler does. A `Sidebar` is app content, and a customer site only
	accepts one from the system."""
	original = frappe.flags.get("in_patch")
	frappe.flags.in_patch = True
	try:
		yield
	finally:
		frappe.flags.in_patch = original


def archive(title, items, module=None, for_user=None, standard=0, ignore_links=False, app=None):
	"""A row as v16 left it. It is inserted under `in_patch`, because the archive takes no new
	entries and a fixture standing in for what a v16 site already holds is the system's own write.

	`ignore_links` seeds a row that has outlived what it points at. A v16 site acquired such a row
	while the target still existed, so there is no way to write one here honestly except to skip
	the check the site skipped by being older than the deletion.
	"""
	with in_patch():
		return frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"title": title,
				"module": module,
				"for_user": for_user,
				"standard": standard,
				"app": app,
				"items": items,
			}
		).insert(ignore_permissions=True, ignore_links=ignore_links)


def run_conversion() -> list[str]:
	"""Run the patches exactly as `bench migrate` does, returning everything they printed.

	They run under `in_patch` because that is what the patch handler sets around every patch, and the
	conversion writes a `Sidebar`, which is app content that a customer site only accepts from the
	system (`Sidebar.validate_app_content`).

	"""
	lines = []
	with in_patch(), patch("click.secho", side_effect=lambda message="", **kwargs: lines.append(message)):
		for name in CONVERSION:
			frappe.get_attr(name + ".execute")()
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

		# A v16 site carries no `Custom Sidebar` at all: the doctype is new here, and the archive
		# above is the whole of what that version stored. The private page made for these fixtures
		# writes rows of its own on insert (`add_private_to_sidebar`), which a real upgrade would
		# never find, so they are cleared and the conversion starts from what v16 actually left.
		for name in frappe.get_all(
			"Custom Sidebar",
			filters={"module": ["in", [cls.MODULE, cls.QUIET_MODULE, cls.SHIPPED_MODULE, PRIVATE_MODULE]]},
			pluck="name",
		):
			frappe.delete_doc("Custom Sidebar", name, force=True, ignore_permissions=True)

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
			standard=1,
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


class TestALinkThatNoLongerResolves(IntegrationTestCase):
	"""A v16 site's rows outlive the things they point at, and the migrate has to survive that.

	The archive has been filling up for two release lines, and nothing pruned it when an app
	dropped a doctype or a customer uninstalled an app. erpnext's shipped v16 sidebars still name
	`Repost Accounting Ledger Settings`, which it deleted in April, so this is not a hypothetical:
	a plain `insert` validates those links and one dead row takes the whole `bench update` down
	with it, partway through `run_schema_updates`.

	The item is carried rather than dropped. A broken link on a sidebar is something a person can
	see and remove; a migrate that stops halfway is not.
	"""

	MODULE = "Test V16 Dangling Module"
	GONE = "V16 Doctype That Was Deleted"
	USER = "test-v16-dangling@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		with no_developer_mode():
			frappe.get_doc(
				{"doctype": "Module Def", "module_name": cls.MODULE, "app_name": "frappe"}
			).insert()
			clear_computed_base_cache(cls.MODULE)

		frappe.get_doc(
			{
				"doctype": "User",
				"email": cls.USER,
				"first_name": "V16 Dangling",
				"send_welcome_email": 0,
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_if_duplicate=True)

		# One row that still resolves and one that does not, because a sidebar of nothing but dead
		# links would convert even if the dead one were quietly dropped.
		items = [
			{"type": "Link", "link_type": "DocType", "link_to": "ToDo", "label": "Todos"},
			{"type": "Link", "link_type": "DocType", "link_to": cls.GONE, "label": "Gone"},
		]
		archive("V16 Dangling", items, module=cls.MODULE, standard=1, ignore_links=True)
		archive(f"V16 Dangling-{cls.USER}", items, module=cls.MODULE, for_user=cls.USER, ignore_links=True)

		cls.output = run_conversion()

	@classmethod
	def tearDownClass(cls):
		frappe.clear_cache()
		super().tearDownClass()

	def test_the_doctype_really_is_gone(self):
		"""The premise. If something ever creates it, these tests would pass without testing
		anything."""
		self.assertFalse(frappe.db.exists("DocType", self.GONE))

	def test_the_module_still_converts(self):
		self.assertTrue(frappe.db.exists("Sidebar", {"module": self.MODULE}))

	def test_the_dead_row_is_carried_not_dropped(self):
		base = frappe.get_doc("Sidebar", {"module": self.MODULE})
		self.assertEqual([row.link_to for row in base.items], ["ToDo", self.GONE])

	def test_a_fork_holding_one_converts_too(self):
		"""`write_user_layer` inserts a `Custom Sidebar` off the same rows, so it is exposed the same
		way and is easy to fix on only one of the two paths."""
		self.assertTrue(frappe.db.exists("Custom Sidebar", {"module": self.MODULE, "user": self.USER}))


class TestRowTypesTheNewSidebarDropped(IntegrationTestCase):
	"""v16's sidebar editor offered `Spacer` and `Sidebar Item Group` rows. A site that used either
	must still migrate: spacers carry over, and the report-group button, whose doctype is gone, is
	left behind.
	"""

	MODULE = "Test V16 Spacer Module"
	USER = "test-v16-spacer@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		with no_developer_mode():
			frappe.get_doc(
				{"doctype": "Module Def", "module_name": cls.MODULE, "app_name": "frappe"}
			).insert()
			clear_computed_base_cache(cls.MODULE)

		frappe.get_doc(
			{"doctype": "User", "email": cls.USER, "first_name": "V16 Spacer", "send_welcome_email": 0}
		).insert(ignore_if_duplicate=True).add_roles("Desk User")

		items = [
			{"type": "Link", "link_type": "DocType", "link_to": "ToDo", "label": "Todos"},
			{"type": "Spacer"},
			{"type": "Sidebar Item Group", "label": "Reports"},
			{"type": "Link", "link_type": "DocType", "link_to": "Event", "label": "Events"},
			{"type": "Spacer"},
		]
		archive("V16 Spacers", items, module=cls.MODULE, standard=1)
		# a second sidebar in the module, merged into the same base, with an unnamed spacer of its own
		# and a title as long as v16 allowed, which a spacer label must not overflow
		archive("V16 More Spacers ".ljust(140, "x"), [{"type": "Spacer"}], module=cls.MODULE, standard=1)
		archive(f"V16 Spacers-{cls.USER}", items, module=cls.MODULE, for_user=cls.USER)
		cls.output = run_conversion()

	@classmethod
	def tearDownClass(cls):
		frappe.clear_cache()
		super().tearDownClass()

	def base_types(self):
		return [row.type for row in frappe.get_doc("Sidebar", {"module": self.MODULE}).items]

	def test_spacers_carry_over_and_the_group_does_not(self):
		self.assertEqual(self.base_types()[:4], ["Link", "Spacer", "Link", "Spacer"])
		self.assertNotIn("Sidebar Item Group", self.base_types())

	def test_spacers_from_two_merged_sidebars_all_survive(self):
		"""Each sidebar numbers its own spacers, so the merge must not see two of them as one."""
		self.assertEqual(self.base_types().count("Spacer"), 3)

	def test_a_normal_user_sees_every_spacer(self):
		"""Spacers link nowhere, so the permission filter must not drop them, and two of them must
		not collapse into one as duplicates."""
		shell = frappe.db.get_value("Sidebar", {"module": self.MODULE})
		items = resolve_sidebar(shell, self.USER).items
		self.assertEqual([item["type"] for item in items].count("Spacer"), 3)

	def test_a_forks_spacers_refer_to_the_sidebar_it_copied(self):
		"""Not added again with the originals hidden, which is what a fork-specific name would do."""
		layer = frappe.get_doc("Custom Sidebar", {"module": self.MODULE, "user": self.USER})
		spacers = [row for row in layer.sidebar_items if row.type == "Spacer"]
		self.assertTrue(spacers)
		self.assertFalse([row for row in spacers if row.added or row.hidden])


class TestAnAppThatMovedItsSidebar(IntegrationTestCase):
	"""polished hrms ships v16's `Expenses` as the sidebar of a new module `Expenses`, while the v16
	row still says `HR`. A row is matched by title first, so it is not built again under `HR`.
	"""

	OLD_MODULE = "Test V16 Old Home Module"
	NEW_MODULE = "Test V16 New Home Module"
	USER = "test-v16-moved@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		with no_developer_mode():
			for module in (cls.OLD_MODULE, cls.NEW_MODULE):
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": module, "app_name": "frappe"}
				).insert()
				clear_computed_base_cache(module)

		frappe.get_doc(
			{"doctype": "User", "email": cls.USER, "first_name": "V16 Moved", "send_welcome_email": 0}
		).insert(ignore_if_duplicate=True).add_roles("Desk User")

		app_sidebar(cls.NEW_MODULE, "V16 Moved", [link("User", "Users")])
		items = [{"type": "Link", "link_type": "DocType", "link_to": "ToDo", "label": "Todos"}]
		archive("V16 Moved", items, module=cls.OLD_MODULE, standard=1)
		archive(f"V16 Moved-{cls.USER}", items, module=cls.OLD_MODULE, for_user=cls.USER)
		run_conversion()

	@classmethod
	def tearDownClass(cls):
		frappe.clear_cache()
		super().tearDownClass()

	def test_the_old_module_gets_no_second_copy(self):
		self.assertFalse(frappe.db.exists("Sidebar", {"module": self.OLD_MODULE}))

	def test_a_fork_follows_the_sidebar_to_its_new_module(self):
		self.assertTrue(frappe.db.exists("Custom Sidebar", {"module": self.NEW_MODULE, "user": self.USER}))
		self.assertFalse(frappe.db.exists("Custom Sidebar", {"module": self.OLD_MODULE, "user": self.USER}))


class TestCustomSidebars(IntegrationTestCase):
	"""A sidebar the site made in v16 becomes a custom module of its own.

	It cannot stay under the module v16 filed it in, since that module has the app's sidebar now
	and answers with it.
	"""

	HOST = "Test V16 Host Module"
	CLASH = "Test V16 Clash Module"
	REUSED = "V16 Reused"
	SHOWROOM = "V16 Showroom"
	FILTERED = "V16 Filtered"
	GATED = "V16 Gated"
	OPEN_ICON = "V16 Open Icon"
	IN_FOLDER = "V16 In Folder"
	IN_APP = "V16 In App"
	GENERATED = "V16 Generated"
	SYSTEM_MANAGER = "test-v16-custom-manager@example.com"
	GATED_ROLE = "Test V16 Gated Role"
	USER = "test-v16-custom@example.com"
	OTHER_USER = "test-v16-custom-other@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		with no_developer_mode():
			for module in (cls.HOST, cls.CLASH):
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": module, "app_name": "frappe"}
				).insert()
				clear_computed_base_cache(module)
			frappe.get_doc({"doctype": "Module Def", "module_name": cls.REUSED, "custom": 1}).insert()

		for user in (cls.USER, cls.OTHER_USER):
			frappe.get_doc(
				{"doctype": "User", "email": user, "first_name": "V16 Custom", "send_welcome_email": 0}
			).insert(ignore_if_duplicate=True).add_roles("Desk User")

		# the app's own sidebar for the module the site filed its sidebars under
		make_sidebar(cls.HOST)

		frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": cls.SHOWROOM,
				"label": cls.SHOWROOM,
				"module": cls.HOST,
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)

		items = [
			{"type": "Link", "link_type": "DocType", "link_to": "ToDo", "label": "Todos"},
			{"type": "Link", "link_type": "DocType", "link_to": "Event", "label": "Events"},
		]
		archive(cls.SHOWROOM, items, module=cls.HOST)
		archive(cls.CLASH, items, module=cls.HOST)
		archive(cls.REUSED, items, module=cls.HOST)
		archive("??", items, module=cls.HOST)
		archive(cls.FILTERED, [*items, link("ToDo", "Open Todos", route_options='{"status": "Open"}')])

		# v16 showed a sidebar to whoever its desktop icon showed to: the icon's roles, and those of
		# the folder it sat in
		frappe.get_doc({"doctype": "Role", "role_name": cls.GATED_ROLE, "desk_access": 1}).insert(
			ignore_if_duplicate=True
		)
		frappe.get_doc("User", cls.USER).add_roles(cls.GATED_ROLE)
		for title in (cls.GATED, cls.OPEN_ICON, cls.IN_FOLDER):
			archive(title, items, module=cls.HOST)
		desktop_icon(cls.GATED, link_to=cls.GATED, roles=[cls.GATED_ROLE])
		# one gated icon and one open one: the open one showed it to everyone
		desktop_icon(f"{cls.OPEN_ICON} Gated", link_to=cls.OPEN_ICON, roles=[cls.GATED_ROLE])
		desktop_icon(cls.OPEN_ICON, link_to=cls.OPEN_ICON)
		desktop_icon("V16 Gated Folder", icon_type="Folder", roles=[cls.GATED_ROLE])
		desktop_icon(cls.IN_FOLDER, link_to=cls.IN_FOLDER, parent_icon="V16 Gated Folder")
		# frappe's app icon is open to System Managers only
		frappe.get_doc(
			{
				"doctype": "User",
				"email": cls.SYSTEM_MANAGER,
				"first_name": "V16 Manager",
				"send_welcome_email": 0,
			}
		).insert(ignore_if_duplicate=True).add_roles("System Manager")
		archive(cls.IN_APP, items, module=cls.HOST)
		desktop_icon("V16 App Parent", icon_type="App", app="frappe")
		desktop_icon(cls.IN_APP, link_to=cls.IN_APP, parent_icon="V16 App Parent")

		# what a conversion that put a site's sidebar into an app module would have left behind
		old_base = frappe.new_doc("Sidebar")
		with no_developer_mode():
			frappe.get_doc(
				{"doctype": "Module Def", "module_name": "Test V16 Old Base Module", "app_name": "frappe"}
			).insert()
		old_base.update(
			{
				"module": "Test V16 Old Base Module",
				"title": "V16 Old Base",
				"merged_from": json.dumps(["V16 Old Base"]),
			}
		)
		old_base.append(
			"items", {"type": "Link", "link_type": "DocType", "link_to": "ToDo", "label": "Todos"}
		)
		with in_patch():
			old_base.insert(ignore_permissions=True)
		archive("V16 Old Base", items, module=cls.HOST)
		archive(f"{cls.SHOWROOM}-{cls.USER}", items[:1], module=cls.HOST, for_user=cls.USER)

		# what v16 built on its own from an app's workspace: neither flag, and no module
		standard_workspace(cls.GENERATED, cls.HOST)
		archive(cls.GENERATED, [home(cls.GENERATED), *items])

		cls.output = run_conversion()

	@classmethod
	def tearDownClass(cls):
		frappe.clear_cache()
		super().tearDownClass()

	def test_each_becomes_a_custom_module(self):
		module = frappe.get_doc("Module Def", self.SHOWROOM)
		self.assertEqual(module.custom, 1)
		self.assertEqual(frappe.db.get_value("Sidebar", {"module": self.SHOWROOM}), self.SHOWROOM)

	def rail_for(self, user: str) -> list[str]:
		from frappe.desk.doctype.dock.dock import resolve_app_dock

		frappe.set_user(user)
		try:
			return [entry["link_to"] for entry in resolve_app_dock("frappe")]
		finally:
			frappe.set_user("Administrator")

	def test_it_is_added_to_its_apps_dock_for_everyone(self):
		from frappe.desk.doctype.dock.dock import get_app_base

		rail = self.rail_for(self.OTHER_USER)
		self.assertIn(self.SHOWROOM, rail)
		# the app's own entries keep their order, ahead of it
		shipped = [link for link in (entry["link_to"] for entry in get_app_base("frappe")) if link in rail]
		self.assertEqual(rail[: len(shipped)], shipped)
		self.assertGreater(rail.index(self.SHOWROOM), len(shipped) - 1)
		self.assertTrue(
			frappe.db.exists("Dock", {"app": "frappe", "user": "", "standard": 0}),
			"the site's own dock layer holds it, not the app's",
		)

	def test_it_is_listed_with_the_app_v16_filed_it_under(self):
		self.assertEqual(frappe.db.get_value("Module Def", self.SHOWROOM, "app_name"), "frappe")

	def test_the_apps_sidebar_is_left_alone(self):
		self.assertEqual(
			[row.link_to for row in frappe.get_doc("Sidebar", {"module": self.HOST}).items], ["User"]
		)

	def test_a_normal_user_sees_its_links(self):
		items = resolve_sidebar(self.SHOWROOM, self.OTHER_USER).items
		self.assertEqual([item["link_to"] for item in items], ["ToDo", "Event"])

	def test_a_title_taken_by_another_module_is_suffixed(self):
		self.assertEqual(frappe.db.get_value("Module Def", f"{self.CLASH} (Custom)", "custom"), 1)
		self.assertEqual(frappe.get_all("Sidebar", filters={"module": self.CLASH}), [])

	def test_a_base_in_an_app_module_is_not_mistaken_for_its_custom_module(self):
		# the old base still answers to the title's URL, so the module takes the suffix
		self.assertEqual(frappe.db.get_value("Module Def", "V16 Old Base (Custom)", "custom"), 1)

	def test_a_row_v16_generated_from_an_apps_workspace_is_the_apps(self):
		"""It names the app's workspace and opens on it, so it is the app's content, and it is the
		workspace that says which module, not the links after it: the host keeps its own sidebar,
		and no module is made for the row."""
		self.assertFalse(frappe.db.exists("Module Def", self.GENERATED))
		self.assertFalse(frappe.db.exists("Module Def", f"{self.GENERATED} (Custom)"))
		self.assertFalse(frappe.db.exists("Sidebar", {"merged_from": json.dumps([self.GENERATED])}))

	def test_a_title_with_nothing_routable_still_gets_a_module(self):
		self.assertEqual(frappe.db.get_value("Module Def", "Custom Sidebar", "custom"), 1)
		self.assertTrue(frappe.db.exists("Sidebar", {"module": "Custom Sidebar"}))

	def test_a_link_with_route_options_is_a_link_of_its_own(self):
		"""v16's `route_options` are filters, and filters are part of what an item is, so a filtered
		copy of a link stays beside it rather than being merged into it."""
		todos = [
			row for row in frappe.get_doc("Sidebar", {"module": self.FILTERED}).items if row.link_to == "ToDo"
		]
		self.assertEqual([row.label for row in todos], ["Todos", "Open Todos"])
		self.assertEqual(json.loads(todos[1].filters), [["ToDo", "status", "=", "Open"]])

	def test_it_is_blocked_for_users_v16_did_not_show_it_to(self):
		def blocked(user):
			return frappe.get_doc("User", user).get_blocked_modules()

		for module in (self.GATED, self.IN_FOLDER):
			self.assertIn(module, blocked(self.OTHER_USER))
			self.assertNotIn(module, blocked(self.USER))
			self.assertNotIn(module, blocked("Administrator"))
		# under an app icon, shown to whoever the app lets in
		self.assertIn(self.IN_APP, blocked(self.OTHER_USER))
		self.assertNotIn(self.IN_APP, blocked(self.SYSTEM_MANAGER))
		# shown to everyone: by an open icon beside a gated one, or by having no icon at all
		self.assertNotIn(self.OPEN_ICON, blocked(self.OTHER_USER))
		self.assertNotIn(self.SHOWROOM, blocked(self.OTHER_USER))

		self.assertNotIn(self.GATED, self.rail_for(self.OTHER_USER))
		self.assertIn(self.GATED, self.rail_for(self.USER))

	def test_running_it_again_blocks_and_docks_nothing_twice(self):
		run_conversion()
		self.assertEqual(
			frappe.db.count("Block Module", {"parent": self.OTHER_USER, "module": self.GATED}), 1
		)
		self.assertEqual(self.rail_for(self.USER).count(self.GATED), 1)

	def test_a_custom_module_without_a_sidebar_is_reused(self):
		self.assertTrue(frappe.db.exists("Sidebar", {"module": self.REUSED}))
		self.assertFalse(frappe.db.exists("Module Def", f"{self.REUSED} (Custom)"))

	def test_its_workspace_moves_with_it(self):
		"""So the desktop icon linking to that workspace opens this sidebar, not the host's."""
		from frappe.desk.doctype.desktop_icon.desktop_icon import get_linked_workspace_modules

		self.assertEqual(frappe.db.get_value("Workspace", self.SHOWROOM, "module"), self.SHOWROOM)
		icon = frappe._dict(name="icon", icon_type="Link", link_to=self.SHOWROOM)
		self.assertEqual(get_linked_workspace_modules([icon]), {"icon": self.SHOWROOM})

	def test_a_fork_of_it_is_laid_over_it(self):
		self.assertTrue(frappe.db.exists("Custom Sidebar", {"module": self.SHOWROOM, "user": self.USER}))
		self.assertFalse(frappe.db.exists("Custom Sidebar", {"module": self.HOST, "user": self.USER}))

		items = resolve_sidebar(self.SHOWROOM, self.USER).items
		self.assertEqual([item["link_to"] for item in items], ["ToDo"])

	def test_running_it_again_changes_nothing(self):
		before = frappe.db.count("Module Def"), frappe.db.count("Sidebar"), frappe.db.count("Custom Sidebar")
		run_conversion()
		after = frappe.db.count("Module Def"), frappe.db.count("Sidebar"), frappe.db.count("Custom Sidebar")
		self.assertEqual(before, after)


class TestV16GeneratedSidebarCleanup(IntegrationTestCase):
	"""A site that ran the earlier conversion holds a custom module per sidebar v16 generated from
	an app's workspace, beside the app's own module. The cleanup takes them out again."""

	HELD = "Test V16 Held Module"
	BARE = "Test V16 Bare Module"
	HELD_ROW = "V16 Held Generated"
	BARE_ROW = "V16 Bare Generated"
	KEPT_ROW = "V16 Kept Generated"
	HOMED_ROW = "V16 Homed Generated"
	USER = "test-v16-cleanup@example.com"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")

		with no_developer_mode():
			for module in (cls.HELD, cls.BARE):
				frappe.get_doc(
					{"doctype": "Module Def", "module_name": module, "app_name": "frappe"}
				).insert()
				clear_computed_base_cache(module)
		# one module the app ships a sidebar for, one it does not
		make_sidebar(cls.HELD)

		frappe.get_doc(
			{"doctype": "User", "email": cls.USER, "first_name": "V16 Cleanup", "send_welcome_email": 0}
		).insert(ignore_if_duplicate=True).add_roles("Desk User")

		rows = (
			(cls.HELD_ROW, cls.HELD),
			(cls.BARE_ROW, cls.BARE),
			(cls.KEPT_ROW, cls.HELD),
			(cls.HOMED_ROW, cls.HELD),
		)
		for title, module in rows:
			standard_workspace(title, module)
			archive(title, [home(title), link("ToDo", "Todos")], module=module)
			cls.wrongly_converted(title)

		# the user arranged the sidebar where the earlier run put it
		write_user_layer(
			f"{cls.HELD_ROW} (Custom)", cls.USER, layer_rows([link("Event", "Events")], below=[])
		)
		# the site has since filed a report under one of them
		frappe.get_doc(
			{
				"doctype": "Report",
				"report_name": "V16 Kept Report",
				"ref_doctype": "ToDo",
				"report_type": "Report Builder",
				"module": f"{cls.KEPT_ROW} (Custom)",
				"is_standard": "No",
			}
		).insert()
		# and made a workspace under another, which no delete would refuse on behalf of
		frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": "V16 Homed Page",
				"label": "V16 Homed Page",
				"module": f"{cls.HOMED_ROW} (Custom)",
				"public": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Dock",
				"app": "frappe",
				"user": "",
				"items": [
					{"link_type": "Sidebar", "link_to": f"{cls.HELD_ROW} (Custom)", "title": cls.HELD_ROW}
				],
			}
		).insert(ignore_permissions=True)

		cls.output = []
		with (
			in_patch(),
			patch("click.secho", side_effect=lambda message="", **kwargs: cls.output.append(message)),
		):
			frappe.get_attr(CONVERSION[-1] + ".execute")()

	@classmethod
	def wrongly_converted(cls, title: str) -> None:
		"""What `convert_custom_sidebars` made of the row before it told a generated row apart from
		a site's own: a custom module, its sidebar, and a block for the user v16 did not show it
		to."""
		module = f"{title} (Custom)"
		with no_developer_mode():
			frappe.get_doc(
				{"doctype": "Module Def", "module_name": module, "custom": 1, "app_name": "frappe"}
			).insert()
		sidebar = frappe.new_doc("Sidebar")
		sidebar.update({"module": module, "title": module, "merged_from": json.dumps([title])})
		sidebar.append("items", link("ToDo", "Todos"))
		with in_patch():
			sidebar.insert(ignore_permissions=True)
		user = frappe.get_doc("User", cls.USER)
		user.append("block_modules", {"module": module})
		user.save(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		frappe.clear_cache()
		super().tearDownClass()

	def test_the_extra_module_goes(self):
		"""With its sidebar and the page `Module Def.after_insert` made for it."""
		for title in (self.HELD_ROW, self.BARE_ROW):
			self.assertFalse(frappe.db.exists("Module Def", f"{title} (Custom)"))
			self.assertFalse(frappe.db.exists("Sidebar", {"module": f"{title} (Custom)"}))
			self.assertFalse(frappe.db.exists("Workspace", f"{title} (Custom)"))

	def test_the_apps_sidebar_is_left_alone(self):
		self.assertEqual(
			[row.link_to for row in frappe.get_doc("Sidebar", {"module": self.HELD}).items], ["User"]
		)

	def test_a_module_without_a_sidebar_takes_the_row(self):
		self.assertEqual(frappe.db.get_value("Sidebar", {"module": self.BARE}), self.BARE_ROW)
		items = resolve_sidebar(self.BARE_ROW, self.USER).items
		self.assertEqual([item["link_to"] for item in items if item["link_type"] == "DocType"], ["ToDo"])

	def test_its_dock_entry_and_blocks_go(self):
		self.assertFalse(
			frappe.db.exists("Dock Item", {"link_type": "Sidebar", "link_to": f"{self.HELD_ROW} (Custom)"})
		)
		self.assertNotIn(f"{self.HELD_ROW} (Custom)", frappe.get_doc("User", self.USER).get_blocked_modules())

	def test_a_users_arrangement_moves_to_the_apps_module(self):
		self.assertTrue(frappe.db.exists("Custom Sidebar", {"module": self.HELD, "user": self.USER}))
		self.assertFalse(frappe.db.exists("Custom Sidebar", {"module": f"{self.HELD_ROW} (Custom)"}))
		items = resolve_sidebar(self.HELD, self.USER).items
		self.assertIn("Event", [item["link_to"] for item in items])

	def test_a_module_holding_other_documents_is_kept(self):
		module = f"{self.KEPT_ROW} (Custom)"
		self.assertTrue(frappe.db.exists("Module Def", module))
		self.assertTrue(frappe.db.exists("Sidebar", {"module": module}))
		self.assertIn(module, frappe.get_doc("User", self.USER).get_blocked_modules())
		self.assertIn(f"Module '{module}': kept, Report V16 Kept Report is filed under it", self.output)

	def test_a_module_holding_a_workspace_is_kept(self):
		module = f"{self.HOMED_ROW} (Custom)"
		self.assertTrue(frappe.db.exists("Module Def", module))
		self.assertIn(f"Module '{module}': kept, Workspace V16 Homed Page is filed under it", self.output)


def standard_workspace(title: str, module: str):
	"""An app's workspace, as its import leaves it on a site."""
	with no_developer_mode():
		return frappe.get_doc(
			{
				"doctype": "Workspace",
				"title": title,
				"label": title,
				"module": module,
				"public": 1,
				"standard": 1,
				"content": "[]",
			}
		).insert(ignore_permissions=True)


def home(workspace: str) -> dict:
	"""The link v16 put first on every sidebar it generated from a workspace."""
	return {"type": "Link", "link_type": "Workspace", "link_to": workspace, "label": "Home"}


def app_sidebar(module: str, title: str, items: list[dict]):
	"""A `Sidebar` as an app's file leaves it on a site: standard, and titled as the app titles it."""
	doc = frappe.new_doc("Sidebar")
	doc.module = module
	doc.title = title
	for item in items:
		doc.append("items", item)
	with in_patch():
		doc.insert(ignore_permissions=True)
	frappe.db.set_value("Sidebar", doc.name, "standard", 1, update_modified=False)
	return doc


def desktop_icon(label: str, roles: list[str] | None = None, icon_type: str = "Link", **fields):
	"""A v16 desktop icon, opening the sidebar named in `link_to`."""
	icon = frappe.get_doc(
		{
			"doctype": "Desktop Icon",
			"label": label,
			"icon_type": icon_type,
			"link_type": "Workspace Sidebar" if icon_type == "Link" else None,
			"roles": [{"role": role} for role in roles or []],
			**fields,
		}
	)
	icon.flags.in_patch = True
	return icon.insert(ignore_permissions=True, ignore_links=True)


def link(doctype: str, label: str, **extra) -> dict:
	return {"type": "Link", "link_type": "DocType", "link_to": doctype, "label": label, **extra}
