# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Sidebar boot path for `Desktop Icon and Workspace Sidebar` navigation.

Workspace navigation builds `bootinfo.workspace_sidebar_item` from
`Workspace.sidebar_items` (see `frappe.boot.get_sidebar_items`). This module is the
other half: it reads the standalone `Workspace Sidebar` doctype, the way v16 did.

Both produce the same payload shape, so the client-side sidebars stay interchangeable
-- `frappe.desk.test_navigation.py` asserts that.

Everything here is only reachable when `System Settings.navigation` is
`Desktop Icon and Workspace Sidebar`; when that option is eventually dropped, this
module goes with it.
"""

import frappe
from frappe import _
from frappe.desk.doctype.workspace_sidebar.workspace_sidebar import (
	add_section_breaks,
	create_sidebar_items,
)
from frappe.desk.utils import is_item_allowed
from frappe.utils.caching import site_cache


def get_sidebar_items(allowed_workspaces):
	"""Build `bootinfo.workspace_sidebar_item` from the `Workspace Sidebar` doctype."""
	workspace_sidebars = frappe.get_all(
		"Workspace Sidebar", fields=["name", "header_icon", "module_onboarding"]
	)
	workspace_sidebars.extend(auto_generate_sidebar_from_module())

	# Permission context for is_item_allowed. Workspace inherits DeskViews, whose caches
	# are lazy, so a throwaway doc is cheap -- this mirrors what the workspace-nav path
	# does in frappe.boot.add_sidebar_entry.
	ctx = frappe.new_doc("Workspace")
	ctx.allowed_workspaces = allowed_workspaces

	sidebar_items = {}

	for sidebar in workspace_sidebars:
		sidebar_title = sidebar.get("name")
		if sidebar_title:
			sidebar_doc = frappe.get_doc("Workspace Sidebar", sidebar_title)
		else:
			# auto-generated sidebars are unsaved docs, not rows
			sidebar_title = sidebar.title
			sidebar_doc = sidebar

		if not (
			frappe.session.user == "Administrator"
			or sidebar_doc.module in get_allowed_modules(sidebar_doc)
			or sidebar_title == "My Workspaces"
		):
			continue

		sidebar_items[sidebar_title.lower()] = {
			"label": sidebar_title,
			"items": [],
			"header_icon": sidebar.get("header_icon"),
			"module_onboarding": sidebar.get("module_onboarding"),
			"module": sidebar_doc.module,
			"app": sidebar_doc.app,
		}

		for item in sidebar_doc.items:
			entry = {
				"label": _(item.label),
				"link_to": item.link_to,
				"link_type": item.link_type,
				"type": item.type,
				"icon": item.icon,
				"child": item.child,
				"collapsible": item.collapsible,
				"indent": item.indent,
				"keep_closed": item.keep_closed,
				"display_depends_on": item.display_depends_on,
				"url": item.url,
				"show_arrow": item.show_arrow,
				"filters": item.filters,
				"route_options": item.route_options,
				"tab": item.navigate_to_tab,
			}

			if item.link_type == "Report" and item.link_to and frappe.db.exists("Report", item.link_to):
				report_type, ref_doctype = frappe.db.get_value(
					"Report", item.link_to, ["report_type", "ref_doctype"]
				)
				entry["report"] = {"report_type": report_type, "ref_doctype": ref_doctype}

			# "My Workspaces" holds the user's own private workspaces, which are theirs by
			# definition, and section breaks carry no target to check.
			if (
				"My Workspaces" in sidebar_title
				or item.type == "Section Break"
				or is_item_allowed(item.link_to, item.link_type, ctx)
			):
				sidebar_items[sidebar_title.lower()]["items"].append(entry)

	add_user_specific_sidebar(sidebar_items)
	return sidebar_items


def get_allowed_modules(sidebar_doc):
	"""Modules the session user may see, via the doc's cached `frappe.get_user()`."""
	user = getattr(sidebar_doc, "user", None)
	if user is None:
		# auto-generated sidebars are plain new_doc()s built during migrate, when
		# WorkspaceSidebar.__init__ skips building the user caches
		return []

	if not user.allow_modules:
		user.build_permissions()

	return user.allow_modules


def add_user_specific_sidebar(sidebar_items):
	"""Promote a user's own `<name>-<user>` sidebar over the shared `<name>` one."""
	suffix = f"-{frappe.session.user.lower()}"
	for sidebar in [s for s in sidebar_items if suffix in s]:
		try:
			base = sidebar.replace(suffix, "")
			sidebar_items[sidebar]["label"] = sidebar_items[base]["label"]
			sidebar_items[base] = sidebar_items.pop(sidebar)
		except KeyError:
			pass


@site_cache()
def auto_generate_sidebar_from_module():
	"""Generate a fallback sidebar for modules that have no `Workspace Sidebar`.

	Deliberately a separate function from the workspace-nav one rather than a branch
	inside it: `site_cache` is a per-process dict that `frappe.clear_cache()` only clears
	in the calling worker, so one function holding two answers would serve stale results
	from other workers after the setting is flipped. Two functions, one answer each.

	The skip condition is also genuinely different -- workspace navigation skips a module
	once `Workspace.sidebar_items` has rows, which after migration is every module.
	"""
	sidebars = []
	for module in frappe.get_all("Module Def", pluck="name"):
		if frappe.db.exists("Workspace Sidebar", {"module": module, "for_user": None}) or frappe.db.exists(
			"Workspace Sidebar", {"name": module, "for_user": None}
		):
			continue

		module_info = get_module_info(module)
		sidebar = frappe.new_doc("Workspace Sidebar")
		sidebar.title = module
		sidebar.items = create_sidebar_items(module_info)
		sidebar.module = module
		sidebar.header_icon = "hammer"
		sidebar.app = frappe.local.module_app.get(frappe.scrub(module), None)
		sidebars.append(sidebar)

	return sidebars


def get_module_info(module_name):
	"""Entities belonging to a module, ordered the way v16 laid them out.

	Kept separate from the workspace-nav version, which takes the first three doctypes
	and filters workspaces to public ones; this one ranks doctypes by row count.
	"""
	entities = ["Workspace", "Dashboard", "DocType", "Report", "Page"]
	module_info = {}

	for entity in entities:
		filters = [{"module": module_name}]
		pluck = "name"
		fieldnames = ["name"]
		if entity.lower() == "doctype":
			filters.append({"istable": 0})
		if entity.lower() == "page":
			fieldnames.append("title")
			pluck = None
		module_info[entity] = frappe.get_all(
			entity, filters=filters, fields=fieldnames, pluck=pluck, order_by="creation asc"
		)

	# with no workspaces to lead with, doctypes go to the front
	if not module_info.get("Workspace"):
		module_info = {
			"DocType": module_info.get("DocType"),
			"Workspace": module_info.get("Workspace"),
			"Report": module_info.get("Report"),
			"Dashboard": module_info.get("Dashboard"),
			"Page": module_info.get("Page"),
		}

	if top_doctypes := choose_top_doctypes(module_info.get("DocType")):
		module_info["DocType"] = top_doctypes

	return module_info


def choose_top_doctypes(doctype_names):
	"""The three most-populated non-single, non-virtual doctypes."""
	from frappe.model.utils import is_single_doctype

	doctype_limit = 3
	if not doctype_names or len(doctype_names) <= doctype_limit:
		return None

	try:
		doctype_count_map = {}
		for doctype in doctype_names:
			if not is_single_doctype(doctype) and not frappe.get_meta(doctype).is_virtual:
				doctype_count_map[doctype] = frappe.db.count(doctype)
		return [
			name
			for name, _count in sorted(doctype_count_map.items(), key=lambda x: x[1], reverse=True)[
				:doctype_limit
			]
		]
	except frappe.db.ProgrammingError:
		# table not found
		return None
