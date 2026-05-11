from frappe.model.sync import remove_orphan_entities
from frappe.utils.install import auto_generate_icons_and_sidebar


def execute():
	"""Auto Create desktop icons and workspace sidebars."""
	remove_orphan_entities("Workspace")
	auto_generate_icons_and_sidebar()
