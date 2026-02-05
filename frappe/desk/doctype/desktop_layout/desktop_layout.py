# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import add_workspace_to_desktop
from frappe.model.document import Document


class DesktopLayout(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		layout: DF.Code | None
		user: DF.Link | None
	# end: auto-generated types

	pass


@frappe.whitelist()
def save_layout(user: str, layout: str, new_icons: str):
	if not user:
		user = frappe.session.user
	layout = json.loads(layout)
	new_icons = json.loads(new_icons)
	desktop_layout = None
	try:
		desktop_layout = frappe.get_doc("Desktop Layout", frappe.session.user)
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		desktop_layout = frappe.new_doc("Desktop Layout")
		desktop_layout.user = frappe.session.user

	if layout:
		desktop_layout.layout = json.dumps(layout)
		desktop_layout.save()

	for icon in new_icons:
		workspace = icon.get("workspace")
		if workspace:
			new_workspace = frappe.new_doc("Workspace")
			new_workspace.update(workspace)
			new_workspace.title = new_workspace.label
			new_workspace.save()
			return add_workspace_to_desktop(new_workspace.name)
		desktop_icon = frappe.new_doc("Desktop Icon")
		desktop_icon.update(icon)
		desktop_icon.owner = frappe.session.user
		desktop_icon.save()

	return {"layout": layout}


@frappe.whitelist()
def delete_layout():
	return frappe.delete_doc_if_exists("Desktop Layout", frappe.session.user)
