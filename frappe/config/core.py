from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Documents"),
			"items": [
				{
					"type": "doctype",
					"name": "DocType",
					"description": _("Models (building blocks) of the Application"),
				},
				{
					"type": "doctype",
					"name": "Module Def",
					"description": _("Groups of DocTypes"),
				},
				{
					"type": "doctype",
					"name": "Page",
					"description": _("Pages in Desk (place holders)"),
				},
				{
					"type": "doctype",
					"name": "Report",
					"description": _("Script or Query reports"),
				},
				{
					"type": "doctype",
					"name": "Print Format",
					"description": _("Customized Formats for Printing, Email"),
				},
				{
					"type": "doctype",
					"name": "Custom Script",
					"description": _("Client side script extensions in Javascript"),
				}
			]
		},
		{
			"label": _("Logs"),
			"items": [
				{
					"type": "doctype",
					"name": "Error Log",
					"description": _("Errors in Background Events"),
				},
				{
					"type": "doctype",
					"name": "Email Queue",
					"description": _("Background Email Queue"),
				},
				{
					"type": "page",
					"label": _("Background Jobs"),
					"name": "background_jobs",
				},
				{
					"type": "doctype",
					"name": "Error Snapshot",
					"description": _("A log of request errors"),
				},
			]
		}
	]
