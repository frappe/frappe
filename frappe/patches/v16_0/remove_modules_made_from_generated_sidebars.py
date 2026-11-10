import click

import frappe
from frappe.desk.doctype.custom_sidebar.custom_sidebar import (
	_save_customization,
	base_items,
	get_customization,
	layer_arrangement,
	layers_below,
	resolve_arrangement,
)
from frappe.desk.doctype.sidebar.sidebar import build_sidebar, item_key
from frappe.model.delete_doc import get_linked_docs
from frappe.patches.v16_0.sidebar_archive import (
	archive_exists,
	generated_from_app_workspace,
	is_module,
	modules_converted_from,
	parse_json_list,
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
			if held := document_filed_under(module, row.name):
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


def document_filed_under(module: str, converted_from: str) -> str | None:
	"""The first document naming `module`, as `DocType name`, or None when nothing does.

	Three things the module was made with do not count: the sidebar converted from
	`converted_from`, which is the reason it exists; the page named after it, which
	`Module Def.after_insert` made with it; and each user's `Block Module` row, reported as its
	user, which `convert_custom_sidebars` wrote and `remove_module` takes back. Another sidebar
	or workspace is the site's content. Both are asked for on their own, since both doctypes are
	in `ignore_links_on_delete` and a delete would not refuse on their behalf.
	"""
	for sidebar in frappe.get_all("Sidebar", filters={"module": module}, fields=["name", "merged_from"]):
		if parse_json_list(sidebar.merged_from) != [converted_from]:
			return f"Sidebar {sidebar.name}"
	if workspace := frappe.db.get_value("Workspace", {"module": module, "name": ["!=", module]}):
		return f"Workspace {workspace}"
	for link in get_linked_docs(frappe.get_doc("Module Def", module)):
		if link["reference_doctype"] != "User":
			return f"{link['reference_doctype']} {link['reference_docname']}"
	return None


def move_user_layers(module: str, into: str | None) -> None:
	"""Save each arrangement of `module`'s sidebar again as a layer over `into`'s base.

	A layer is a delta on what sits below it: a reference row names an item the base or the site's
	layer holds, and stores only what it overrides. Moved as it stands, every reference to an item
	the new base lacks would name nothing. So each arrangement is read whole, the way the editor
	opens it (`layer_arrangement`: this layer over the site's, with what it hid), and saved whole
	the way the editor saves it (`_save_customization`, which settles references against the new
	base and keeps the layer's label and icon). An item the new base and site layer do not show
	travels as the layer's own, which is what `added` means. The site's layer goes first, so the
	users' layers settle against it. The old layers go with the module.

	A layer already on `into` is the user's later word on that module, so it wins and this one is
	dropped, as it is when there is nowhere to move it.
	"""
	layers = frappe.get_all(
		"Custom Sidebar",
		filters={"module": module},
		fields=["name", "user", "label", "header_icon"],
		order_by="user asc",
	)
	for layer in layers:
		user = layer.user or None
		who = layer.user or "the site"
		if not into or not is_module(into) or get_customization(into, user):
			click.secho(f"Custom Sidebar of {who} on '{module}': dropped", fg="yellow")
			continue

		arrangement = layer_arrangement(module, user)
		shown, _hidden = resolve_arrangement(base_items(into), layers_below(into, user))
		shown_keys = {item_key(item) for item in shown}
		rows = []
		for item in arrangement:
			if item_key(item) not in shown_keys:
				# hidden here and absent there: a hidden row would name nothing
				if item["hidden"]:
					continue
				item["added"] = 1
			rows.append(item)

		_save_customization(into, rows, user, label=layer.label, header_icon=layer.header_icon)
		click.secho(f"Custom Sidebar of {who}: moved from '{module}' to '{into}'", fg="green")


def remove_module(module: str) -> None:
	# deleted in place, the way `convert_custom_sidebars` inserted them: saving each user would run
	# the whole of `User.validate` per user
	frappe.db.delete("Block Module", {"parenttype": "User", "module": module})
	# the module's own page was made with it; `Module Def.on_trash` leaves content alone, which
	# would strand it under a module that is gone
	if frappe.db.get_value("Workspace", module, "module") == module:
		frappe.delete_doc("Workspace", module)
	# `Module Def.on_trash` takes the sidebars and what is left of the user layers, and each
	# sidebar's `on_trash` takes its dock rows
	frappe.delete_doc("Module Def", module)
