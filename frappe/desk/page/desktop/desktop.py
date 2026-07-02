import sys

import frappe


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
	return context
