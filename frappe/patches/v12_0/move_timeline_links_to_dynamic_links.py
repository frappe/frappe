from __future__ import unicode_literals

import frappe

def execute():
	comm_lists = []
	for communication in frappe.db.sql("""
				Select
					`tabCommunication`.name, `tabCommunication`.creation, `tabCommunication`.modified,
					`tabCommunication`.modified_by,`tabCommunication`.timeline_doctype, `tabCommunication`.timeline_name,
					`tabCommunication`.link_doctype, `tabCommunication`.link_name
				from `tabCommunication`
				where `tabCommunication`.communication_medium='Email'
			""", as_dict=True):
		counter = 1
		if communication.timeline_doctype and communication.timeline_name:
			comm_lists.append(
				{
					"idx": counter,
					"name": frappe.generate_hash(length=10),
					"parentfield": "timeline_links",
					"parenttype": "Communication",
					"parent": communication.name,
					"link_doctype": communication.timeline_doctype,
					"link_name": communication.timeline_name,
					"creation": communication.creation,
					"modified": communication.modified,
					"modified_by": communication.modified_by
				}
			)
			counter += 1

		if communication.link_doctype and communication.link_name:
			comm_lists.append(
				{
					"idx": counter,
					"name": frappe.generate_hash(length=10),
					"parentfield": "timeline_links",
					"parenttype": "Communication",
					"parent": communication.name,
					"link_doctype": communication.link_doctype,
					"link_name": communication.link_name,
					"creation": communication.creation,
					"modified": communication.modified,
					"modified_by": communication.modified_by
				}
			)

	for comm_list in comm_lists:
		frappe.db.sql("""
			INSERT INTO `tabDynamic Link`
				(`idx`, `name`, `parentfield`, `parenttype`, `parent`, `link_doctype`, `link_name`, `creation`,
				`modified`, `modified_by`)
			VALUES
				(%(idx)s, %(name)s, %(parentfield)s, %(parenttype)s, %(parent)s, %(link_doctype)s, %(link_name)s,%(creation)s,
				%(modified)s, %(modified_by)s)
		""",{
			"idx": comm_list.get("idx"),
			"name": comm_list.get("name"),
			"parentfield": comm_list.get("parentfield"),
			"parenttype": comm_list.get("parenttype"),
			"parent": comm_list.get("parent"),
			"link_doctype": comm_list.get("link_doctype"),
			"link_name": comm_list.get("link_name"),
			"creation": comm_list.get("creation"),
			"modified": comm_list.get("modified"),
			"modified_by": comm_list.get("modified_by")
		})