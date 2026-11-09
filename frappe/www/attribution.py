import frappe
from frappe import _
from frappe.permissions import is_system_user
from frappe.utils.sbom.collector import get_app_info


def get_context(context):
	if not is_system_user():
		frappe.throw(_("You need to be a system user to access this page."), frappe.PermissionError)

	apps = []
	for app in frappe.get_active_apps():
		app_info = get_app_info(app)
		if any([app_info.get("authors"), app_info.get("dependencies"), app_info.get("description")]):
			apps.append(app_info)

	context.apps = apps
