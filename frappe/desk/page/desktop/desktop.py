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
	context.desktop_icons = get_desktop_icons()
	context.current_user = frappe.session.user
	return context
