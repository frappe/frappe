# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.utils.background_jobs import enqueue
from frappe import _

@frappe.whitelist()
def add_subcription(doctype):
	if frappe.get_doc("DocType",doctype).track_changes == 1:
		print("------------------------------>>>>>>>>>>>>>>inside if")
	else:
		print("------------------------->>>>>>>>I am out")

@frappe.whitelist()
def get_message(doc_name, doctype):
	version = frappe.get_list("Version", filters = {"docname":doc_name},fields=["ref_doctype","data"])
	html = "\n<h4>Activity</h4>\n"
	changed_fields = ""
	for d in version:
		if isinstance(d.data, frappe.string_types):
			change = frappe._dict(json.loads(d.data))
			if change.comment:
				html += "<p>\n"+ change.comment
				html += "</p>\n"
			if change.changed:
				for d in change.changed:
					d[1] = d[1] if d[1] else " None "
					d[2] = d[2] if d[2] else " None "
					d[0] = d[0] if d[0] else "None"
					changed_fields += "<p>\n feilds: "+d[0]+" changed from \n"
					changed_fields += d[1] + " to \n"
					changed_fields += d[2] + "\n</p>"
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
def send_email_alert(doc_name,doctype):
	html = get_message(doc_name, doctype)
	receiver ="mishranaman123@gmail.com"
	if receiver:
		email_args = {
			"recipients": [receiver],
			"message": html,
			"subject": 'Documemt Follow {0}:{1}'.format(doctype,doc_name),
			"reference_doctype": doctype,
			"reference_name": doc_name,
			"delayed": False,
		}
		#frappe.sendmail(**email_args)
	enqueue(method=frappe.sendmail, now=True, queue='short', timeout=300, async=True, **email_args)
	frappe.db.commit()