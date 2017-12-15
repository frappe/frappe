import frappe

def execute():
	for t in frappe.db.sql('show table status'):
		if t[0].startswith('tab'):
			frappe.db.sql('update tabDocType set engine=%s where name=%s', (t[1], t[0][3:]))