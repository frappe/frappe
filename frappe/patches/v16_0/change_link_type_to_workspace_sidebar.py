import frappe


def execute():
	desktop_icons = frappe.get_all(
		"Desktop Icon",
		filters={
			"icon_type": "Link",
			"link_type": ["in", ["Workspace", "DocType"]],
		},
	)

	for icon in desktop_icons:
		icon_doc = frappe.get_doc("Desktop Icon", icon.name)
		if frappe.db.exists("Workspace Sidebar", icon.name):
			icon_doc.link_type = "Workspace Sidebar"
			icon_doc.link_to = icon.name
			icon_doc.save()

	frappe.db.commit()
