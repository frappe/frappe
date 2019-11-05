import frappe

def execute():
	contact_details = frappe.db.sql("""
		SELECT
			`name`, `email_id`, `phone`, `mobile_no`, `modified_by`, `creation`, `modified`
		FROM `tabContact`
	""", as_dict=True)
	frappe.reload_doc("contacts", "doctype", "contact_email")
	frappe.reload_doc("contacts", "doctype", "contact_phone")
	frappe.reload_doc("contacts", "doctype", "contact")

	email_values = []
	phone_values = []
	for count, contact_detail in enumerate(contact_details):
		phone_counter = 1
		is_primary = 1

		if contact_detail.email_id:
			email_values.append((
				1,
				frappe.generate_hash(contact_detail.email_id, 10),
				contact_detail.email_id,
				'email_ids',
				'Contact',
				contact_detail.name,
				1,
				contact_detail.creation,
				contact_detail.modified,
				contact_detail.modified_by
			))

		if contact_detail.phone:
			is_primary_phone = 1 if phone_counter == 1 else 0
			phone_values.append((
				phone_counter,
				frappe.generate_hash(contact_detail.email_id, 10),
				contact_detail.phone,
				'phone_nos',
				'Contact',
				contact_detail.name,
				is_primary_phone,
				0,
				contact_detail.creation,
				contact_detail.modified,
				contact_detail.modified_by
			))
			phone_counter += 1

		if contact_detail.mobile_no:
			is_primary_mobile_no = 1 if phone_counter == 1 else 0
			phone_values.append((
				phone_counter,
				frappe.generate_hash(contact_detail.email_id, 10),
				contact_detail.mobile_no,
				'phone_nos',
				'Contact',
				contact_detail.name,
				0,
				is_primary_mobile_no,
				contact_detail.creation,
				contact_detail.modified,
				contact_detail.modified_by
			))

		if email_values and (count%10000 == 0 or count == len(contact_details)-1):
			frappe.db.sql("""
				INSERT INTO `tabContact Email`
					(`idx`, `name`, `email_id`, `parentfield`, `parenttype`, `parent`, `is_primary`, `creation`,
					`modified`, `modified_by`)
				VALUES {}
			""".format(", ".join(['%s'] * len(email_values))), tuple(email_values))

			email_values = []

		if phone_values and (count%10000 == 0 or count == len(contact_details)-1):
			frappe.db.sql("""
				INSERT INTO `tabContact Phone`
					(`idx`, `name`, `phone`, `parentfield`, `parenttype`, `parent`, `is_primary_phone`, `is_primary_mobile_no`, `creation`,
					`modified`, `modified_by`)
				VALUES {}
			""".format(", ".join(['%s'] * len(phone_values))), tuple(phone_values))

			phone_values = []

	frappe.db.add_index("Contact Phone", ["phone"])
	frappe.db.add_index("Contact Email", ["email_id"])