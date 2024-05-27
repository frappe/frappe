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


@frappe.whitelist()
def get_module_sidebar(module: str) -> dict:
	"""Returns user specfic/global sidebar for a module"""
	sidebar = frappe.db.exists("Module Sidebar", {"module": module, "for_user": frappe.session.user})

	if not sidebar:
		sidebar = frappe.db.exists("Module Sidebar", {"module": module, "for_user": ("is", "Not Set")})

	doc = frappe.get_cached_doc("Module Sidebar", sidebar)

	sections = []
	current_section = None
	# first link in the sidebar
	module_home = None

	if doc.workspaces:
		module_home = frappe._dict(
			{
				"workspace": doc.workspaces[0].workspace,
			}
		)

	for item in doc.items:
		item = item.as_dict()
		if item.type == "Spacer":
			sections.append(item)
			current_section = None
		elif item.type == "Section Break":
			current_section = frappe._dict(item)
			current_section["links"] = []
			sections.append(current_section)
		elif item.type == "Link":
			if current_section:
				current_section["links"].append(item)
			else:
				sections.append(item)

			if not module_home:
				module_home = item

	return frappe._dict(
		{
			"workspaces": doc.workspaces,
			"sections": sections,
			"module": module,
			"module_home": module_home,
			"name": doc.name,
		}
	)


@frappe.whitelist()
def save_module_sidebar(name: str, workspaces: list[dict], sections: list[dict]) -> None:
	"""Update module sidebar"""
	doc = frappe.get_doc("Module Sidebar", name)
	doc.workspaces = []
	doc.items = []

	def append_item(item):
		doc.append(
			"items",
			{
				"type": item.get("type"),
				"label": item.get("label"),
				"icon": item.get("icon"),
				"link_type": item.get("link_type"),
				"link_to": item.get("link_to"),
			},
		)

	for workspace in workspaces:
		doc.append(
			"workspaces",
			{
				"workspace": workspace.get("workspace"),
				"icon": workspace.get("icon"),
				"label": workspace.get("label"),
			},
		)

	for section in sections:
		if section.get("type") in ["Link", "Spacer"]:
			append_item(section)

		elif section.get("type") == "Section Break":
			doc.append(
				"items",
				{
					"type": "Section Break",
					"label": section.get("label"),
				},
			)
			for item in section.get("links"):
				append_item(item)

	doc.save()
