from __future__ import unicode_literals

import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'communication')

	communications = frappe.db.sql("""
						Select
							`tabCommunication`.name, `tabCommunication`.creation, `tabCommunication`.modified,
							`tabCommunication`.modified_by,`tabCommunication`.timeline_doctype, `tabCommunication`.timeline_name,
							`tabCommunication`.link_doctype, `tabCommunication`.link_name
						from `tabCommunication`
						where `tabCommunication`.communication_medium='Email'
					""", as_dict=True)

	values = []

	for count, communication in enumerate(communications):
		counter = 1
		if communication.timeline_doctype and communication.timeline_name:
			values.append("""({0}, '{1}', 'timeline_links', 'Communication', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}')""".format(
				counter, frappe.generate_hash(length=10), communication.name, communication.timeline_doctype,
				communication.timeline_name, communication.creation, communication.modified, communication.modified_by
			))
			counter += 1
		if communication.link_doctype and communication.link_name:
			values.append("""({0}, '{1}', 'timeline_links', 'Communication', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}')""".format(
				counter, frappe.generate_hash(length=10), communication.name, communication.link_doctype,
				communication.link_name, communication.creation, communication.modified, communication.modified_by
			))
		if count % 1000 == 0 or count == len(communications) - 1:
			frappe.db.sql("""
				INSERT INTO `tabDynamic Link`
					(`idx`, `name`, `parentfield`, `parenttype`, `parent`, `link_doctype`, `link_name`, `creation`,
					`modified`, `modified_by`)
				VALUES {0}
			""".format(", ".join([d for d in values])))
			values = []