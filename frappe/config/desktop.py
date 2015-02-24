from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		"Calendar": {
			"color": "#2980b9",
			"icon": "icon-calendar",
			"label": _("Calendar"),
			"link": "Calendar/Event",
			"type": "view"
		},
		"Messages": {
			"color": "#9b59b6",
			"icon": "icon-comments",
			"label": _("Messages"),
			"link": "messages",
			"type": "page"
		},
		"To Do": {
			"color": "#f1c40f",
			"icon": "icon-check",
			"label": _("To Do"),
			"link": "List/ToDo",
			"doctype": "ToDo",
			"type": "list"
		},
		"Website": {
			"color": "#16a085",
			"icon": "icon-globe",
			"type": "module"
		},
		"Installer": {
			"color": "#888",
			"icon": "icon-download",
			"link": "applications",
			"type": "page",
			"label": _("Installer")
		},
		"Setup": {
			"color": "#bdc3c7",
			"icon": "icon-wrench",
			"type": "module"
		},
		"Core": {
			"color": "#589494",
			"icon": "icon-cog",
			"type": "module",
			"system_manager": 1
		},
	}
