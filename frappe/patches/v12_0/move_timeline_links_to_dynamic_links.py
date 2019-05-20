from __future__ import unicode_literals

import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'communication')

	communications = frappe.db.sql("""
			SELECT
				`tabCommunication`.name, `tabCommunication`.creation, `tabCommunication`.modified,
				`tabCommunication`.modified_by,`tabCommunication`.timeline_doctype, `tabCommunication`.timeline_name,
				`tabCommunication`.link_doctype, `tabCommunication`.link_name
			FROM `tabCommunication`
			WHERE `tabCommunication`.communication_medium='Email'
		""", as_dict=True)

	for count, communication in enumerate(communications):
		counter = 1
		if communication.timeline_doctype and communication.timeline_name:
			values = [
				counter, frappe.generate_hash(length=10), 'timeline_links', 'Communication', communication.name,
				communication.timeline_doctype, communication.timeline_name, communication.creation, communication.modified,
				communication.modified_by
			]
			execute_query(values)
			counter += 1

		if communication.link_doctype and communication.link_name:
			values = [
				counter, frappe.generate_hash(length=10), 'timeline_links', 'Communication', communication.name,
				communication.link_doctype, communication.link_name, communication.creation, communication.modified,
				communication.modified_by
			]
			execute_query(values)

def execute_query(values):
	try:
		frappe.db.sql("""
			INSERT INTO `tabDynamic Link`
				(`idx`, `name`, `parentfield`, `parenttype`, `parent`, `link_doctype`, `link_name`, `creation`,
				`modified`, `modified_by`)
			VALUES ({0}, {1}, {2}, {3}, {4}, {5}, {6}, {7}, {8}, {9})
		""".format(values[0], values[1], values[2], values[3], values[4], values[5], values[6], values[7], values[8], values[9])
	except Exception as e:
		values[1] = frappe.generate_hash(length=10)
		execute_query(values)
