from __future__ import unicode_literals
import frappe

def execute():
	for name in frappe.db.sql_list("""select name from `tabToDo`
		where ifnull(reference_type, '')!='' and ifnull(reference_name, '')!=''"""):
		try:
			frappe.get_doc("ToDo", name).on_update()
		except Exception as e:
			if e.args[0]!=1146:
				raise
