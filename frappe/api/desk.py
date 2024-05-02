import frappe
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
def get_links_for_workspace(workspace: str) -> dict[list]:
	"""Returns doctypes that are allowed to be shown in the workspace"""
	WorkspaceLink = frappe.qb.DocType("Workspace Link")
	workspace_links = (
		frappe.qb.from_(WorkspaceLink)
		.select("link_type", "link_to", "label")
		.distinct()
		.where((WorkspaceLink.parent == workspace) & (WorkspaceLink.type == "Link"))
		.orderby(WorkspaceLink.label, order=Order.asc)
	).run(as_dict=True)

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
