# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
import os
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from babel.util import pathmatch

import frappe
from frappe.desk.doctype.default_view import api as default_view_api
from frappe.desk.doctype.default_view.resolver import DefaultViews
from frappe.desk.doctype.doctype_view import app_views as app_views_module
from frappe.desk.doctype.doctype_view.api import find
from frappe.desk.doctype.doctype_view.app_views import ViewIndex, app_defaults, app_view_settings, app_views
from frappe.desk.doctype.doctype_view.doctype_view import SITE_ROW, DuplicateViewError
from frappe.desk.doctype.doctype_view.key_space import KeySpace
from frappe.desk.doctype.favourite.favourite import toggle_favourite
from frappe.gettext.extractors.app_view import extract
from frappe.patches.v17_0 import fill_view_key_slots
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user

APPS = ("frappe", "acme", "zeta")
CURRENT_INDEX = app_views_module.current_index
LIST_SETTINGS = {"sort": [{"fieldname": "date", "direction": "asc"}]}


class AppFolders:
	"""Three apps' module folders in a temp dir: frappe owns `ToDo`, the others reach it through `custom/`."""

	def __init__(self, root: str):
		self.root = root
		self.write(self.doctype_folder("frappe", "todo.json"), {"name": "ToDo"})

	def module_paths(self, apps):
		return [(app, os.path.join(self.root, app)) for app in apps]

	def doctype_folder(self, app: str, *parts: str) -> str:
		return os.path.join(self.root, app, "doctype", "todo", *parts)

	def own_view(self, key: str, **file) -> str:
		return self.write(self.doctype_folder("frappe", "frontend", "views", f"{key}.json"), a_file(**file))

	def custom_view(self, app: str, key: str, doctype: str = "todo", **file) -> str:
		return self.write(
			os.path.join(self.root, app, "custom", doctype, "views", f"{key}.json"), a_file(**file)
		)

	def write(self, path: str, data) -> str:
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w") as f:
			f.write(data if isinstance(data, str) else frappe.as_json(data) + "\n")
		return path


def a_file(label="Probe", type="List", settings=None, **extra) -> dict:
	return {
		"label": label,
		"type": type,
		"settings": LIST_SETTINGS if settings is None else settings,
		**extra,
	}


class AppViewCase(IntegrationTestCase):
	def setUp(self):
		root = tempfile.mkdtemp(prefix="test_app_views_45985_")
		self.addCleanup(shutil.rmtree, root)
		self.folders = AppFolders(root)
		self.enterContext(
			patch.object(app_views_module, "module_paths", side_effect=self.folders.module_paths)
		)
		self.enterContext(patch.object(app_views_module, "current_index", side_effect=self.index))

	def tearDown(self):
		frappe.db.rollback()

	def index(self) -> ViewIndex:
		return ViewIndex(APPS)


class TestTheIndex(AppViewCase):
	def test_a_doctype_folder_file_is_its_own_apps_view(self):
		self.folders.own_view("probe-open", label="Open probe")
		view = app_views("ToDo")["probe-open"]
		self.assertEqual(
			(view.app, view.doctype, view.label, view.type), ("frappe", "ToDo", "Open probe", "List")
		)
		self.assertEqual(app_view_settings("ToDo", "probe-open"), LIST_SETTINGS)

	def test_an_app_ships_a_view_of_another_apps_doctype(self):
		self.folders.custom_view("acme", "probe-acme")
		self.assertEqual(app_views("ToDo")["probe-acme"].app, "acme")

	def test_the_own_app_wins_a_clash_else_the_first_in_app_order(self):
		self.folders.custom_view("zeta", "probe-own", label="Zeta's")
		self.folders.own_view("probe-own", label="Frappe's")
		self.folders.custom_view("zeta", "probe-order", label="Zeta's")
		self.folders.custom_view("acme", "probe-order", label="Acme's")

		with self.assertLogs(frappe.logger("desk"), "WARNING") as logged:
			views = app_views("ToDo")
		self.assertEqual(views["probe-own"].label, "Frappe's")
		self.assertEqual(views["probe-order"].label, "Acme's")
		self.assertEqual(sum("ships in" in line for line in logged.output), 2)

	def test_a_bad_file_is_refused(self):
		bad = {
			"probe-unknown-type": a_file(type="Gantt"),
			"probe-no-label": a_file(label=""),
			"probe-list-settings": a_file(settings=[]),
			"probe-too-big": a_file(settings={"columns": "x" * 17 * 1024}),
			"probe-icon": a_file(icon="star"),
			"probe-default-word": a_file(default="yes"),
			"list": a_file(),
			"Probe_Caps": a_file(),
		}
		for key, file in bad.items():
			self.folders.own_view(key, **file)
		self.folders.write(self.folders.doctype_folder("frappe", "frontend", "views", "probe-json.json"), "{")

		index = self.index()
		self.assertEqual(index.views, {})
		self.assertEqual(len(index.refused), len(bad) + 1)

	def test_a_second_default_of_one_app_is_refused(self):
		self.folders.own_view("probe-a", default=True)
		self.folders.own_view("probe-b", default=True)
		index = self.index()
		self.assertEqual([view.key for _doctype, view in index.defaults_in(None)], ["probe-a"])
		self.assertEqual(len(index.refused), 1)

	def test_developer_mode_rebuilds_when_a_views_folder_changes(self):
		self.use_the_real_index()
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 1}))
		self.assertEqual(self.fresh_views(), {})

		path = self.folders.own_view("probe-new", label="New")
		self.assertEqual(self.fresh_views()["probe-new"].label, "New")

		self.folders.own_view("probe-new", label="Renamed in a longer label")
		self.assertEqual(self.fresh_views()["probe-new"].label, "Renamed in a longer label")

		os.remove(path)
		self.assertEqual(self.fresh_views(), {})

	def test_outside_developer_mode_the_index_is_built_once(self):
		self.use_the_real_index()
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 0}))
		self.folders.own_view("probe-first")
		self.assertEqual(list(self.fresh_views()), ["probe-first"])

		self.folders.own_view("probe-later")
		self.assertEqual(list(self.fresh_views()), ["probe-first"])

	def use_the_real_index(self):
		self.enterContext(patch.object(app_views_module, "current_index", CURRENT_INDEX))
		self.enterContext(patch("frappe.get_active_apps", return_value=list(APPS)))
		for cache in (app_views_module.deployed_index, app_views_module.developer_index):
			cache.cache_clear()
			self.addCleanup(cache.cache_clear)
		self.addCleanup(frappe.local.request_cache.clear)

	def fresh_views(self) -> dict:
		frappe.local.request_cache.clear()
		return app_views("ToDo")


class TestTheKeySpace(AppViewCase):
	def test_find_reads_own_then_site_then_app(self):
		person_row("Probe Open")  # made before an app release shipped the same key
		self.folders.own_view("probe-open", label="Open probe")
		self.assertEqual(
			find("ToDo", "probe-open"), {"key": "probe-open", "label": "Probe Open", "type": "List"}
		)
		self.assertEqual(KeySpace("ToDo").find("probe-open", "nobody-45985@example.com").label, "Open probe")

		site_row("probe-open", label="Site's")
		self.assertEqual(KeySpace("ToDo").find("probe-open", "nobody-45985@example.com").label, "Site's")
		self.assertEqual(KeySpace("ToDo").find("probe-open").label, "Probe Open")

	def test_a_new_view_does_not_take_an_app_key(self):
		self.folders.own_view("probe-open")
		self.assertEqual(KeySpace("ToDo").claim("Probe Open"), "probe-open-2")
		self.assertEqual(person_row("Probe Open").key, "probe-open-2")

	def test_a_site_row_overrides_an_app_view_and_its_delete_brings_it_back(self):
		self.folders.own_view("probe-open", label="Open probe")
		toggle_favourite("DocType", "ToDo", add=True, view="probe-open")

		row = site_row("probe-open", label="Site's")
		self.assertEqual(row.key, "probe-open")
		self.assertEqual(KeySpace("ToDo").find("probe-open").label, "Site's")

		row.delete(ignore_permissions=True)
		self.assertEqual(KeySpace("ToDo").find("probe-open").label, "Open probe")
		self.assertTrue(
			frappe.db.exists(
				"Favourite",
				{"user": "Administrator", "reference_name": "ToDo", "view": "probe-open"},
			)
		)

	def test_a_site_override_keeps_the_app_views_type(self):
		self.folders.own_view("probe-open")
		index = self.index()
		index.views["todo"]["probe-open"] = index.views["todo"]["probe-open"]._replace(type="Kanban")
		self.enterContext(patch.object(app_views_module, "current_index", return_value=index))
		with self.assertRaisesRegex(frappe.ValidationError, "stays a Kanban view"):
			site_row("probe-open")

	def test_a_site_override_shares_its_key_with_a_person_s_older_view(self):
		own = person_row("Probe Open")  # made before an app release shipped the same key
		self.folders.own_view("probe-open")
		site = site_row("probe-open")

		self.assertEqual([own.key_slot, site.key_slot], ["probe-open", None])
		with patch.object(fill_view_key_slots, "add_key_index"):
			fill_view_key_slots.execute()
		self.assertIsNone(frappe.db.get_value("Doctype View", site.name, "key_slot"))

	def test_a_second_site_override_is_refused(self):
		self.folders.own_view("probe-open")
		site_row("probe-open")
		with self.assertRaises(DuplicateViewError):
			site_row("probe-open")

	def test_a_view_the_person_cannot_read_is_not_found_for_them(self):
		self.folders.own_view("probe-open")
		with set_user("Guest"), self.assertRaises(frappe.PermissionError):
			find("ToDo", "probe-open")

	def test_deleting_a_persons_own_row_at_an_app_key_keeps_their_default(self):
		own = person_row("Probe Open")  # made before an app release shipped the same key
		self.folders.own_view("probe-open")
		frappe.db.delete("Default View", {"reference_doctype": "ToDo"})
		default_view_api.save("ToDo", "probe-open", "user")

		own.delete(ignore_permissions=True)
		self.assertEqual(DefaultViews().addresses(["ToDo"]), {"ToDo": "probe-open"})


class TestAppDefaults(AppViewCase):
	def setUp(self):
		super().setUp()
		frappe.db.delete("Default View", {"reference_doctype": "ToDo"})
		self.folders.own_view("probe-frappe", default=True)
		self.folders.custom_view("acme", "probe-acme", default=True)

	def test_an_apps_default_applies_in_its_prefix(self):
		self.assertEqual(DefaultViews(app="acme").addresses(["ToDo"]), {"ToDo": "probe-acme"})

	def test_outside_it_the_doctypes_own_app_default_applies(self):
		self.assertEqual(DefaultViews(app="zeta").addresses(["ToDo"]), {"ToDo": "probe-frappe"})
		self.assertEqual(DefaultViews().addresses(["ToDo"]), {"ToDo": "probe-frappe"})

	def test_a_doctype_made_on_the_site_is_named_from_the_database(self):
		self.folders.custom_view("acme", "probe-note", doctype="note", default=True)
		self.assertEqual(app_defaults("acme")["Note"], "probe-note")

	def test_the_sites_default_may_point_at_an_app_view(self):
		self.assertEqual(default_view_api.save("ToDo", "probe-acme", "site", app="zeta"), "probe-acme")
		self.assertEqual(
			frappe.db.get_value("Default View", {"reference_doctype": "ToDo", "user": SITE_ROW}, "view"),
			"probe-acme",
		)

	def test_a_stored_default_beats_the_app_default_and_may_point_at_an_app_view(self):
		with set_user("Administrator"):
			self.assertEqual(default_view_api.save("ToDo", "probe-acme", "user", app="zeta"), "probe-acme")
			self.assertEqual(default_view_api.clear("ToDo", "user", app="acme"), "probe-acme")
			self.assertEqual(default_view_api.clear("ToDo", "user", app="zeta"), "probe-frappe")


class TestInstalledViewFiles(IntegrationTestCase):
	def test_every_installed_file_passes_the_checks_a_row_gets(self):
		index = ViewIndex(tuple(frappe.get_installed_apps()))
		self.assertEqual(index.refused, [])
		self.assertIn("open", app_views("ToDo"))

	def test_both_globs_name_view_files_and_the_doctype_glob_does_not(self):
		own = "frappe/desk/doctype/todo/frontend/views/open.json"
		custom = "crm/fcrm/custom/contact/views/my-contacts.json"
		self.assertTrue(pathmatch("**/doctype/*/frontend/views/*.json", own))
		self.assertTrue(pathmatch("**/custom/*/views/*.json", custom))
		self.assertFalse(pathmatch("**/doctype/*/*.json", own))
		self.assertFalse(pathmatch("**/custom/*.json", custom))
		lines = Path(frappe.get_app_path("frappe", "..", "babel_extractors.csv")).read_text().splitlines()
		self.assertIn("**/custom/*/views/*.json,frappe.gettext.extractors.app_view.extract", lines)

	def test_extracts_the_label(self):
		path = frappe.get_app_path("frappe", "desk", "doctype", "todo", "frontend", "views", "open.json")
		with open(path, "rb") as f:
			fileobj = BytesIO(f.read())
		fileobj.name = path
		self.assertEqual(list(extract(fileobj)), [(2, "_", "Open", ["Label of the open view"])])


def site_row(key: str, label: str = "Probe") -> "frappe.Document":
	row = frappe.get_doc(
		{
			"doctype": "Doctype View",
			"reference_doctype": "ToDo",
			"type": "List",
			"user": SITE_ROW,
			"key": key,
			"label": label,
			"settings": json.dumps(LIST_SETTINGS),
		}
	)
	return row.insert(ignore_permissions=True)


def person_row(label: str) -> "frappe.Document":
	row = frappe.get_doc(
		{"doctype": "Doctype View", "reference_doctype": "ToDo", "type": "List", "label": label}
	)
	row.user = "Administrator"
	return row.insert(ignore_permissions=True)
