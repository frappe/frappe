import frappe
from frappe.config import get_modules_from_all_apps_for_user
from frappe.query_builder import Order


@frappe.whitelist()
def get_current_user_info() -> dict:
	current_user = frappe.session.user
	user = frappe.get_cached_value(
		"User", current_user, ["name", "first_name", "full_name", "user_image"], as_dict=True
	)
	user["roles"] = frappe.get_roles(current_user)

	return user


@frappe.whitelist()
def get_permissions_for_current_user() -> dict:
	from frappe.desk.desktop import get_workspace_sidebar_items

	workspaces = get_workspace_sidebar_items().get("pages")
	allow_workspaces = [
		{
			"name": workspace.get("name"),
			"module": workspace.get("module"),
		}
		for workspace in workspaces
	]
	user = frappe.get_user().load_user()
	user.allow_workspaces = allow_workspaces
	return user


@frappe.whitelist()
def get_desktop_items() -> list[dict]:
	"""Returns desktop items for the current user"""
	modules = get_modules_from_all_apps_for_user()
	module_names = {module.get("module_name"): module.get("app") for module in modules}

	DesktopItem = frappe.qb.DocType("Desktop Item")
	desktop_items = (
		frappe.qb.from_(DesktopItem)
		.select("name", "label", "icon", "color", "link_type", "url", "module")
		.where(
			((DesktopItem.link_type == "Module") & (DesktopItem.module.isin(list(module_names.keys()))))
			| (DesktopItem.link_type == "URL")
		)
	).run(as_dict=True)

	for item in desktop_items:
		item["app"] = module_names.get(item.get("module"))

	return sorted(desktop_items, key=lambda x: (x.get("app"), x.get("name")))
