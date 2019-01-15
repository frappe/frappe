# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
import frappe.utils
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
	version = frappe.get_list("Version", filters = [["docname","=",doc_name],["modified","like","%"+frappe.utils.nowdate()+"%"]],fields=["ref_doctype","data","modified"])
	html = ""
	message = ""
	if version:
		for d1 in version:
			if isinstance(d1.data, frappe.string_types):
				change = frappe._dict(json.loads(d1.data))
				#print(change)
				time = frappe.utils.format_datetime(d1.modified,"hh:mm a")
				if change.comment:
					html += "<li> "+"<span style ='color:#8d99a6!important'>"+time+ ": </span>"
					html += change.comment + "</li>"
				if change.changed:
					for d in change.changed:
						d[1] = d[1] if d[1] else " None "
						d[2] = d[2] if d[2] else " None "
						d[0] = d[0] if d[0] else "None"
						html += "<li><span style ='color:#8d99a6!important'>Field " +time +": </span>"+d[0]+" changed from "
						html += d[1] + " to "
						html += d[2] + "</li>"
				if change.row_changed:
					for d in change.row_changed:
						d[2] = d[2] if d[2] else " None "
						d[0] = d[0] if d[0] else "None"
						d[3][0][1] = d[3][0][1] if d[3][0][1] else "None"
						html += "<li><span style ='color:#8d99a6!important'>" +time +": </span> Table Field: "+d[0]+" Row# "
						html += str(d[1]) + " Field: "
						html += d[3][0][0] + " Changed from " + d[3][0][1] + " to " + d[3][0][2] + "</li>"
				if change.added:
					for d in change.added:
						html += "<li><span style ='color:#8d99a6!important'>" +time +": </span>Row Added to Table Field "+d[0]

	comments = frappe.db.get_value(doctype, doc_name, "_comments")
	if comments:
		com = json.loads(comments)
		for comment in com:
			dictio = frappe._dict(comment)
			if len(frappe.get_list("Communication", filters = [["name","=",dictio.name],["modified","like","%"+frappe.utils.nowdate()+"%"]])) != 0:
				modified = frappe.db.get_value("Communication", dictio.name, "modified")
				print(dictio.comment)
				time = frappe.utils.format_datetime(modified,"hh:mm a")
				html += "<li><span style ='color:#8d99a6!important'>" +time +": </span>"+ dictio.comment + " By: "
				html += dictio.by + "</li>"

		if html != "":
			message += "<ul style='list-style-type: none;'>" + html+ '</ul>'
	return message

@frappe.whitelist()
def sent_email_alert(doc_name, doctype, receiver, message):
	if receiver:
		email_args = {
			"recipients": [receiver],
			"message": message,
			"subject": 'Document Follow Notification',
			"reference_doctype": doctype,
			"reference_name": doc_name,
			"delayed": False,
		}
		#frappe.sendmail(**email_args)
	enqueue(method=frappe.sendmail, now=True, queue='short', timeout=300, async=True, **email_args)
	frappe.db.commit()

def sending_mail():
	users = frappe.get_all("Document Follow", distinct=1, fields=["user"])
	#data = frappe.get_list("Document Follow", fields = ["user"])
	for d in users:
		data = frappe.get_all("Document Follow", filters={"user" : d.user}, distinct=1, fields=["ref_doctype","ref_docname"])
		message = ""
		for d2 in data:
			content = get_message(d2.ref_docname, d2.ref_doctype)
			if content != '':
				message += """<div style='margin-bottom: 20px; background-color: #fff; border: 1px solid transparent; border-radius: 4px; -webkit-box-shadow: 0 1px 1px rgba(0,0,0,.05); box-shadow: 0 1px 1px rgba(0,0,0,.05); border-color: #ddd;'>
					<div style='color: #333; background-color: #f5f5f5; border-color: #ddd; padding: 10px 15px; border-bottom: 1px solid transparent; border-top-left-radius: 3px; border-top-right-radius: 3px; color:#8d99a6!important'>{0} : {1} </div>
					<div style='padding: 15px; color:#36414C!important'> {2} </div>
				</div>""".format(d2.ref_doctype, d2.ref_docname, content)
		if message != "":
			sent_email_alert(d.ref_docname, d.ref_doctype, d.user, message)
