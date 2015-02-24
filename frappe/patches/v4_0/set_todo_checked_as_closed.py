from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "todo")
	try:
		frappe.db.sql("""update tabToDo set status = if(ifnull(checked,0)=0, 'Open', 'Closed')""")
	except:
		pass
