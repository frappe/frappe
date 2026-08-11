# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

"""D17 -- an app author gets a command and a notice.

App-shipped `<app>/workspace_sidebar/*.json` stops being imported. Nothing breaks -- the module
falls back to a computed base -- but for the apps that curated their navigation that fallback
is the whole of it reverting, so there is a command to convert with and a one-time notice
saying the command exists.
"""

import json
import os
import shutil
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.desk.doctype.module_sidebar.convert_fixtures import (
	OLD_FIXTURE_FOLDER,
	apps_with_old_fixtures,
	convert_app,
	export_path,
)
from frappe.desk.doctype.module_sidebar.test_module_sidebar import (
	module_resolvable_on_disk,
	no_developer_mode,
)
from frappe.modules.utils import get_app_level_directory_path
from frappe.tests import IntegrationTestCase

MODULE = "Test Fixture Conversion Module"


@contextmanager
def old_fixtures(fixtures: dict[str, dict], app: str = "frappe"):
	"""An app shipping the old folder, for the length of the test.

	Written to disk rather than mocked: the whole question is what is in that folder and what
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
			path = export_path(MODULE)
			self.assertTrue(os.path.exists(path), f"nothing written to {path}")

			written = json.loads(open(path).read())
			self.assertEqual(written["doctype"], "Module Sidebar")
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
			import_file_by_path(export_path(MODULE), force=True, ignore_version=True)

		doc = frappe.get_doc("Module Sidebar", MODULE)
		self.assertEqual([item.link_to for item in doc.items], ["User"])
		self.assertEqual(doc.standard, 1)

	def test_it_never_overwrites_a_file_that_is_already_there(self):
		"""Idempotent, and safe against an app half-way through converting by hand -- which is
		the state erpnext is actually in."""
		fixtures = {"only": fixture("Conversion Only", MODULE, [link("User")])}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			convert_app("frappe")
			before = open(export_path(MODULE)).read()

			results = convert_app("frappe")

			self.assertIn("already converted", [r["state"] for r in results if r["module"] == MODULE])
			self.assertEqual(before, open(export_path(MODULE)).read())

	def test_a_dry_run_writes_nothing(self):
		fixtures = {"only": fixture("Conversion Only", MODULE, [link("User")])}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			results = convert_app("frappe", dry_run=True)

			self.assertIn("converted", [r["state"] for r in results if r["module"] == MODULE])
			self.assertFalse(os.path.exists(export_path(MODULE)))

	def test_a_personal_fork_in_an_app_folder_is_not_shipped(self):
		"""A `for_user` sidebar that got exported by accident is somebody's own arrangement,
		and an app has no business shipping one."""
		fixtures = {
			"mine": fixture("Conversion Mine", MODULE, [link("User")], for_user="someone@example.com")
		}

		with module_resolvable_on_disk(MODULE), old_fixtures(fixtures):
			results = convert_app("frappe")

			self.assertEqual([r for r in results if r["module"] == MODULE], [])
			self.assertFalse(os.path.exists(export_path(MODULE)))


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
			"frappe.desk.doctype.module_sidebar.convert_fixtures.apps_with_old_fixtures",
			return_value={},
		):
			self.assertEqual(self.run_patch(), [])

	def test_it_runs_once_rather_than_on_every_migrate(self):
		"""A one-time fact belongs at the upgrade boundary. A line printed on every migrate for
		the rest of the release is a nag, which is why this is a patch and not console output
		from the conversion."""
		from frappe.modules.patch_handler import PatchType, get_patches_from_app

		patches = [p.split(maxsplit=1)[0] for p in get_patches_from_app("frappe", PatchType.post_model_sync)]
		notice = "frappe.patches.v16_0.notify_apps_to_convert_sidebar_fixtures"

		self.assertIn(notice, patches)
		self.assertEqual(patches.count(notice), 1)
		# and it has no re-run marker, which is what would make it run again
		lines = get_patches_from_app("frappe", PatchType.post_model_sync)
		self.assertNotIn("re-run-patch", next(p for p in lines if p.startswith(notice)))
