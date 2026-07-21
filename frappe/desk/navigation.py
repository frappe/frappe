# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe

# The two navigation systems a site can run. These strings are the options of the
# `navigation` field in System Settings, so they are what a system manager sees.
#
# This module is the only place either string is compared. Everything else asks
# `is_workspace_navigation()`, so the wording can change without a hunt.
WORKSPACE = "Workspace"
DESKTOP_ICON_AND_WORKSPACE_SIDEBAR = "Desktop Icon and Workspace Sidebar"


def get_navigation() -> str:
	"""Return the site's navigation system.

	Defaults to `Workspace` when unset, which is the case on a fresh install --
	existing sites are moved to `Desktop Icon and Workspace Sidebar` by patch so an
	upgrade doesn't change navigation underneath them.
	"""
	return frappe.get_system_settings("navigation") or WORKSPACE


def is_workspace_navigation() -> bool:
	"""True when the site runs workspace-driven navigation.

	That means the workspace dock, the hook-driven apps screen, and sidebars authored
	on `Workspace.sidebar_items`. When false, the site renders the desktop icon grid
	and reads sidebars from the separate `Workspace Sidebar` doctype instead.
	"""
	return get_navigation() == WORKSPACE
