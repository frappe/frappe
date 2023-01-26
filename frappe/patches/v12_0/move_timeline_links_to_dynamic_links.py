import frappe


def execute():
	communications = frappe.db.sql(
		"""
		SELECT
			`tabCommunication`.name, `tabCommunication`.creation, `tabCommunication`.modified,
			`tabCommunication`.modified_by,`tabCommunication`.timeline_doctype, `tabCommunication`.timeline_name,
			`tabCommunication`.link_doctype, `tabCommunication`.link_name
		FROM `tabCommunication`
		WHERE `tabCommunication`.communication_medium='Email'
	""",
		as_dict=True,
	)

	name = 1000000000
	values = []

	for count, communication in enumerate(communications):
		counter = 1
		if communication.timeline_doctype and communication.timeline_name:
			name += 1
			values.append(
				"""({}, "{}", "timeline_links", "Communication", "{}", "{}", "{}", "{}", "{}", "{}")""".format(
					counter,
					str(name),
					frappe.db.escape(communication.name),
					frappe.db.escape(communication.timeline_doctype),
					frappe.db.escape(communication.timeline_name),
					communication.creation,
					communication.modified,
					communication.modified_by,
				)
			)
			counter += 1
		if communication.link_doctype and communication.link_name:
			name += 1
			values.append(
				"""({}, "{}", "timeline_links", "Communication", "{}", "{}", "{}", "{}", "{}", "{}")""".format(
					counter,
					str(name),
					frappe.db.escape(communication.name),
					frappe.db.escape(communication.link_doctype),
					frappe.db.escape(communication.link_name),
					communication.creation,
					communication.modified,
					communication.modified_by,
				)
			)

		if values and (count % 10000 == 0 or count == len(communications) - 1):
			frappe.db.sql(
				"""
				INSERT INTO `tabCommunication Link`
					(`idx`, `name`, `parentfield`, `parenttype`, `parent`, `link_doctype`, `link_name`, `creation`,
					`modified`, `modified_by`)
				VALUES {}
			""".format(
					", ".join([d for d in values])
				)
			)

			values = []

	frappe.db.add_index("Communication Link", ["link_doctype", "link_name"])
