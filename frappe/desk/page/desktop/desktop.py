import sys

import frappe
from frappe.core.doctype.navbar_settings.navbar_settings import get_app_logo
from frappe.desk.doctype.desktop_icon.desktop_icon import get_desktop_icons


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/app"
		raise frappe.Redirect
	context.app_logo = get_app_logo()
	try:
		layout = frappe.get_doc("Desktop Layout", frappe.session.user).layout
		context.desktop_layout = layout if layout else "[]"
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		context.desktop_layout = {}

	context.show_search_bar = frappe.get_cached_value("User", frappe.session.user, "search_bar")
	return context
