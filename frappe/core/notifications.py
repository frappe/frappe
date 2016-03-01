# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def get_notification_config():
	return {
		"for_doctype": {
			"Scheduler Log": {"seen": 0},
			"Communication": {"status": "Open", "communication_type": "Communication"},
			"ToDo": "frappe.core.notifications.get_things_todo",
			"Event": "frappe.core.notifications.get_todays_events",
			"Error Snapshot": {"seen": 0, "parent_error_snapshot": None},
		},
		"for_other": {
			"Likes": "frappe.core.notifications.get_unseen_likes",
			"Messages": "frappe.core.notifications.get_unread_messages",
		}
	}

def get_things_todo():
	"""Returns a count of incomplete todos"""
	return frappe.get_list("ToDo",
		fields=["count(*)"],
		filters=[["ToDo", "status", "=", "Open"]],
		or_filters=[["ToDo", "owner", "=", frappe.session.user],
			["ToDo", "assigned_by", "=", frappe.session.user]],
		as_list=True)[0][0]

def get_todays_events():
	"""Returns a count of todays events in calendar"""
	from frappe.desk.doctype.event.event import get_events
	from frappe.utils import nowdate
	today = nowdate()
	return len(get_events(today, today))

def get_unread_messages():
	"returns unread (docstatus-0 messages for a user)"
	return frappe.db.sql("""\
		SELECT count(*)
		FROM `tabCommunication`
		WHERE communication_type in ('Chat', 'Notification')
		AND reference_doctype = 'User'
		AND reference_name = %s
		AND seen=0
		""", (frappe.session.user,))[0][0]

def get_unseen_likes():
	"""Returns count of unseen likes"""
	return frappe.db.sql("""select count(*) from `tabCommunication`
		where
			communication_type='Comment'
			and comment_type='Like'
			and owner is not null and owner!=%(user)s
			and reference_owner=%(user)s
			and seen=0""", {"user": frappe.session.user})[0][0]
