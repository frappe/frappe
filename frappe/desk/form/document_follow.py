# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.utils
from frappe.utils import get_url_to_form
from frappe import _
from itertools import groupby

@frappe.whitelist()
def follow_document(doctype, doc_name, user, force=False):
	'''
		param:
		Doctype name
		doc name
		user email

		condition:
		avoided for some doctype
		follow only if track changes are set to 1
	'''
	avoid_follow = ["Communication", "ToDo", "DocShare", "Email Unsubscribe", "Activity Log",
		"File", "Version", "View Log", "Document Follow", "Comment"]

	track_changes = frappe.get_meta(doctype).track_changes
	exists = is_document_followed(doctype, doc_name, user)
	if exists == 0:
		user_can_follow = frappe.db.get_value("User", user, "document_follow_notify", ignore=True)
		if user != "Administrator" and user_can_follow and track_changes and (doctype not in avoid_follow or force):
			doc = frappe.new_doc("Document Follow")
			doc.update({
				"ref_doctype": doctype,
				"ref_docname": doc_name,
				"user": user
			})
			doc.save()
			return doc

@frappe.whitelist()
def unfollow_document(doctype, doc_name, user):
	doc = frappe.get_all(
		"Document Follow",
		filters={
			"ref_doctype": doctype,
			"ref_docname": doc_name,
			"user": user
		},
		fields=["name"],
		limit=1
	)
	if doc:
		frappe.delete_doc("Document Follow", doc[0].name)
		return 1
	return 0

def get_message(doc_name, doctype, frequency, user):
	activity_list = get_version(doctype, doc_name, frequency, user) + get_comments(doctype, doc_name, frequency, user)
	return sorted(activity_list, key=lambda k: k["time"], reverse=True)

def send_email_alert(receiver, docinfo, timeline):
	if receiver:
		frappe.sendmail(
			subject=_("Document Follow Notification"),
			recipients=[receiver],
			template="document_follow",
			args={
				"docinfo": docinfo,
				"timeline": timeline,
			}
		)

def send_document_follow_mails(frequency):

	'''
		param:
		frequency for sanding mails

		task:
		set receiver according to frequency
		group document list according to user
		get changes, activity, comments on doctype
		call method to send mail
	'''

	users = frappe.get_list("Document Follow",
		fields=["*"])

	sorted_users = sorted(users, key=lambda k: k['user'])

	grouped_by_user = {}
	for k, v in groupby(sorted_users, key=lambda k: k['user']):
		grouped_by_user[k] = list(v)

	for user in grouped_by_user:
		user_frequency = frappe.db.get_value("User", user, "document_follow_frequency")
		message = []
		valid_document_follows = []
		if user_frequency == frequency:
			for d in grouped_by_user[user]:
				content = get_message(d.ref_docname, d.ref_doctype, frequency, user)
				if content:
					message = message + content
					valid_document_follows.append({
						"reference_docname": d.ref_docname,
						"reference_doctype": d.ref_doctype,
						"reference_url": get_url_to_form(d.ref_doctype, d.ref_docname)
					})

			if message and frappe.db.get_value("User", user, "document_follow_notify", ignore=True):
				send_email_alert(user, valid_document_follows, message)


def get_version(doctype, doc_name, frequency, user):
	timeline = []
	filters = get_filters("docname", doc_name, frequency, user)
	version = frappe.get_all("Version",
		filters=filters,
		fields=["ref_doctype", "data", "modified", "modified", "modified_by"]
	)
	if version:
		for v in version:
			change = frappe.parse_json(v.data)
			time = frappe.utils.format_datetime(v.modified, "hh:mm a")
			timeline_items = []
			if change.changed:
				timeline_items = get_field_changed(change.changed, time, doctype, doc_name, v)
			if change.row_changed:
				timeline_items = get_row_changed(change.row_changed, time, doctype, doc_name, v)
			if change.added:
				timeline_items = get_added_row(change.added, time, doctype, doc_name, v)

			timeline = timeline + timeline_items

	return timeline

def get_comments(doctype, doc_name, frequency, user):
	timeline = []
	filters = get_filters("reference_name", doc_name, frequency, user)
	comments = frappe.get_all("Comment",
		filters=filters,
		fields=["content", "modified", "modified_by", "comment_type"]
	)
	for comment in comments:
		if comment.comment_type == "Like":
			by = ''' By : <b>{0}<b>'''.format(comment.modified_by)
		elif comment.comment_type == "Comment":
			by = '''Commented by : <b>{0}<b>'''.format(comment.modified_by)
		else:
			by = ''

		time = frappe.utils.format_datetime(comment.modified, "hh:mm a")
		timeline.append({
			"time": comment.modified,
			"data": {
				"time": time,
				"comment": frappe.utils.html2text(str(comment.content)),
				"by": by
			},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "comment"
		})
	return timeline

def is_document_followed(doctype, doc_name, user):
	docs = frappe.get_all(
		"Document Follow",
		filters={
			"ref_doctype": doctype,
			"ref_docname": doc_name,
			"user": user
		},
		limit=1
	)
	return len(docs)

@frappe.whitelist()
def get_follow_users(doctype, doc_name):
	return frappe.get_all(
		"Document Follow",
		filters={
			"ref_doctype": doctype,
			"ref_docname":doc_name
		},
		fields=["user"]
	)

def get_row_changed(row_changed, time, doctype, doc_name, v):
	items = []
	for d in row_changed:
		d[2] = d[2] if d[2] else ' '
		d[0] = d[0] if d[0] else ' '
		d[3][0][1] = d[3][0][1] if d[3][0][1] else ' '
		items.append({
			"time": v.modified,
			"data": {
					"time": time,
					"table_field": d[0],
					"row": str(d[1]),
					"field": d[3][0][0],
					"from": frappe.utils.html2text(str(d[3][0][1])),
					"to": frappe.utils.html2text(str(d[3][0][2]))
				},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "row changed",
			"by": v.modified_by
		})
	return items

def get_added_row(added, time, doctype, doc_name, v):
	items = []
	for d in added:
		items.append({
			"time": v.modified,
			"data": {
					"to": d[0],
					"time": time
				},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "row added",
			"by": v.modified_by
		})
	return items

def get_field_changed(changed, time, doctype, doc_name, v):
	items = []
	for d in changed:
		d[1] = d[1] if d[1] else ' '
		d[2] = d[2] if d[2] else ' '
		d[0] = d[0] if d[0] else ' '
		items.append({
			"time": v.modified,
			"data": {
					"time": time,
					"field": d[0],
					"from": frappe.utils.html2text(str(d[1])),
					"to": frappe.utils.html2text(str(d[2]))
				},
			"doctype": doctype,
			"doc_name": doc_name,
			"type": "field changed",
			"by": v.modified_by
		})
	return items

def send_hourly_updates():
	send_document_follow_mails("Hourly")

def send_daily_updates():
	send_document_follow_mails("Daily")

def send_weekly_updates():
	send_document_follow_mails("Weekly")

def get_filters(search_by, name, frequency, user):
	filters = []

	if frequency == "Weekly":
		filters = [
			[search_by, "=", name],
			["modified", ">", frappe.utils.add_days(frappe.utils.nowdate(),-7)],
			["modified", "<", frappe.utils.nowdate()],
			["modified_by", "!=", user]
		]
	elif frequency == "Daily":
		filters = [
			[search_by, "=", name],
			["modified", ">", frappe.utils.add_days(frappe.utils.nowdate(),-1)],
			["modified", "<", frappe.utils.nowdate()],
			["modified_by", "!=", user]
		]
	elif frequency == "Hourly":
		filters = [
			[search_by, "=", name],
			["modified", ">", frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-1)],
			["modified", "<", frappe.utils.now_datetime()],
			["modified_by", "!=", user]
		]

	return filters
