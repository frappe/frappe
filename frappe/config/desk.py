from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Tools"),
			"icon": "octicon octicon-briefcase",
			"items": [
				# {
				# 	"type": "doctype",
				# 	"name": "Communication Reconciliation",
				# 	"description":_("Reattach communications to other documents"),
				# },
				{
					"type": "doctype",
					"name": "Newsletter",
					"description": _("Newsletters to contacts, leads."),
				},
				{
					"type": "doctype",
					"name": "ToDo",
					"label": _("To Do"),
					"description": _("Documents assigned to you and by you."),
				},
				{
					"type": "doctype",
					"name": "File",
					"label": _("Files"),
				},
				{
					"type": "doctype",
					"name": "Event",
					"label": _("Calendar"),
					"link": "Calendar/Event",
					"description": _("Event and other calendars."),
				},
				{
					"type": "page",
					"label": _("Chat"),
					"name": "chat",
					"description": _("Chat messages and other notifications."),
					"data_doctype": "Communication"
				},
				{
					"type": "doctype",
					"name": "Note",
					"description": _("Private and public Notes."),
				},
				{
					"type": "page",
					"label": _("Activity"),
					"name": "activity",
					"description": _("Activity log of all users."),
				},
			]
		}
	]
