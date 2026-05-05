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
def save_layout(user: str, layout: str, new_icons: str | None = None):
	if not user:
		user = frappe.session.user
	layout = json.loads(layout)
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
	if new_icons:
		new_icons = json.loads(new_icons)
		for icon in new_icons:
			workspace = icon.get("workspace")
			if workspace:
				new_workspace = frappe.new_doc("Workspace")
				new_workspace.update(workspace)
				new_workspace.title = new_workspace.label
				if not new_workspace.public:
					new_workspace.for_user = frappe.session.user
				new_workspace.save()
				return add_workspace_to_desktop(new_workspace.name)
			desktop_icon = frappe.new_doc("Desktop Icon")
			desktop_icon.update(icon)
			desktop_icon.owner = frappe.session.user
			desktop_icon.save()

	return {"layout": layout}


@frappe.whitelist()
def get_layout():
	"""Return the current user's saved desktop layout. Used on desk load to avoid stale cached HTML."""
	try:
		doc = frappe.get_doc("Desktop Layout", frappe.session.user)
		if doc.layout:
			layout = json.loads(doc.layout)
			latest_icons = frappe.get_all("Desktop Icon", fields="*")

			def key(i):
				return i.get("label") or None

			latest_map = {key(i): i for i in latest_icons}

			def merge_icon(item):
				k = key(item)
				latest = latest_map.get(k)
				# preserve layout-specific fields
				layout_idx = item.get("idx")
				layout_parent = item.get("parent_icon", None)
				layout_hidden = item.get("hidden", None)

				if latest:
					if item.get("icon_type") != latest.get("icon_type"):
						if latest.get("icon_type") == "Folder":
							latest["icon_image"] = None
					item.update(latest)
				# restore layout-specific values if present
				if layout_idx is not None:
					item["idx"] = layout_idx
				if layout_hidden:
					item["hidden"] = item.get("hidden")
				item["parent_icon"] = layout_parent

				if item.get("child_icons"):
					item["child_icons"] = [merge_icon(c) for c in item["child_icons"]]
				return item

			layout = [merge_icon(i) for i in layout]
		return layout
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
	return None


@frappe.whitelist()
def delete_layout():
	return frappe.delete_doc_if_exists("Desktop Layout", frappe.session.user)
