import frappe

def execute():
	for name in frappe.db.sql_list("""select name from `tabToDo`
		where ifnull(reference_type, '')!='' and ifnull(reference_name, '')!=''"""):
		frappe.get_doc("ToDo", name).on_update()
