import frappe

def execute():
	if not 'tabError Log' in frappe.db.get_tables():
		frappe.rename_doc('DocType', 'Scheduler Log', 'Error Log')
		frappe.db.commit()
		frappe.db.sql('alter table `tabError Log` engine=MyISAM')