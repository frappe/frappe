import frappe


def execute():
	frappe.reload_doc("website", "doctype", "web_page_view", force=True)
	site_url = frappe.utils.get_url()
	frappe.db.sql(f"""UPDATE `tabWeb Page View` set is_unique=1 where referrer LIKE '%{site_url}%'""")
