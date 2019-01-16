# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
import frappe.utils
from frappe.utils.background_jobs import enqueue
from frappe import _
from pprint import pprint


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
			return doc

def get_message(doc_name, doctype):
	html = get_version(doctype, doc_name) + get_comments(doctype, doc_name)
	t = sorted(html, key=lambda k: k['time'], reverse=True)
	return t

def sent_email_alert(doc_name, doctype, receiver, docinfo,timeline):
	if receiver:
		email_args = {
			'template' :'doc_subscription',
			'args' : {
				"docinfo" : docinfo,
				"timeline" : timeline,
			},
			"recipients": [receiver],
			"subject": 'Document Follow Notification',
			"reference_doctype": doctype,
			"reference_name": doc_name,
			"delayed": False,
		}
	enqueue(method=frappe.sendmail, now=True, queue='short', timeout=300, async=True, **email_args)
	frappe.db.commit()

def sending_mail():
	users = frappe.get_all("Document Follow", distinct=1, fields=["user"])
	message = []
	for d in users:
		data = frappe.get_all("Document Follow", filters={"user" : d.user}, distinct=1, fields=["ref_doctype","ref_docname","user"])
		message = []
		for d2 in data:
			content = get_message(d2.ref_docname, d2.ref_doctype)
			if content != []:
				message = message + content

		if message != []:
			sent_email_alert(d2.ref_docname, d2.ref_doctype, d.user, data, message)

def get_version(doctype,doc_name):
	timeline = []
	version = frappe.get_list("Version", filters = [["docname","=",doc_name],["modified","like","%"+frappe.utils.nowdate()+"%"]],fields=["ref_doctype","data","modified"])
	if version:
		for d1 in version:
			if isinstance(d1.data, frappe.string_types):
				change = frappe._dict(json.loads(d1.data))
				time = frappe.utils.format_datetime(d1.modified,"hh:mm a")
				if change.comment:
					timeline.append({
							"time": d1.modified,
							"content" : "<li><span style ='color:#8d99a6!important'>" + time + ": </span>" +change.comment + "</li>",
							"doctype" : doctype,
							"doc_name" : doc_name
						})
				if change.changed:
					for d in change.changed:
						d[1] = d[1] if d[1] else ' '
						d[2] = d[2] if d[2] else ' '
						d[0] = d[0] if d[0] else ' '
						timeline.append({
							"time": d1.modified,
							"content" : "<li><span style ='color:#8d99a6!important'>" +time +": </span>Field: <b>"+cleantext(d[0])+'</b> changed from <b>"' + cleantext(d[1]) + '"</b>  to <b>"' +cleantext(d[2]) + '"</b> </li>',
							"doctype" : doctype,
							"doc_name" : doc_name
						})
				if change.row_changed:
					for d in change.row_changed:
						d[2] = d[2] if d[2] else ' '
						d[0] = d[0] if d[0] else ' '
						d[3][0][1] = d[3][0][1] if d[3][0][1] else ' '
						timeline.append({
							"time": d1.modified,
							"content" : "<li><span style ='color:#8d99a6!important'>" +time +": </span> Table Field: <b>"+d[0]+"</b> Row# " + str(d[1]) + " Field: <b>" +cleantext(d[3][0][0]) + '</b> changed from <b>"' + cleantext(d[3][0][1]) + '"</b>  to <b>"' + cleantext(d[3][0][2]) + '"</b> </li>',
							"doctype" : doctype,
							"doc_name" : doc_name
						})
				if change.added:
					for d in change.added:
						timeline.append({
							"time": d1.modified,
							"content" : "<li><span style ='color:#8d99a6!important'>" +time +": </span>Row Added to Table Field <b>"+d[0]+"</b></li>",
							"doctype" : doctype,
							"doc_name" : doc_name
						})
	return timeline

def get_comments(doctype, doc_name):
	timeline = []
	comments = frappe.db.get_value(doctype, doc_name, "_comments")
	if comments:
		com = json.loads(comments)
		for comment in com:
			dictio = frappe._dict(comment)
			if len(frappe.get_list("Communication", filters = [["name","=",dictio.name],["modified","like","%"+frappe.utils.nowdate()+"%"]])) != 0:
				modified = frappe.db.get_value("Communication", dictio.name, "modified")
				time = frappe.utils.format_datetime(modified,"hh:mm a")
				timeline.append({
					"time": modified,
					"content": "<li><span style ='color:#8d99a6!important'>" +time +": </span><b>"+cleantext(dictio.comment)+ "</b>commented By: <b>" + dictio.by + "</b></li>",
					"doctype" : doctype,
					"doc_name" : doc_name
				})
	return timeline

def cleantext(s):
	s = s.replace("<div>"," ")
	s = s.replace("</div>"," ")
	return s


