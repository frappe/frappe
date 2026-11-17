import os

import frappe
from frappe import _
from frappe.utils import escape_html

SCHEMA_FOLDER = ("studio", "frontend", "src", "json_types")


def get_component_definition(component: str) -> dict:
	"""Return the JSON schema of a built-in component's props, which the editor also uses."""
	path = get_schema_files().get(component)
	if not path:
		frappe.throw(
			_(
				"Studio has no prop definition for {0}. Component names are case sensitive. Some components that work only inside another one, such as SidebarItem, have no definition."
			).format(frappe.bold(escape_html(component))),
			title=_("No definition"),
		)
	return frappe.get_file_json(path)


def get_schema_files() -> dict[str, str]:
	"""Map each component that has a schema to the path of its file."""
	folder = frappe.get_app_source_path("frappe", *SCHEMA_FOLDER)
	return {
		file_name.removesuffix(".json"): os.path.join(folder, library, file_name)
		for library in sorted(os.listdir(folder))
		if os.path.isdir(os.path.join(folder, library))
		for file_name in os.listdir(os.path.join(folder, library))
		if file_name.endswith(".json")
	}
