import frappe


def execute() -> None:
	frappe.reload_doc("website", "doctype", "web_page_view", force=True)
	frappe.db.sql("""UPDATE `tabWeb Page View` set path='/' where path=''""")
