import re
from itertools import chain, count

import click

import frappe
from frappe.desk.doctype.sidebar.sidebar import UNROUTABLE_IN_A_TITLE, build_sidebar, shell_holding_slug
from frappe.patches.v16_0.sidebar_archive import (
	archive_exists,
	custom_module_of,
	is_custom,
	is_module,
	site_rows,
	write_base,
	written_as_of,
)
from frappe.utils.modules import get_module_placement


def execute():
	"""Turn each sidebar the site made in v16 into a custom module with that sidebar.

	It cannot stay in the module v16 filed it under, because a module has one sidebar and that
	module now shows the app's. The old rows are not changed, so this is safe to run again.
	"""
	if not archive_exists():
		return

	for row in site_rows():
		if not is_custom(row) or custom_module_of(row.name):
			continue

		module = make_module(row)
		plan = build_sidebar(module, [row])
		plan.title = module
		write_base(module, plan, written_as_of([row]))

		click.secho(f"Sidebar '{row.name}': carried into custom module '{module}'", fg="green")


def make_module(row) -> str:
	"""Create the custom module `row` becomes, listed in the dock of the app v16 filed it under."""
	name = module_name_for(row.name)
	if frappe.db.exists("Module Def", name):
		return name

	frappe.get_doc(
		{
			"doctype": "Module Def",
			"module_name": name,
			"custom": 1,
			"app_name": get_module_placement(row.module) if is_module(row.module) else None,
		}
	).insert(ignore_permissions=True)
	return name


# `Module Def.module_name` is a Data field
MODULE_NAME_LENGTH = 140


def module_name_for(title: str) -> str:
	"""The sidebar's title, or the nearest free name to it.

	The title is also the sidebar's, so it has to be one a desk URL can carry. A custom module that
	has no sidebar yet is the site's own and is reused; any other module of that name is not this
	sidebar's, so `Stock` becomes `Stock (Custom)`.

	A module's name holds 140 characters, so the title is cut short enough to take the suffix. One
	with nothing left once cleaned, such as `//`, is named `Custom Sidebar` instead.
	"""
	cleaned = " ".join(re.sub(f"[{re.escape(UNROUTABLE_IN_A_TITLE)}]", " ", title).split())
	cleaned = cleaned[: MODULE_NAME_LENGTH - len(" (Custom) 999")].strip() or "Custom Sidebar"
	candidates = chain((cleaned, f"{cleaned} (Custom)"), (f"{cleaned} (Custom) {n}" for n in count(2)))
	return next(candidate for candidate in candidates if is_free(candidate))


def is_free(name: str) -> bool:
	if frappe.db.exists("Module Def", name):
		return bool(frappe.db.get_value("Module Def", name, "custom")) and not frappe.db.exists(
			"Sidebar", {"module": name}
		)

	return not shell_holding_slug(name, module=name)
