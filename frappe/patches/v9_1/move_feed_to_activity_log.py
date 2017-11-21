import frappe

def execute():
	frappe.reload_doc("core", "doctype", "communication")
	frappe.reload_doc("core", "doctype", "activity_log")

	communication_data = frappe.get_all('Communication', filters= {'comment_type': 'Updated'})
	activity_log_fields = frappe.get_meta('Activity Log').fields

	for d in communication_data:
		try:
			communication_doc = frappe.get_doc('Communication', d)

			activity_data = {'doctype': 'Activity Log'}
			for field in activity_log_fields:
				if communication_doc.get(field.fieldname):
					activity_data[field.fieldname] = communication_doc.get_value(field.fieldname)

			activity_doc = frappe.get_doc(activity_data)
			activity_doc.insert()

			frappe.db.sql("""update `tabActivity Log` set creation = %s,\
				modified = %s where name = %s""", (communication_doc.creation,communication_doc.modified,activity_doc.name))

			frappe.db.sql("""delete from `tabCommunication` where name='{0}'""".format(communication_doc.name))

		except frappe.LinkValidationError:
			pass
	frappe.delete_doc("DocType", "Authentication Log")
