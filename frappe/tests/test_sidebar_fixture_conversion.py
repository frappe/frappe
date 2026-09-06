# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""D17: an app author gets a command and a notice.

App-shipped `<app>/workspace_sidebar/*.json` stops being imported. Nothing breaks, because the
module falls back to a computed base, but for apps that curated their navigation that fallback
undoes all of it, so there is a command to convert with and a one-time notice saying the command
exists.

"""

import json
import os
import shutil
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.doctype.sidebar.convert_fixtures import (
	OLD_FIXTURE_FOLDER,
	apps_with_old_fixtures,
	convert_app,
	export_path,
)
from frappe.desk.doctype.sidebar.sidebar import build_sidebar, item_key, pick_primary
from frappe.desk.doctype.sidebar.test_sidebar import (
	module_resolvable_on_disk,
	no_developer_mode,
)
from frappe.modules.utils import get_app_level_directory_path
from frappe.tests import IntegrationTestCase

MODULE = "Test Fixture Conversion Module"


@contextmanager
def old_fixtures(fixtures: dict[str, dict], app: str = "frappe"):
	"""An app shipping the old folder, for the length of the test.

	It is written to disk rather than mocked, because the question is what is in that folder and what
	gets written beside it.

	"""
	folder = get_app_level_directory_path(OLD_FIXTURE_FOLDER, app)
	created = not os.path.exists(folder)
	os.makedirs(folder, exist_ok=True)

	written = []
	for name, fixture in fixtures.items():
		path = os.path.join(folder, f"{name}.json")
		with open(path, "w") as f:
			f.write(json.dumps(fixture, indent=1) + "\n")
		written.append(path)

	try:
		yield folder
	finally:
		if created:
			shutil.rmtree(folder, ignore_errors=True)
		else:
			for path in written:
				os.path.exists(path) and os.remove(path)


def fixture(title, module, items, **extra):
	return {
		"doctype": "Workspace Sidebar",
		"name": title,
		"title": title,
		"module": module,
		"header_icon": "hammer",
		"standard": 1,
		"items": items,
		**extra,
	}


def link(doctype):
	return {"type": "Link", "link_type": "DocType", "link_to": doctype, "label": doctype}


class TestSidebarFixtureConversion(IntegrationTestCase):
	def setUp(self):
		with no_developer_mode():
			frappe.get_doc({"doctype": "Module Def", "module_name": MODULE, "app_name": "frappe"}).insert(
				ignore_if_duplicate=True
			)

	def tearDown(self):
		with no_developer_mode():
			frappe.delete_doc("Module Def", MODULE, force=True, ignore_missing=True)

	def test_it_writes_one_export_per_module_where_migrate_will_find_it(self):
		fixtures = {
			"primary": fixture("Conversion Primary", MODULE, [link("User"), link("Role")]),
			"secondary": fixture("Conversion Secondary", MODULE, [link("DocType")]),
		}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			results = convert_app("frappe")
			mine = [r for r in results if r["module"] == MODULE]

			self.assertEqual([r["state"] for r in mine], ["converted"])
			# A merge is titled after the module, since four sidebars in one are not any one of
			# them, and a sidebar is named by its title, so the path is the module's here.
			path = export_path(MODULE, MODULE)
			self.assertTrue(os.path.exists(path), f"nothing written to {path}")

			written = json.loads(open(path).read())
			self.assertEqual(written["doctype"], "Sidebar")
			self.assertEqual(written["name"], MODULE)
			self.assertEqual(written["standard"], 1)
			# both fixtures' content survives; the second becomes a collapsed section
			links = [item.get("link_to") for item in written["items"]]
			for expected in ("User", "Role", "DocType"):
				self.assertIn(expected, links)

	def test_what_it_writes_imports_back(self):
		"""The point of the command: `bench migrate` reads the file it produced."""
		from frappe.modules.import_file import import_file_by_path

		fixtures = {"only": fixture("Conversion Only", MODULE, [link("User")])}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			convert_app("frappe")
			import_file_by_path(export_path(MODULE, "Conversion Only"), force=True, ignore_version=True)

		doc = frappe.get_doc("Sidebar", "Conversion Only")
		self.assertEqual(doc.module, MODULE)
		self.assertEqual([item.link_to for item in doc.items], ["User"])
		self.assertEqual(doc.standard, 1)

	def test_a_single_source_is_written_under_the_title_it_keeps(self):
		"""A module with one source keeps that workspace's title, so `Loan Management` still reads
		"Lending". A sidebar is named by its title, so that is what the record and the file are called.
		The module column still says whose it is.
		"""
		fixtures = {"only": fixture("Conversion Only", MODULE, [link("User")])}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			convert_app("frappe")

			written = json.loads(open(export_path(MODULE, "Conversion Only")).read())
			self.assertEqual(written["name"], "Conversion Only")
			self.assertEqual(written["title"], "Conversion Only")
			self.assertEqual(written["module"], MODULE)

	def test_it_never_overwrites_a_file_that_is_already_there(self):
		"""Idempotent, and safe against an app half-way through converting by hand, which is the state
		erpnext is in.
		"""
		fixtures = {"only": fixture("Conversion Only", MODULE, [link("User")])}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			convert_app("frappe")
			before = open(export_path(MODULE, "Conversion Only")).read()

			results = convert_app("frappe")

			self.assertIn("already converted", [r["state"] for r in results if r["module"] == MODULE])
			self.assertEqual(before, open(export_path(MODULE, "Conversion Only")).read())

	def test_a_dry_run_writes_nothing(self):
		fixtures = {"only": fixture("Conversion Only", MODULE, [link("User")])}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			results = convert_app("frappe", dry_run=True)

			self.assertIn("converted", [r["state"] for r in results if r["module"] == MODULE])
			self.assertFalse(os.path.exists(export_path(MODULE, "Conversion Only")))

	def test_a_personal_fork_in_an_app_folder_is_not_shipped(self):
		"""A `for_user` sidebar exported by accident is a user's own arrangement, and an app should not
		ship one.
		"""
		fixtures = {
			"mine": fixture("Conversion Mine", MODULE, [link("User")], for_user="someone@example.com")
		}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			results = convert_app("frappe")

			self.assertEqual([r for r in results if r["module"] == MODULE], [])
			self.assertFalse(os.path.exists(export_path(MODULE, "Conversion Mine")))


class TestTheMerge(IntegrationTestCase):
	"""One module, several of the app's old files, and one sidebar out the other end.

	The merge is reached only from here now: a module that shipped four workspace fixtures still
	ships one sidebar. Its sources are read off disk rather than out of a table, so these build them
	the way `read_fixtures` hands them over.

	"""

	def source(self, title, items, **extra):
		"""A fixture in the shape `convert_app` passes down. See `read_fixtures`."""
		return frappe._dict(
			{
				"name": title,
				"title": title,
				"icon": "hammer",
				"module": MODULE,
				"rows": [frappe._dict(item) for item in items],
				"sequence_id": 0,
				"creation": title,
				**extra,
			}
		)

	def labelled(self, doctype, label):
		return {**link(doctype), "label": label}

	def test_largest_sidebar_becomes_primary(self):
		"""`sequence_id` is nearly uniform on a real site, so as the primary signal it picks
		arbitrarily: it gives Accounts to Invoicing(28) over Accounting(49).
		"""
		sources = [
			self.source("Merge Small", [link("User")]),
			self.source("Merge Large", [link("Role"), link("DocType")]),
		]

		self.assertEqual(pick_primary(MODULE, sources).name, "Merge Large")

	def test_secondary_becomes_collapsed_section(self):
		plan = build_sidebar(
			MODULE,
			[
				self.source("Merge Primary", [link("User"), link("Role")]),
				self.source("Merge Second", [link("DocType")]),
			],
		)
		sections = [i for i in plan["items"] if i["type"] == "Section Break"]

		self.assertEqual(len(sections), 1)
		self.assertEqual(sections[0]["label"], "Merge Second")
		self.assertEqual(sections[0]["keep_closed"], 1)
		# the secondary's own items follow it, nested under it
		after = plan["items"][plan["items"].index(sections[0]) + 1 :]
		self.assertTrue(after, "the secondary contributed no items")
		self.assertTrue(all(i["child"] == 1 for i in after if i["type"] == "Link"))

	def test_merged_title_is_the_module_name(self):
		"""The union of several sidebars is not any one source's title."""
		plan = build_sidebar(
			MODULE,
			[
				self.source("Merge Primary", [link("User"), link("Role")]),
				self.source("Merge Second", [link("DocType")]),
			],
		)

		self.assertEqual(plan["title"], MODULE)

	def test_unmerged_title_keeps_the_fixture_label(self):
		"""A module with one fixture must look exactly as it does today, so `Loan Management` still
		reads "Lending".
		"""
		plan = build_sidebar(MODULE, [self.source("Merge Only", [link("User")])])

		self.assertEqual(plan["title"], "Merge Only")

	def test_duplicate_rows_are_dropped(self):
		"""The tables carry rows boot dedupes away, and copying them straight across would show copies
		the desk does not. erpnext.site has 160 such rows, 72 in Core alone.
		"""
		plan = build_sidebar(MODULE, [self.source("Merge Dupes", [link("User"), link("User"), link("Role")])])

		self.assertEqual(len([i for i in plan["items"] if i["link_to"] == "User"]), 1)

	def test_differently_labelled_duplicates_are_one_item(self):
		"""A relabelled duplicate used to survive the merge, because the dedupe key included `label`.
		Identity does not: two rows pointing at one target are one item, whatever the two files called
		it. erpnext's CRM lists Lead twice.

		Keeping the second is now impossible rather than merely undesirable: it would share an identity
		with the first, so no customization could name one without naming the other, and the resolution
		drops it on the way to the payload anyway. The first wins, which is the label the desk was
		already showing at that position.

		"""
		plan = build_sidebar(
			MODULE,
			[
				self.source(
					"Merge Deliberate",
					[self.labelled("User", "All Users"), self.labelled("User", "Active Users")],
				)
			],
		)

		users = [i for i in plan["items"] if i["link_to"] == "User"]
		self.assertEqual([i["label"] for i in users], ["All Users"])

	def test_merging_does_not_re_key_items(self):
		"""A delta made against a source's item still names it after the merge: the merge copies the
		columns the identity is made of and derives nothing.
		"""
		sources = [self.source("Merge Keyed", [link("User"), {"type": "Section Break", "label": "More"}])]
		plan = build_sidebar(MODULE, sources)

		self.assertEqual(
			[item_key(row) for row in sources[0].rows],
			[item_key(row) for row in plan["items"]],
		)

	def test_claim_flag_is_not_carried(self):
		"""The conversion drops the claim rather than mapping it to `is_default_module`.

		A claim is an app's opinion and the app has to be able to retract it, which it can by flagging
		the row in the `sidebar` fixture it ships from here on.

		"""
		item = {**link("User"), "default_workspace": 1}
		plan = build_sidebar(MODULE, [self.source("Merge Default", [item])])

		self.assertFalse(plan["items"][0].get("is_default_module"))
		self.assertNotIn("default_workspace", plan["items"][0])

	def test_the_sources_are_recorded(self):
		"""`merged_from` names every file that went into the export, so an author reading the converted
		JSON can see which of their old fixtures produced it.
		"""
		plan = build_sidebar(
			MODULE,
			[
				self.source("Merge Primary", [link("User"), link("Role")]),
				self.source("Merge Second", [link("DocType")]),
			],
		)

		self.assertEqual(sorted(json.loads(plan["merged_from"])), ["Merge Primary", "Merge Second"])


class TestAnAppThatHasNotFollowedTheRename(IntegrationTestCase):
	"""`Module Sidebar` is `Sidebar`, and an app's fixtures moved with it, but only frappe's.

	hrms and erpnext convert on their own branches, so in between they ship
	`<module>/module_sidebar/` naming a doctype this site no longer has. That has to be ignored: a
	migrate that tried to import one would fail on every site holding a stale app, which is far worse
	than the module falling back to a computed base.

	"""

	def test_the_old_folder_is_not_walked(self):
		import shutil

		from frappe.model.sync import get_doc_files

		with module_resolvable_on_disk(MODULE) as module_path:
			stale = os.path.join(module_path, "module_sidebar", "stale")
			os.makedirs(stale)
			with open(os.path.join(stale, "stale.json"), "w") as f:
				f.write(json.dumps({"doctype": "Module Sidebar", "name": "stale", "module": MODULE}))

			try:
				self.assertEqual(
					[path for path in get_doc_files(files=[], start_path=module_path) if "stale" in path],
					[],
				)
			finally:
				shutil.rmtree(os.path.join(module_path, "module_sidebar"), ignore_errors=True)

	def test_the_new_folder_is(self):
		"""The other half of the same fact: the walk found nothing above because it looks in `sidebar/`
		now, not because it stopped looking.
		"""
		import shutil

		from frappe.model.sync import get_doc_files

		with module_resolvable_on_disk(MODULE) as module_path:
			fresh = os.path.join(module_path, "sidebar", "fresh")
			os.makedirs(fresh)
			path = os.path.join(fresh, "fresh.json")
			with open(path, "w") as f:
				f.write(json.dumps({"doctype": "Sidebar", "name": "fresh", "module": MODULE}))

			try:
				self.assertIn(path, get_doc_files(files=[], start_path=module_path))
			finally:
				shutil.rmtree(os.path.join(module_path, "sidebar"), ignore_errors=True)


class TestTheNotice(IntegrationTestCase):
	"""It names the apps that actually still hold a folder, and says nothing when none do."""

	def run_patch(self) -> list[str]:
		lines = []
		with patch("click.secho", side_effect=lambda message="", **kwargs: lines.append(message)):
			frappe.get_attr("frappe.patches.v16_0.notify_apps_to_convert_sidebar_fixtures.execute")()
		return lines

	def test_it_names_the_app_and_the_command(self):
		fixtures = {"only": fixture("Notice Only", "Core", [link("User")])}

		with old_fixtures(fixtures):
			self.assertEqual(apps_with_old_fixtures().get("frappe"), 1)
			lines = " ".join(self.run_patch())

		self.assertIn("frappe", lines)
		self.assertIn("workspace_sidebar", lines)
		self.assertIn("convert-sidebar-fixtures", lines)

	def test_it_says_nothing_when_every_app_has_converted(self):
		with patch(
			"frappe.desk.doctype.sidebar.convert_fixtures.apps_with_old_fixtures",
			return_value={},
		):
			self.assertEqual(self.run_patch(), [])

	def test_it_runs_once_rather_than_on_every_migrate(self):
		"""A one-time fact belongs at the upgrade boundary. A line printed on every migrate for the
		rest of the release is a nag, which is why this is a patch rather than console output from the
		conversion.
		"""
		from frappe.modules.patch_handler import PatchType, get_patches_from_app

		patches = [p.split(maxsplit=1)[0] for p in get_patches_from_app("frappe", PatchType.post_model_sync)]
		notice = "frappe.patches.v16_0.notify_apps_to_convert_sidebar_fixtures"

		self.assertIn(notice, patches)
		self.assertEqual(patches.count(notice), 1)
		# and it has no re-run marker, which is what would make it run again
		lines = get_patches_from_app("frappe", PatchType.post_model_sync)
		self.assertNotIn("re-run-patch", next(p for p in lines if p.startswith(notice)))
