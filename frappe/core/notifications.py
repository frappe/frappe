# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def get_notification_config():
	return {
		"for_module_doctypes": {
			"ToDo": "To Do",
			"Event": "Calendar",
			"Comment": "Messages"
		},
		"for_module": {
			"To Do": "frappe.core.notifications.get_things_todo",
			"Calendar": "frappe.core.notifications.get_todays_events",
			"Messages": "frappe.core.notifications.get_unread_messages"
		}
	}

def get_things_todo():
	"""Returns a count of incomplete todos"""
	incomplete_todos = frappe.db.sql("""\
		SELECT COUNT(*) FROM `tabToDo`
		WHERE status="Open"
		AND (owner = %s or assigned_by=%s)""", (frappe.session.user, frappe.session.user))
	return incomplete_todos[0][0]

def get_todays_events():
	"""Returns a count of todays events in calendar"""
	from frappe.core.doctype.event.event import get_events
	from frappe.utils import nowdate
	today = nowdate()
	return len(get_events(today, today))

def get_unread_messages():
	"returns unread (docstatus-0 messages for a user)"
	return frappe.db.sql("""\
		SELECT count(*)
		FROM `tabComment`
		WHERE comment_doctype IN ('My Company', 'Message')
		AND comment_docname = %s
		AND ifnull(docstatus,0)=0
		""", (frappe.user.name,))[0][0]