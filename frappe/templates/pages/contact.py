# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import frappe
from frappe.utils import now

def get_context(context):
	bean = frappe.bean("Contact Us Settings", "Contact Us Settings")
	
	query_options = filter(None, bean.doc.query_options.replace(",", "\n").split()) if \
			bean.doc.query_options else ["Sales", "Support", "General"]
			
	address = frappe.bean("Address", bean.doc.address).doc if bean.doc.address else None
	
	out = {
		"query_options": query_options
	}
	out.update(bean.doc.fields)
	
	return out
	
max_communications_per_hour = 300

@frappe.whitelist(allow_guest=True)
def send_message(subject="Website Query", message="", sender=""):
	if not message:
		frappe.response["message"] = 'Please write something'
		return
		
	if not sender:
		frappe.response["message"] = 'Email Id Required'
		return
		
	# guest method, cap max writes per hour
	if frappe.db.sql("""select count(*) from `tabCommunication`
		where TIMEDIFF(%s, modified) < '01:00:00'""", now())[0][0] > max_communications_per_hour:
		frappe.response["message"] = "Sorry: we believe we have received an unreasonably high number of requests of this kind. Please try later"
		return
	
	# send email
	forward_to_email = frappe.db.get_value("Contact Us Settings", None, "forward_to_email")
	if forward_to_email:
		from frappe.utils.email_lib import sendmail
		sendmail(forward_to_email, sender, message, subject)
	
	return "okay"