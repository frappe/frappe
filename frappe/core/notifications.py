# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.query_builder import DocType, Interval
from frappe.query_builder.functions import Now


def get_notification_config():
	return {
		"for_doctype": {
			"Error Log": {"seen": 0},
			"Communication": {"status": "Open", "communication_type": "Communication"},
			"ToDo": "frappe.core.notifications.get_things_todo",
			"Event": "frappe.core.notifications.get_todays_events",
			"Error Snapshot": {"seen": 0, "parent_error_snapshot": None},
			"Workflow Action": {"status": 'Open'}
		},
	}

def get_things_todo(as_list=False):
	"""Returns a count of incomplete todos"""
	data = frappe.get_list("ToDo",
		fields=["name", "description"] if as_list else "count(*)",
		filters=[["ToDo", "status", "=", "Open"]],
		or_filters=[["ToDo", "allocated_to", "=", frappe.session.user],
			["ToDo", "assigned_by", "=", frappe.session.user]],
		as_list=True)

	if as_list:
		return data
	else:
		return data[0][0]

def get_todays_events(as_list=False):
	"""Returns a count of todays events in calendar"""
	from frappe.desk.doctype.event.event import get_events
	from frappe.utils import nowdate
	today = nowdate()
	events = get_events(today, today)
	return events if as_list else len(events)

def get_unseen_likes():
	"""Returns count of unseen likes"""

	comment_doctype = DocType("Comment")
	return frappe.db.count(comment_doctype,
		filters=(
			(comment_doctype.comment_type == "Like")
			& (comment_doctype.modified >= Now() - Interval(years=1))
			& (comment_doctype.owner.notnull())
			& (comment_doctype.owner != frappe.session.user)
			& (comment_doctype.reference_owner == frappe.session.user)
			& (comment_doctype.seen == 0)
		)
	)


def get_unread_emails():
	"returns count of unread emails for a user"

	communication_doctype = DocType("Communication")
	user_doctype = DocType("User")
	distinct_email_accounts = (
		frappe.qb.from_(user_doctype)
		.select(user_doctype.email_account)
		.where(user_doctype.parent == frappe.session.user)
		.distinct()
	)

	return frappe.db.count(communication_doctype,
		filters=(
			(communication_doctype.communication_type == "Communication")
			& (communication_doctype.communication_medium == "Email")
			& (communication_doctype.sent_or_received == "Received")
			& (communication_doctype.email_status.notin(["spam", "Trash"]))
			& (communication_doctype.email_account.isin(distinct_email_accounts))
			& (communication_doctype.modified >= Now() - Interval(years=1))
			& (communication_doctype.seen == 0)
		)
	)
