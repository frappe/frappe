import sys

import frappe
from frappe.desk.navigation import is_workspace_navigation


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/app"
		raise frappe.Redirect
	brand_logo = None
	brand_logo = frappe.get_single_value("Navbar Settings", "app_logo")
	if not brand_logo:
		brand_logo = frappe.get_hooks("app_logo_url", app_name="frappe")[0]
	context.brand_logo = brand_logo
	context.show_search_bar = frappe.get_cached_value("User", frappe.session.user, "search_bar")

	# The desktop icon grid restores each user's saved arrangement from Desktop Layout.
	# Workspace navigation has no per-user layout -- its apps screen is ordered by the
	# `add_to_apps_screen` hook's sequence_id.
	if not is_workspace_navigation():
		try:
			context.desktop_layout = frappe.get_doc("Desktop Layout", frappe.session.user).layout or {}
		except frappe.DoesNotExistError:
			frappe.clear_last_message()
			context.desktop_layout = {}

	return context
