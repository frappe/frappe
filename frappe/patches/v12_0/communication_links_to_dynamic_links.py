from __future__ import unicode_literals

import frappe
from frappe.core.doctype.communication.email import add_contacts

def execute():
	for communication in frappe.get_list("Communication"):
		comm = frappe.get_doc("Communication", communication.name)
		if comm.reference_doctype and comm.reference_name:
			comm.add_link(comm.reference_doctype, comm.reference_name)
		if comm.timeline_doctype and comm.timeline_name:
			comm.add_link(comm.timeline_doctype, comm.timeline_name)
		if comm.link_doctype and comm.link_name:
			comm.add_link(comm.link_doctype, comm.link_name)
		contacts = add_contacts([comm.sender, comm.recipients, comm.cc, comm.bcc])
		for contact_name in contacts:
			comm.add_link('Contact', contact_name)
		comm.save(ignore_permissions=True)