
import frappe

def execute():
	frappe.db.delete("DocType", {
		"name": "Feedback Request"
	})
	# frappe.db.sql('''
	#DELETE from `tabDocType`
	#WHERE name = 'Feedback Request'
	# ''')