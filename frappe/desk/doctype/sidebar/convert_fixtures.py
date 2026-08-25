"""Convert an app's old sidebar fixtures into per-module `Sidebar` exports.

An app used to ship its sidebars as `<app>/workspace_sidebar/*.json` -- one file per
workspace, in a flat app-level folder that a special case in the sync walked. Those files stop
being imported with this release: a sidebar belongs to a **module** now, and an app ships one
per module under `<app>/<module>/sidebar/`, which rides the ordinary doc-files walk with
no special case at all.

Nothing breaks in the meantime -- a module whose app has not re-exported falls back to a base
computed from its own contents -- but "falls back to generated" means an app's whole curated
navigation reverting on this release, and there are 28 of these files across six apps. So the
work is a command rather than an afternoon of hand-editing, and
`frappe/patches/v16_0/notify_apps_to_convert_sidebar_fixtures.py` is what tells an author it
exists.

	bench --site <site> convert-sidebar-fixtures --app erpnext

Retiring: this, the command and the notice go with the icon-grid batch, on one of the two
triggers written down in `frappe/desk/RETIRING.md` -- by which point an app that has not
converted has had a whole release line to.

Reads only; the old folder is left exactly where it is, so a conversion can be inspected,
thrown away, and run again.
"""

import json
import os

import frappe
from frappe.desk.doctype.sidebar.sidebar import (
	SIDEBAR_ITEM_FIELDS,
	build_sidebar,
	majority_module_of,
)
from frappe.modules.utils import get_app_level_files

OLD_FIXTURE_FOLDER = "workspace_sidebar"


def apps_with_old_fixtures() -> dict[str, int]:
	"""Installed apps still shipping the old folder, and how many files each holds.

	Named rather than warned about in the abstract: an author reading "some apps still ship
	the old format" has to go and find out whether theirs is one of them.
	"""
	counts = {}
	for app in frappe.get_installed_apps():
		files = [path for path in get_app_level_files(OLD_FIXTURE_FOLDER, app) if path.endswith(".json")]
		if files:
			counts[app] = len(files)
	return counts


def read_fixtures(app: str) -> list[frappe._dict]:
	"""The app's old fixtures, shaped like the merge's other sources.

	Personal forks are skipped: a `for_user` sidebar in an app's folder is somebody's own
	arrangement that got exported by accident, and an app has no business shipping one.
	"""
	sources = []
	for path in sorted(get_app_level_files(OLD_FIXTURE_FOLDER, app)):
		if not path.endswith(".json"):
			continue

		# the path is an installed app's own folder, walked by the operator's own bench
		# command -- nothing here comes from a request
		with open(path) as f:  # nosemgrep
			fixture = frappe.parse_json(f.read())
		if isinstance(fixture, list):
			fixture = fixture[0] if fixture else None
		if not fixture or fixture.get("for_user"):
			continue

		rows = [frappe._dict(row) for row in (fixture.get("items") or [])]
		if not rows:
			continue

		sources.append(
			frappe._dict(
				{
					"name": fixture.get("name") or fixture.get("title"),
					"title": fixture.get("title"),
					"icon": fixture.get("header_icon"),
					"module": fixture.get("module"),
					"rows": rows,
					# the fixtures carry no ordering of their own; file order stands in
					"sequence_id": 0,
					"creation": path,
					"path": path,
				}
			)
		)
	return sources


def convert_app(app: str, dry_run: bool = False) -> list[dict]:
	"""Write one `Sidebar` export per module the app's fixtures name.

	**Idempotent, and safe against an app that has already converted by hand**: a module whose
	export file is already there is reported and left alone, never overwritten. That is what
	makes it runnable against erpnext, which has ten converted files today and fourteen old
	ones.
	"""
	by_module = {}
	unresolved = []
	for source in read_fixtures(app):
		module = source.module or majority_module_of(source.rows)
		if not module:
			unresolved.append(source.path)
			continue
		by_module.setdefault(module, []).append(source)

	results = [{"module": None, "path": path, "state": "no module"} for path in unresolved]

	for module in sorted(by_module):
		# Built before the path rather than after it: a `Sidebar` is named by its title, so the
		# title the merge lands on is what says where the file goes.
		plan = build_sidebar(module, by_module[module])

		try:
			path = export_path(module, plan["title"])
		except (frappe.DoesNotExistError, ImportError):
			# the fixture names a module this app has no folder for, so there is nowhere to
			# write it; anything else here is a real failure and should not be reported as one
			frappe.clear_last_message()
			results.append({"module": module, "path": None, "state": "no folder"})
			continue

		# A file already there is left alone, under either of the two names it could be under:
		# an app that converted by hand before a sidebar was named by its title wrote its file
		# under the module's name, and re-converting must not write it a second time.
		existing = next((p for p in (path, export_path(module)) if os.path.exists(p)), None)
		if existing:
			results.append({"module": module, "path": existing, "state": "already converted"})
			continue

		results.append(
			{
				"module": module,
				"path": path,
				"state": "converted",
				"sources": len(by_module[module]),
				"items": len(plan["items"]),
			}
		)

		if not dry_run:
			write_export(path, module, plan, app)

	return results


def export_path(module: str, title: str | None = None) -> str:
	"""Where `bench migrate` will look for this sidebar. Mirrors `Sidebar.exported_file_path`,
	which is also what orphan removal derives -- both are built from the record's name, and a
	sidebar's name is its title.

	`title` defaults to the module's name, which is what a sidebar's title defaults to.
	"""
	scrubbed = frappe.scrub(title or module)
	return os.path.join(frappe.get_module_path(module), "sidebar", scrubbed, f"{scrubbed}.json")


def write_export(path: str, module: str, plan, app: str) -> None:
	"""The document, in the shape `import_file` reads back.

	`standard: 1` because that is what the flag means -- a file in an app backs this row -- and
	writing the file is precisely what earns it.
	"""
	os.makedirs(os.path.dirname(path), exist_ok=True)

	doc = {
		"doctype": "Sidebar",
		# the record is named by its title, and the file is named after the record
		"name": plan["title"],
		"module": module,
		"title": plan["title"],
		"header_icon": plan["header_icon"],
		"app": app,
		"standard": 1,
		"items": [
			{
				"doctype": "Sidebar Item",
				"parentfield": "items",
				"parenttype": "Sidebar",
				"idx": idx,
				**{field: item.get(field) for field in SIDEBAR_ITEM_FIELDS if item.get(field) is not None},
			}
			for idx, item in enumerate(plan["items"], start=1)
		],
	}

	# `export_path` builds this from `get_module_path`, the same way every other document
	# export in the framework does
	with open(path, "w") as f:  # nosemgrep
		f.write(json.dumps(doc, indent=1, sort_keys=True) + "\n")
