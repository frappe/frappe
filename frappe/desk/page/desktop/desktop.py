import sys

import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import get_desktop_icons


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/app"
		raise frappe.Redirect
	brand_logo = None
	brand_logo = frappe.get_single_value("Navbar Settings", "app_logo")
	if not brand_logo:
		brand_logo = frappe.get_hooks("app_logo_url", app_name="frappe")[0]
	context.brand_logo = brand_logo
<<<<<<< HEAD
	context.desktop_icons = get_desktop_icons()
	context.current_user = frappe.session.user
	# check if system is mac or not
	context.is_mac = sys.platform == "darwin"
=======
	try:
		context.desktop_layout = frappe.get_doc("Desktop Layout", frappe.session.user).layout or {}
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		context.desktop_layout = {}

	context.show_search_bar = frappe.get_cached_value("User", frappe.session.user, "search_bar")
>>>>>>> upstream/develop
	return context
