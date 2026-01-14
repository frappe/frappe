import frappe
from frappe import _
from frappe.utils.caching import redis_cache


def get_modules_from_all_apps_for_user(user: str | None = None) -> list[dict]:
	user = user or frappe.session.user
	all_modules = get_modules_from_all_apps()
	global_blocked_modules = frappe.get_cached_doc("User", "Administrator").get_blocked_modules()
	user_blocked_modules = frappe.get_cached_doc("User", user).get_blocked_modules()
	blocked_modules = global_blocked_modules + user_blocked_modules
	allowed_modules_list = [m for m in all_modules if m.get("module_name") not in blocked_modules]

	return allowed_modules_list


def get_modules_from_all_apps():
	modules_list = []
	for app in frappe.get_installed_apps():
		modules_list += get_modules_from_app(app)
	return modules_list


@redis_cache
def get_modules_from_app(app):
	return frappe.get_all("Module Def", filters={"app_name": app}, fields=["module_name", "app_name as app"])


def is_domain(module):
	return module.get("category") == "Domains"


def is_module(module):
	return module.get("type") == "module"
