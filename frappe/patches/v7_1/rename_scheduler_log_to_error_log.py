import frappe

def execute():
	if not 'tabError Log' in frappe.db.get_tables():
		frappe.rename_doc('DocType', 'Scheduler Log', 'Error Log')
		frappe.db.sql("""delete from `tabError Log` where datediff(curdate(), creation) > 30""")
		frappe.db.commit()
		frappe.db.sql('alter table `tabError Log` change column name name varchar(140)')
		frappe.db.sql('alter table `tabError Log` change column parent parent varchar(140)')
		frappe.db.sql('alter table `tabError Log` engine=MyISAM')
