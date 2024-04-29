import frappe


@frappe.whitelist()
def get_current_user_info() -> dict:
	current_user = frappe.session.user
	user = frappe.get_cached_value(
		"User", current_user, ["name", "first_name", "full_name", "user_image"], as_dict=True
	)
	user["roles"] = frappe.get_roles(current_user)

	return user


@frappe.whitelist()
def get_links_for_workspace(workspace: str) -> dict[list]:
	"""Returns doctypes that are allowed to be shown in the workspace"""
	workspace_links = frappe.get_all(
		"Workspace Link",
		{"parent": workspace, "type": "Link"},
		["link_type", "link_to", "label"],
		order_by="link_to asc",
	)

	links = {
		"Document Types": [],
		"Reports": [],
		"Pages": [],
	}

	for item in workspace_links:
		if item.link_type == "DocType":
			links["Document Types"].append(item)
		elif item.link_type == "Report":
			links["Reports"].append(item)
		elif item.link_type == "Page":
			links["Pages"].append(item)

	return links
