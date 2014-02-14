import frappe

def execute():
	if frappe.conn.exists("Website Sitemap", "index"):
		frappe.delete_doc("Website Sitemap", "index", ignore_permissions=True)
	