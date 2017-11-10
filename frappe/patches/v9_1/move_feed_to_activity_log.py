import frappe

def execute():
	frappe.reload_doc("core", "doctype", "communication")
	frappe.reload_doc("core", "doctype", "activity_log")

	communication_data = frappe.get_all('Communication', filters= {'comment_type': 'Updated'})
	activity_log_fields = frappe.get_meta('Activity Log').fields

	for d in communication_data:
		communication_doc = frappe.get_doc('Communication', d)

		activity_data = {'doctype': 'Activity Log'}
		for field in activity_log_fields:
			if communication_doc.get(field.fieldname):
				activity_data[field.fieldname] = communication_doc.get_value(field.fieldname)

		activity_data['creation'] = communication_doc.creation
		activity_data['modified'] = communication_doc.modified

		activity_doc = frappe.get_doc(activity_data)
		activity_doc.insert()

		# frappe.db.set_value('Activity Log', activity_doc.name, 'creation', communication_doc.creation)
		# frappe.db.set_value('Activity Log', activity_doc.name, 'modified', communication_doc.modified)
		frappe.db.sql("""delete from `tabCommunication` where name='{0}'""".format(communication_doc.name))

	frappe.delete_doc("DocType", "Authentication Log")
