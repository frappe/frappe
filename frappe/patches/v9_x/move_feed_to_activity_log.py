import frappe

def execute():
	frappe.reload_doc("core", "doctype", "communication")
	frappe.reload_doc("core", "doctype", "activity_log")

	communication_data = frappe.get_all('Communication', filters= {'comment_type': 'Updated'})
	activity_log_field = frappe.get_meta('Activity Log').fields

	for d in communication_data:
		communication_doc = frappe.get_doc('Communication', d)

		activity_data = {'doctype': 'Activity Log'}
		for x in activity_log_field:
			activity_data[x.fieldname] = communication_doc.get_value(x.fieldname)

		activity_doc = frappe.get_doc(activity_data)
		activity_doc.insert()

		creation = frappe.db.get_value('Communication', {'name': d.name}, 'creation')
		modified = frappe.db.get_value('Communication', {'name': d.name}, 'modified')

		frappe.db.set_value('Activity Log', activity_doc.name, 'creation', creation)
		frappe.db.set_value('Activity Log', activity_doc.name, 'modified', modified)
		frappe.db.sql("""delete from `tabCommunication` where name='{0}'""".format(communication_doc.name))
