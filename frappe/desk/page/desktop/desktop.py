import sys

import frappe
from frappe.desk.doctype.desktop_settings.desktop_settings import is_desktop_icons_page


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

	# The Desktop Icon grid restores each user's saved arrangement from Desktop Layout. The
	# Apps screen has no per-user layout -- it's ordered by the add_to_apps_screen hook.
	if is_desktop_icons_page():
		try:
			context.desktop_layout = frappe.get_doc("Desktop Layout", frappe.session.user).layout or {}
		except frappe.DoesNotExistError:
			frappe.clear_last_message()
			context.desktop_layout = {}

	return context
