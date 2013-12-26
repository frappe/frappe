# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import webnotes

def get_notification_config():
	return {
		"for_module_doctypes": {
			"ToDo": "To Do",
			"Event": "Calendar",
			"Comment": "Messages"
		},
		"for_module": {
			"To Do": "webnotes.core.notifications.get_things_todo",
			"Calendar": "webnotes.core.notifications.get_todays_events",
			"Messages": "webnotes.core.notifications.get_unread_messages"
		}
	}

def get_things_todo():
	"""Returns a count of incomplete todos"""
	incomplete_todos = webnotes.conn.sql("""\
		SELECT COUNT(*) FROM `tabToDo`
		WHERE IFNULL(checked, 0) = 0
		AND (owner = %s or assigned_by=%s)""", (webnotes.session.user, webnotes.session.user))
	return incomplete_todos[0][0]

def get_todays_events():
	"""Returns a count of todays events in calendar"""
	from webnotes.core.doctype.event.event import get_events
	from webnotes.utils import nowdate
	today = nowdate()
	return len(get_events(today, today))

def get_unread_messages():
	"returns unread (docstatus-0 messages for a user)"
	return webnotes.conn.sql("""\
		SELECT count(*)
		FROM `tabComment`
		WHERE comment_doctype IN ('My Company', 'Message')
		AND comment_docname = %s
		AND ifnull(docstatus,0)=0
		""", webnotes.user.name)[0][0]