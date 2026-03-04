import frappe

LINK_FIELD_DATA = [
	{"doctype_name": "User", "link_fieldname": "user", "display_fieldname": "user_full_name"},
]


def execute():
	link_formatter = frappe.get_single("Link Formatter")

	for data in LINK_FIELD_DATA:
		exists = any(
			row.doctype_name == data["doctype_name"] and row.link_fieldname == data["link_fieldname"]
			for row in link_formatter.link_field_display
		)

		if not exists:
			link_formatter.append("link_field_display", data)

	link_formatter.save()
