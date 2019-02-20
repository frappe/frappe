# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json
import frappe.utils
from itertools import groupby
from frappe.utils.background_jobs import enqueue

@frappe.whitelist()
def add_subcription(doctype, doc_name, user_email):
	avoid_follow = ["Communication", "ToDo", "DocShare", "Email Unsubscribe", "Activity Log", "File", "Version", "View Log", "Document Follow", "Comment"]

	track_changes = frappe.db.get_value("DocType", doctype, "track_changes")

	custom_track_change = frappe.db.get_value(
		"Property Setter",
		filters={
			"doc_type": doctype,
			"property": "track_changes"
		},
		fieldname="value"
	)
	print(custom_track_change)
	check_if_exists = check(doctype, doc_name, user_email)
	if check_if_exists == 1:
		check_if_enable = frappe.db.get_value("User", user_email, "enable_email_for_follow_documents")
		if user_email != "Administrator" and check_if_enable == 1 and (track_changes == 1 or custom_track_change == '1') and doctype not in avoid_follow:
			doc = frappe.new_doc("Document Follow")
			doc.update({
				"ref_doctype": doctype,
				"ref_docname": doc_name,
				"user": user_email
			})
			doc.save()
			return doc

@frappe.whitelist()
def unfollow(doctype, doc_name, user_email):
	doc = frappe.get_all(
		"Document Follow",
		filters={"ref_doctype": doctype,
			"ref_docname": doc_name,
			"user": user_email
		},
		fields=["name"],
		limit=1
	)
	if len(doc) != 0:
		frappe.delete_doc("Document Follow", doc[0].name)
		return 1

def get_message(doc_name, doctype, frequency):
	html = get_version(doctype, doc_name, frequency) + get_comments(doctype, doc_name, frequency)
	t = sorted(html, key=lambda k: k["time"], reverse=True)
	return t

def sent_email_alert(doc_name, doctype, receiver, docinfo, timeline):
	if receiver:
		email_args = {
			"template": "doc_subscription",
			"args": {
				"docinfo": docinfo,
				"timeline": timeline,
			},
			"recipients": [receiver],
			"subject": "Document Follow Notification",
			"reference_doctype": doctype,
			"reference_name": doc_name,
			"delayed": False,
		}
	enqueue(method=frappe.sendmail, now=True, queue="short", timeout=300, async=True, **email_args)
	frappe.db.commit()

def send_document_follow_mails(frequency):
	users = frappe.get_list("Document Follow", fields={"name", "ref_doctype", "ref_docname", "user"})
	newlist = sorted(users, key=lambda k:k["user"])
	grouped_by_user = {}
	for k, v in groupby(newlist, key=lambda k:k["user"]):
		grouped_by_user[k]=list(v)

	for k in grouped_by_user:
		freq = frappe.db.get_value("User", k, "frequency_for_follow_documents_email")
		message = []
		info = []
		if freq == frequency:
			for d in grouped_by_user[k]:
				content = get_message(d.ref_docname, d.ref_doctype, frequency)
				if content != []:
					message = message + content
					info.append({"ref_docname": d.ref_docname, "ref_doctype": d.ref_doctype, "user": k})

			if message != []:
				sent_email_alert(d.ref_docname, d.ref_doctype, k, info, message)

def get_version(doctype, doc_name,frequency):
	timeline = []
	filters = get_filters("docname", doc_name, frequency)
	version = frappe.get_all("Version", filters = filters,fields=["ref_doctype", "data", "modified"])
	if version:
		for d1 in version:
			if isinstance(d1.data, frappe.string_types):
				change = frappe._dict(json.loads(d1.data))
				time = frappe.utils.format_datetime(d1.modified, "hh:mm a")
				if change.comment:
					get_activity(change.comment, timeline, time, doctype, doc_name, d1)
				if change.changed:
					get_field_changed(change.changed, timeline, time, doctype, doc_name, d1)
				if change.row_changed:
					get_row_changed(change.row_changed, timeline, time, doctype, doc_name, d1)
				if change.added:
					get_added_row(change.added, timeline, time, doctype, doc_name, d1)
	return timeline

def get_comments(doctype, doc_name, frequency):
	timeline = []
	filters = get_filters("reference_name", doc_name, frequency)
	comments= frappe.get_all("Comment", filters = filters, fields=["content", "modified", "modified_by"])
	for comment in comments:
		time = frappe.utils.format_datetime(comment.modified, "hh:mm a")
		timeline.append({
			"time": comment.modified,
			"data": {
				"time": time,
				"comment": frappe.utils.html2text(comment.content),
				"by": comment.modified_by
			},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "comment"
		})
	return timeline

@frappe.whitelist()
def check(doctype, doc_name, user):
	check_if_exists = frappe.get_all(
		"Document Follow",
		filters={
			"ref_doctype": doctype,
			"ref_docname": doc_name,
			"user": user
		},
		limit=1
	)
	if len(check_if_exists) == 0:
		return 1
	else:
		return 0

@frappe.whitelist()
def get_follow_users(doctype, doc_name, limit=4):
	return frappe.get_all(
		"Document Follow",
		filters={
			"ref_doctype": doctype,
			"ref_docname":doc_name
		},
		fields=["user"],
		limit=limit
	)

def get_row_changed(row_changed, timeline, time, doctype, doc_name, d1):
	for d in row_changed:
		d[2] = d[2] if d[2] else ' '
		d[0] = d[0] if d[0] else ' '
		d[3][0][1] = d[3][0][1] if d[3][0][1] else ' '
		timeline.append({
			"time": d1.modified,
			"data": {
					"time": time,
					"table_field": d[0],
					"row": str(d[1]),
					"field": d[3][0][0],
					"from": frappe.utils.html2text(d[3][0][1]),
					"to": frappe.utils.html2text(d[3][0][2])
				},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "row changed"
		})

def get_added_row(added, timeline, time, doctype, doc_name, d1):
	for d in added:
		timeline.append({
			"time": d1.modified,
			"data": {
					"to": d[0],
					"time": time
				},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "row added"
		})

def get_field_changed(changed, timeline, time, doctype, doc_name, d1):
	for d in changed:
		d[1] = d[1] if d[1] else ' '
		d[2] = d[2] if d[2] else ' '
		d[0] = d[0] if d[0] else ' '
		timeline.append({
			"time": d1.modified,
			"data": {
					"time": time,
					"field": d[0],
					"from": frappe.utils.html2text(d[1]),
					"to": frappe.utils.html2text(d[2])
				},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "field changed"
		})

def get_activity(comment, timeline, time, doctype, doc_name, d1):
	timeline.append({
		"time": d1.modified,
		"data": {"time": time,
				"activity": comment
			},
		"doctype": doctype,
		"doc_name": doc_name,
		"type": "activity"
	})

def send_hourly_updates():
	send_document_follow_mails("Hourly")

def send_daily_updates():
	send_document_follow_mails("Daily")

def send_weekly_updates():
	send_document_follow_mails("Weekly")

def get_filters(search_by, name, frequency):
	if frequency == "Weekly":
		filters = [
			[search_by, "=", name],
			["modified", ">", frappe.utils.add_days(frappe.utils.nowdate(),-7)],
			["modified", "<", frappe.utils.nowdate()]
		]
	elif frequency == "Daily":
		filters = [
			[search_by, "=", name],
			["modified", ">", frappe.utils.add_days(frappe.utils.nowdate(),-1)],
			["modified", "<", frappe.utils.nowdate()]
		]
	elif frequency == "Hourly":
		filters = [
			[search_by, "=", name],
			["modified", ">", frappe.utils.add_to_date(frappe.utils.now_datetime(), 0, 0, 0, -1 )],
			["modified", "<", frappe.utils.now_datetime()]
		]

	return filters
