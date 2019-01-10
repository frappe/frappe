# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.utils.background_jobs import enqueue
from frappe import _

@frappe.whitelist()
def add_subcription(doctype, doc_name, user_email):
	if len(frappe.get_list("Document Follow", filters={'ref_doctype': doctype, 'ref_docname': doc_name, 'user': user_email})) == 0:
		if user_email != "Administrator":
			doc = frappe.new_doc("Document Follow")
			doc.update({
				"ref_doctype": doctype,
				"ref_docname": doc_name,
				"user": user_email
			})
			doc.save()

@frappe.whitelist()
def get_message(doc_name, doctype):
	version = frappe.get_list("Version", filters = [["docname","=",doc_name],["modified","like","%"+frappe.utils.nowdate()+"%"]],fields=["ref_doctype","data"])
	if version:
		html = ""
		activity = ""
		changed_fields = ""
		for d in version:
			if isinstance(d.data, frappe.string_types):
				change = frappe._dict(json.loads(d.data))
				if change.comment:
					activity += "<p>\n"+ change.comment
					activity += "</p>\n"
				if change.changed:
					for d in change.changed:
						d[1] = d[1] if d[1] else " None "
						d[2] = d[2] if d[2] else " None "
						d[0] = d[0] if d[0] else "None"
						changed_fields += "<p>\n"+d[0]+" changed from \n"
						changed_fields += d[1] + " to \n"
						changed_fields += d[2] + "\n</p>"
		if activity != "":
			html += '\n<h4>Activity</h4>\n' + activity
		if changed_fields != "":
			html += '\n<h4>Changed fields</h4>\n' + changed_fields

	doc = frappe.get_doc(doctype, doc_name)
	if doc._comments:
		html += "<h4>Comments</h4>\n"
		com = json.loads(doc._comments)
		for comment in com:
			dictio = frappe._dict(comment)
			html += dictio.comment + "\n<p> By: "
			html += dictio.by + "</p>\n"
	return html

@frappe.whitelist()
def sent_email_alert(doc_name, doctype, receiver, message):
	if receiver:
		email_args = {
			"recipients": [receiver],
			"message": message,
			"subject": 'Documemt Follow {0}:{1}'.format(doctype,doc_name),
			"reference_doctype": doctype,
			"reference_name": doc_name,
			"delayed": False,
		}
		#frappe.sendmail(**email_args)
	enqueue(method=frappe.sendmail, now=True, queue='short', timeout=300, async=True, **email_args)
	frappe.db.commit()

def sending_mail():
	data = frappe.get_list("Document Follow", fields = ["ref_doctype","ref_docname","user"])
	for d in data:
		message = get_message(d.ref_docname, d.ref_doctype)
		if message != "":
			sent_email_alert(d.ref_docname, d.ref_doctype, d.user, message)
