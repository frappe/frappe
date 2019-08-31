import frappe

def execute():
	contact_details = frappe.get_list("Contact", fields=["name", "email_id", "phone", "mobile_no", "modified_by", "creation", "modified"])
	frappe.reload_doc("contacts", "doctype", "contact_email")
	frappe.reload_doc("contacts", "doctype", "contact_phone")
	frappe.reload_doc("contacts", "doctype", "contact")

	for contact_detail in contact_details:
		contact_name = frappe.db.escape(contact_detail.name)

		if contact_detail.email_id:
			frappe.db.sql("""
				INSERT INTO `tabContact Email`
					(`idx`, `name`, `email_id`, `parentfield`, `parenttype`, `parent`, `is_primary`, `creation`, `modified`, `modified_by`)
				VALUES (1, '{0}', '{1}', 'email_ids', 'Contact', {2}, 1, '{3}', '{4}', '{5}')
			""".format(frappe.generate_hash(contact_detail.email_id, 10), contact_detail.email_id, contact_name, contact_detail.creation, contact_detail.modified, contact_detail.modified_by))

		if contact_detail.phone:
			frappe.db.sql("""
				INSERT INTO `tabContact Phone`
					(`idx`, `name`, `phone`, `parentfield`, `parenttype`, `parent`, `is_primary`, `creation`, `modified`, `modified_by`)
				VALUES (1, '{0}', '{1}', 'phone_nos', 'Contact', {2}, 1, '{3}', '{4}', '{5}')
			""".format(frappe.generate_hash(contact_detail.phone, 10), contact_detail.phone, contact_name, contact_detail.creation, contact_detail.modified, contact_detail.modified_by))

		if contact_detail.mobile_no:
			frappe.db.sql("""
				INSERT INTO `tabContact Phone`
					(`idx`, `name`, `phone`, `parentfield`, `parenttype`, `parent`, `is_primary`, `creation`, `modified`, `modified_by`)
				VALUES (2, '{0}', '{1}', 'phone_nos', 'Contact', {2}, 0, '{3}', '{4}', '{5}')
			""".format(frappe.generate_hash(contact_detail.mobile_no, 10), contact_detail.mobile_no, contact_name, contact_detail.creation, contact_detail.modified, contact_detail.modified_by))