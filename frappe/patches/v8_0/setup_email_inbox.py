import frappe, json

def execute():
	""" 
		depricate email inbox page if exists
		remove desktop icon for email inbox page if exists
		patch to remove Custom DocPerm for communication
	"""

	if frappe.db.exists("Page", "email_inbox"):
		frappe.delete_doc("Page", "email_inbox")

	desktop_icon = frappe.db.get_value("Desktop Icon", {
		"module_name": "Email",
		"type": "Page",
		"link": "email_inbox"
	})

	if desktop_icon:
		frappe.delete_doc("Desktop Icon", desktop_icon)

	frappe.db.sql("""update `tabCustom DocPerm` set `write`=0, email=1 where parent='Communication'""")