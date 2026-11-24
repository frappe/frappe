"""Global Studio components on desk. Desk renders one through the `frappe.studio.component`
island. A workspace is one too: see `frappe.desk.workspace_component`.

A component is client code, like the script of a desk page. So every desk user can load a global
component, and the data that it fetches is checked against that user's permissions."""

import frappe
from frappe import _
from frappe.studio.doctype.studio_component.studio_component import get_components_for_blocks

GLOBAL_COMPONENTS = {"studio_app": ("is", "not set"), "is_disabled": 0}


@frappe.whitelist(methods=["GET"])
def get_desk_component(component_id: str) -> list[dict]:
	"""A global component, and after it the components that its blocks use."""
	validate_desk_user()
	block = {"isStudioComponent": True, "componentName": component_id}
	components = get_components_for_blocks([block])
	is_found = components and components[0].component_id == component_id and not components[0].is_disabled
	# a workspace's root loads through the workspace, which checks who can open it
	if not is_found or component_id in get_root_component_ids():
		frappe.throw(
			_("Component {0} not found").format(frappe.bold(frappe.utils.escape_html(component_id))),
			frappe.DoesNotExistError,
		)
	return components


@frappe.whitelist(methods=["GET"])
def get_desk_components() -> list[dict]:
	"""The components that a user can add to a desk page."""
	validate_desk_user()
	return frappe.get_all(
		"Studio Component",
		filters={**GLOBAL_COMPONENTS, "name": ("not in", get_root_component_ids())},
		fields=["component_id", "component_name", "is_standard"],
		order_by="component_name asc",
	)


def get_root_component_ids() -> list[str]:
	from frappe.desk.workspace_component import get_root_component_ids

	return get_root_component_ids()


def validate_desk_user():
	if frappe.get_cached_value("User", frappe.session.user, "user_type") != "System User":
		frappe.throw(_("Only desk users can load a desk component."), frappe.PermissionError)
