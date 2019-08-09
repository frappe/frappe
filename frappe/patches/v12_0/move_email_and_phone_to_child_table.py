import frappe

def execute():
	contact_details = frappe.get_list("Contact", fields=["name", "email_id", "phone", "mobile_no", "modified_by", "creation", "modified"])
	frappe.reload_doc("contacts", "doctype", "contact_email")
	frappe.reload_doc("contacts", "doctype", "contact_phone")
	frappe.reload_doc("contacts", "doctype", "contact")

	name_counter = 100000000
	for contact_detail in contact_details:
		if contact_detail.email_id:
			frappe.db.sql("""
				INSERT INTO `tabContact Email`
					(`idx`, `name`, `email_id`, `parentfield`, `parenttype`, `parent`, `is_primary`, `creation`, `modified`, `modified_by`)
				VALUES ("1", {0}, {1}, "email_ids", "Contact Email", {2}, "1", {3}, {4}, {5})
			""".format(name_counter, contact_detail.email_id, contact_detail.creation, contact_detail.modified, contact_detail.modified_by))
			name_counter += 1

		if contact_detail.phone:
			frappe.db.sql("""
				INSERT INTO `tabContact Phone`
					(`idx`, `name`, `phone`, `parentfield`, `parenttype`, `parent`, `is_primary`, `creation`, `modified`, `modified_by`)
				VALUES ("1", {0}, {1}, "email_ids", "Contact Email", {2}, "1", {3}, {4}, {5})
			""".format(name_counter, contact_detail.phone, contact_detail.creation, contact_detail.modified, contact_detail.modified_by))
			name_counter += 1

		if contact_detail.mobile_no:
			frappe.db.sql("""
				INSERT INTO `tabContact Phone`
					(`idx`, `name`, `phone`, `parentfield`, `parenttype`, `parent`, `is_primary`, `creation`, `modified`, `modified_by`)
				VALUES ("1", {0}, {1}, "email_ids", "Contact Email", {2}, "0", {3}, {4}, {5})
			""".format(name_counter, contact_detail.mobile_no, contact_detail.creation, contact_detail.modified, contact_detail.modified_by))
			name_counter += 1