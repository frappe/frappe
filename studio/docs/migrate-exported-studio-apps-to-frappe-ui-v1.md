# Migrating exported Studio apps to frappe-ui v1

Studio's patches migrate pages and components in the database. A standard app's pages and
components also live as JSON in the app's own repo (`<app>/studio/<studio_app>/`), and those files
are imported over the database on every `bench migrate`. A patch cannot rewrite another app's repo,
so each app migrates its files once and commits the result. This is the procedure for that.

Do it on a bench where Studio is already on the frappe-ui v1 branch, in the repo of the app that
owns the files.

## What gets migrated

The same three functions Studio's patches run on the database, in this order:

| Migration | What it changes |
| --- | --- |
| `migrate_blocks_to_frappe_ui_v1` | Renamed components, props, slots and events; feather icon names to `lucide-*`; `rounded-md` style radius aliases to `rounded-5` |
| `migrate_charts_to_frappe_ui_charts` | `AxisChart`, `DonutChart`, `NumberChart` `config` objects to frappe-ui/charts props |
| `migrate_get_icon_calls` | Complete literal prop bindings such as `{{ getIcon('x') }}` to `lucide-x`; reports remaining helper references for review |

Run this on files exported before the v1 upgrade and review the diff before importing them.
Do not assume every old and new prop value can be distinguished automatically. In particular,
Tabs that already define `value` keep their selection; check old numeric selections on those tabs
by hand. Page scripts (`<page>.ts`) are scanned for `getIcon` references but are not rewritten.

Do not redo these by hand from the frappe-ui migration guide. The guide describes Vue templates;
these files are Studio's block JSON (`componentProps`, `componentSlots`, `classes`, `baseStyles`),
and several changes are Studio-specific (Sidebar `sections` become child blocks, `FeatherIcon`
becomes an `Icon` block, chart `config` becomes props). Use the guide only for what the script
leaves to you, listed under [By hand](#by-hand).

## Steps

1. Start from a clean tree in the app's repo, so the diff is only the migration.
   Stop `bench watch-studio` while rewriting and reviewing the files.

2. Save the script below as `migrate_exported_files.py` anywhere outside the repo and run it from
   the bench's `sites` directory:

   ```bash
   cd <bench>/sites
   ../env/bin/python /path/to/migrate_exported_files.py <app>
   ```

   It prints each file it rewrote and identifies files and fields that need manual review.
   Resolve those reports before importing the files. Reports may appear even when a file was unchanged.

3. Check the result.
   - `git diff --stat` touches only `studio_page/*/*.{json,ts}` and `studio_components/*.json`.
   - Load the reviewed files into a site with `bench --site <site> migrate`, then open each page
     in the editor and at its route. Look for blank blocks and for
     errors in the browser console.

4. Commit the files in the app's repo.

## By hand

- Charts the script reports as having a dynamic `config` (a `{{ }}` binding or a variable): build the
  new props in the page script instead. See frappe-ui's charts docs.
- Sidebars with dynamic `header` or `sections`: convert them to Sidebar child blocks manually.
  Dialogs with a dynamic `options` binding: move its fields to the flat props (`title`, `message`,
  `size`, `icon`, `actions`). Dialogs with both a `disableOutsideClickToClose` binding and a static
  `dismissible`: keep one, as `dismissible` (the negation of the old binding). The script preserves
  these props and reports the affected blocks; in the editor they show under **Deprecated**.
- Coloured ink tokens (`text-ink-red-5`, `var(--ink-red-5)`) keep their names but v1 renders each
  step one shade lighter. The script does not touch them; adjust a step by hand where it matters.
- Remaining calls to Studio's `getIcon(...)` helper in page scripts, event handlers or expressions:
  replace literal calls such as `getIcon('search')` with `'lucide-search'`, and construct the
  `"lucide-<name>"` string for dynamic arguments. The script only rewrites complete literal prop
  bindings. It reports possible references, including methods, comments and string contents;
  leave unrelated references such as a custom `helpers.getIcon()` method unchanged.
- Anything else in a page script that calls a removed frappe-ui API needs the frappe-ui migration
  guide (`frappe-ui/docs/content/docs/migration.md`).
- Custom Vue components in the app (`studio/<studio_app>/components/`) are ordinary frappe-ui code.
  Migrate them with the frappe-ui migration guide.

## Script

```python
"""Migrate a frappe app's exported Studio files to frappe-ui v1."""

import glob
import sys

import frappe

from studio.studio.doctype.studio_page.patches import (
	migrate_blocks_to_frappe_ui_v1 as frappe_ui_v1,
	migrate_charts_to_frappe_ui_charts as charts,
	migrate_get_icon_calls as get_icon,
)

BLOCK_FIELDS = ("blocks", "draft_blocks", "block")


def main(app):
	folder = frappe.get_app_source_path(app, "studio")
	pages = glob.glob(f"{folder}/*/studio_page/*/*.json")
	components = glob.glob(f"{folder}/*/studio_components/*.json")
	for path in sorted(pages + components):
		if migrate_file(path):
			print(path)
	for path in sorted(glob.glob(f"{folder}/*/studio_page/*/*.ts")):
		report_get_icon_calls(frappe.read_file(path), path)


def migrate_file(path) -> bool:
	data = frappe.parse_json(frappe.read_file(path))
	dynamic_props = []
	dynamic_charts = []
	for field in BLOCK_FIELDS:
		if not data.get(field):
			continue
		location = f"{path}:{field}"
		text = frappe_ui_v1.migrate_blocks_json(data[field], dynamic_props, location)
		text = charts.migrate_blocks_json(text, dynamic_charts, location)
		text = get_icon.rewrite_get_icon_calls(text)
		data[field] = frappe.parse_json(text)
		report_get_icon_calls(text, location)
	for location, component_id in dynamic_props:
		print(f"  {location}: {component_id} has dynamic props v1 dropped: migrate them by hand")
	for location, component_id in dynamic_charts:
		print(f"  {location}: chart {component_id} has a dynamic `config`: migrate its props by hand")

	# same layout as studio.export.write_document_file, so the diff is only the blocks
	text = frappe.as_json(data) + "\n"
	if text == frappe.read_file(path):
		return False
	with open(path, "w") as file:
		file.write(text)
	return True


def report_get_icon_calls(text, location):
	for call in get_icon.find_get_icon_calls(text):
		print(f"  {location}: review {call}; replace calls to Studio's helper with lucide-* strings")


if __name__ == "__main__":
	main(sys.argv[1])
```
