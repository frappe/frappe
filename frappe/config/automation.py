from __future__ import unicode_literals
from frappe import _

def get_data():
	data = [
		{
			"label": _("Automation"),
			"icon": "fa fa-random",
			"items": [
				{
					"type": "doctype",
					"name": "Assignment Rule",
					"description": _("Set up rules for user assignments.")
				},
				{
					"type": "doctype",
					"name": "Milestone",
					"description": _("Tracks milestones on the lifecycle of a document if it undergoes multiple stages.")
				},
				{
					"type": "doctype",
					"name": "Auto Repeat",
					"description": _("Automatically generates recurring documents.")
				},
			]
		},
		{
			"label": _("Event Streaming"),
			"icon": "fa fa-random",
			"items": [
				{
					"type": "doctype",
					"name": "Event Producer",
					"description": _("The site you want to subscribe to for consuming events.")
				},
				{
					"type": "doctype",
					"name": "Event Consumer",
					"description": _("The site which is consuming your events.")
				},
				{
					"type": "doctype",
					"name": "Event Update Log",
					"description": _("Maintains a Log of all inserts, updates and deletions on Event Producer site for documents that have consumers.")
				},
				{
					"type": "doctype",
					"name": "Event Sync Log",
					"description": _("Maintains a log of every event consumed along with the status of the sync and a Resync button in case sync fails.")
				},
				{
					"type": "doctype",
					"name": "Document Type Mapping",
					"description": _("The mapping configuration between two doctypes.")
				}
			]
		}
	]
	return data
