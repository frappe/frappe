import click

import frappe
from frappe.desk.doctype.sidebar.sidebar import build_sidebar
from frappe.model.delete_doc import get_linked_docs
from frappe.patches.v16_0.sidebar_archive import (
	archive_exists,
	generated_from_app_workspace,
	is_module,
	modules_converted_from,
	site_rows,
	write_base,
	written_as_of,
)


def execute():
	"""Remove the custom modules an earlier `convert_custom_sidebars` made from sidebars v16 had
	generated from app workspaces.

	That patch took such a row for one the site made, and gave it a module of its own, `Raven
	(Custom)`, beside the app's `Raven`. The row is the app's content, so the app's module is
	where it belongs: it is carried there when that module has no sidebar yet, each user's
	arrangement of it moves along, and the extra module goes with its sidebar, its dock rows and
	the users it was blocked for.

	A module the site has since filed other documents under is kept and named, since removing it
	would orphan them. A row whose own module left with its app has nowhere to be carried, so only
	the extra module goes.
	"""
	if not archive_exists():
		return

	removed = False
	for row in site_rows():
		if row.standard or row.app or not generated_from_app_workspace(row):
			continue

		for module in modules_converted_from(row.name):
			if module == row.module or not frappe.db.get_value("Module Def", module, "custom"):
				continue
			if held := document_filed_under(module):
				click.secho(f"Module '{module}': kept, {held} is filed under it", fg="yellow")
				continue

			if is_module(row.module) and not frappe.db.exists("Sidebar", {"module": row.module}):
				write_base(row.module, build_sidebar(row.module, [row]), written_as_of([row]))
				click.secho(f"Sidebar '{row.name}': carried into '{row.module}'", fg="green")
			move_user_layers(module, row.module)
			remove_module(module)
			removed = True
			click.secho(f"Module '{module}': removed", fg="yellow")

	if removed:
		frappe.clear_cache()


def document_filed_under(module: str) -> str | None:
	"""The first document naming `module`, as `DocType name`, or None when nothing does.

	A `Block Module` row is reported as its user and does not count: `convert_custom_sidebars`
	wrote those rows, and `remove_module` takes them back.
	"""
	for link in get_linked_docs(frappe.get_doc("Module Def", module)):
		if link["reference_doctype"] != "User":
			return f"{link['reference_doctype']} {link['reference_docname']}"
	return None


def move_user_layers(module: str, into: str | None) -> None:
	"""Re-file each user's arrangement of `module`'s sidebar under `into`, which holds the same
	base. One already there is the user's later word on that module, so it wins and this one is
	dropped, as it is when there is nowhere to move it."""
	for layer in frappe.get_all("Custom Sidebar", filters={"module": module}, fields=["name", "user"]):
		taken = frappe.db.exists("Custom Sidebar", {"module": into, "user": layer.user})
		if into and is_module(into) and not taken:
			frappe.db.set_value("Custom Sidebar", layer.name, "module", into, update_modified=False)
		else:
			who = layer.user or "the site"
			click.secho(f"Custom Sidebar of {who} on '{module}': dropped", fg="yellow")


def remove_module(module: str) -> None:
	# deleted in place, the way `convert_custom_sidebars` inserted them: saving each user would run
	# the whole of `User.validate` per user
	frappe.db.delete("Block Module", {"parenttype": "User", "module": module})
	# `Module Def.on_trash` takes the sidebars and what is left of the user layers, and each
	# sidebar's `on_trash` takes its dock rows
	frappe.delete_doc("Module Def", module)
