import frappe

def execute():
	frappe.reload_doc("core", "doctype", "todo")
	frappe.conn.sql("""update tabToDo set status = if(ifnull(checked,0)=0, 'Open', 'Closed')""")
