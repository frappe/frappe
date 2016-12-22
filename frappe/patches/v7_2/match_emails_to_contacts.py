from __future__ import unicode_literals
import frappe
def execute():
	frappe.db.sql("update `tabContact` set email_id = lower(email_id)")
	frappe.db.sql("update `tabCommunication` set sender = lower(sender),recipients = lower(recipients)")


	origin_contact = frappe.db.sql("select name,email_id,supplier,supplier_name,customer,customer_name,user,organisation from `tabContact` where email_id <>''",as_dict=1)
	origin_communication = frappe.db.sql("select name, sender,recipients,sent_or_received from `tabCommunication` where communication_type = 'Communication'",as_dict=1)

	for communication in origin_communication:
		# format contacts
		for comm in origin_contact:
			if (communication.sender and communication.sent_or_received == "Received" and communication.sender.find(comm.email_id) > -1) \
				or (communication.recipients !=None and communication.sent_or_received == "Sent" and communication.recipients.find(comm.email_id) > -1):
				if sum(1 for x in [comm.supplier, comm.customer, comm.user,comm.organisation] if x) > 1:
					frappe.db.sql("""update `tabCommunication`
							set timeline_doctype = %(timeline_doctype)s,
							timeline_name = %(timeline_name)s,
							timeline_label = %(timeline_label)s
							where name = %(name)s""", {
						"timeline_doctype": "Contact",
						"timeline_name": comm.name,
						"timeline_label": comm.name,
						"name": communication.name
					})

				elif comm.supplier:
					frappe.db.sql("""update `tabCommunication`
							set timeline_doctype = %(timeline_doctype)s,
							timeline_name = %(timeline_name)s,
							timeline_label = %(timeline_label)s
							where name = %(name)s""", {
						"timeline_doctype": "Supplier",
						"timeline_name": comm.supplier,
						"timeline_label": comm.supplier_name,
						"name": communication.name
					})

				elif comm.customer:
					frappe.db.sql("""update `tabCommunication`
							set timeline_doctype = %(timeline_doctype)s,
							timeline_name = %(timeline_name)s,
							timeline_label = %(timeline_label)s
							where name = %(name)s""", {
						"timeline_doctype": "Customer",
						"timeline_name": comm.customer,
						"timeline_label": comm.customer_name,
						"name": communication.name
					})
				elif comm.user:
					frappe.db.sql("""update `tabCommunication`
							set timeline_doctype = %(timeline_doctype)s,
							timeline_name = %(timeline_name)s,
							timeline_label = %(timeline_label)s
							where name = %(name)s""", {
						"timeline_doctype": "User",
						"timeline_name": comm.user,
						"timeline_label": comm.user,
						"name": communication.name
					})
				elif comm.organisation:
					frappe.db.sql("""update `tabCommunication`
							set timeline_doctype = %(timeline_doctype)s,
							timeline_name = %(timeline_name)s,
							timeline_label = %(timeline_label)s
							where name = %(name)s""", {
						"timeline_doctype": "Organisation",
						"timeline_name": comm.organisation,
						"timeline_label": comm.organisation,
						"name": communication.name
					})