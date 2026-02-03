from frappe.utils.install import LINK_FIELD_DATA, add_link_field_formatters


def execute():
	add_link_field_formatters(LINK_FIELD_DATA)
