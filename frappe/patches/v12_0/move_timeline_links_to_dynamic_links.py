from __future__ import unicode_literals

import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'communication')

	sql_query =	"""INSERT INTO `tabDynamic Link`
					(`idx`, `name`, `parentfield`, `parenttype`, `parent`, `link_doctype`, `link_name`, `creation`,
					`modified`, `modified_by`)
				VALUES """

	communications = frappe.db.sql("""
						Select
							`tabCommunication`.name, `tabCommunication`.creation, `tabCommunication`.modified,
							`tabCommunication`.modified_by,`tabCommunication`.timeline_doctype, `tabCommunication`.timeline_name,
							`tabCommunication`.link_doctype, `tabCommunication`.link_name
						from `tabCommunication`
						where `tabCommunication`.communication_medium='Email'
					""", as_dict=True)

	for communication in communications:
		counter = 1
		if communication.timeline_doctype and communication.timeline_name:
			sql_query += str((
					counter, frappe.generate_hash(length=10), "timeline_links", "Communication", communication.name,
					communication.timeline_doctype, communication.timeline_name, communication.creation,
					communication.modified, communication.modified_by
				)) + """, """
			counter += 1

		if communication.link_doctype and communication.link_name:
			sql_query += str((
					counter, frappe.generate_hash(length=10), "timeline_links", "Communication", communication.name,
					communication.link_doctype, communication.link_name, communication.creation,
					communication.modified, communication.modified_by
			)) + """, """

	frappe.db.sql(sql_query)
