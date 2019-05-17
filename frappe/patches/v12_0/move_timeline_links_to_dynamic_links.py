from __future__ import unicode_literals

import frappe

def execute():
	comm_lists = []
	for communication in frappe.get_list("Communication", filters={"communication_medium": "Email"},
			fields=[
				"name", "creation", "modified", "modified_by",
				"timeline_doctype", "timeline_name",
				"link_doctype", "link_name"
			]):
		counter = 1
		if communication.timeline_doctype and communication.timeline_name:
			comm_lists.append((
				counter, frappe.generate_hash(length=10), "timeline_links", "Communication",
				communication.name, communication.timeline_doctype, communication.timeline_name,
				communication.creation, communication.modified, communication.modified_by
			))
			counter += 1

		if communication.link_doctype and communication.link_name:
			comm_lists.append((
				counter, frappe.generate_hash(length=10), "timeline_links", "Communication",
				communication.name, communication.link_doctype, communication.link_name,
				communication.creation, communication.modified, communication.modified_by
			))

	for comm_list in comm_lists:
		frappe.db.sql("""
			insert into table `tabDynamic Link` (idx, name, parentfield, parenttype, parent, link_doctype, link_name, creation, modified, modified_by)
			values %(values)s""",
		{
			"values": comm_list
		})