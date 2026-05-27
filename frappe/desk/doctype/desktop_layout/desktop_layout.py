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
		if not doc.layout:
			return None

		layout = json.loads(doc.layout)
		latest_icons = frappe.get_all("Desktop Icon", fields="*")

		def key(i):
			return i.get("label") or None

		latest_map = {key(i): i for i in latest_icons}

		name_map = {i.get("name"): i for i in latest_icons if i.get("name")}

		def merge_icon(item):
			k = key(item)
			latest = latest_map.get(k) or name_map.get(item.get("name"))
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
			if layout_hidden is not None:
				item["hidden"] = layout_hidden
			item["parent_icon"] = layout_parent

			if item.get("child_icons"):
				item["child_icons"] = [merge_icon(c) for c in item["child_icons"]]
			return item

		layout = [merge_icon(i) for i in layout]

		def collect_labels(items):
			labels = set()
			for item in items:
				k = key(item)
				if k:
					labels.add(k)
				if item.get("child_icons"):
					labels.update(collect_labels(item["child_icons"]))
			return labels

		_icon_fields = [
			"label",
			"bg_color",
			"link",
			"link_type",
			"app",
			"icon_type",
			"parent_icon",
			"icon",
			"link_to",
			"idx",
			"standard",
			"logo_url",
			"hidden",
			"name",
			"restrict_removal",
			"icon_image",
		]

		saved_labels = collect_labels(layout)
		new_icons = [
			{f: i.get(f) for f in _icon_fields}
			for k, i in latest_map.items()
			if k and k not in saved_labels and not i.get("parent_icon")
		]

		return layout + new_icons
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
	return None


@frappe.whitelist()
def delete_layout():
	return frappe.delete_doc_if_exists("Desktop Layout", frappe.session.user)
