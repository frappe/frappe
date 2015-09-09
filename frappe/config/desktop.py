from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		"Activity": {
			"color": "#e67e22",
			"icon": "icon-play",
			"icon": "octicon octicon-pulse",
			"label": _("Activity"),
			"link": "activity",
			"type": "page"
		},
		"Calendar": {
			"color": "#2980b9",
			"icon": "icon-calendar",
			"icon": "octicon octicon-calendar",
			"label": _("Calendar"),
			"link": "Calendar/Event",
			"type": "view"
		},
		"Messages": {
			"color": "#9b59b6",
			"icon": "icon-comments",
			"icon": "octicon octicon-comment-discussion",
			"label": _("Messages"),
			"link": "messages",
			"type": "page"
		},
		"To Do": {
			"color": "#f1c40f",
			"icon": "icon-check",
			"icon": "octicon octicon-check",
			"label": _("To Do"),
			"link": "List/ToDo",
			"doctype": "ToDo",
			"type": "list"
		},
		"Notes": {
			"color": "#95a5a6",
			"doctype": "Note",
			"icon": "icon-file-alt",
			"icon": "octicon octicon-file-text",
			"label": _("Notes"),
			"link": "List/Note",
			"type": "list"
		},
		"File Manager": {
			"color": "#95a5a6",
			"doctype": "File",
			"icon": "icon-folder-close",
			"icon": "octicon octicon-file-directory",
			"label": _("File Manager"),
			"link": "List/File",
			"type": "list"
		},
		"Website": {
			"color": "#16a085",
			"icon": "icon-globe",
			"icon": "octicon octicon-globe",
			"type": "module"
		},
		"Installer": {
			"color": "#5ac8fb",
			"icon": "icon-download",
			"icon": "octicon octicon-cloud-download",
			"link": "applications",
			"type": "page",
			"label": _("Installer")
		},
		"Setup": {
			"color": "#bdc3c7",
			"icon": "icon-wrench",
			"icon": "octicon octicon-settings",
			"type": "module"
		},
		"Core": {
			"color": "#589494",
			"icon": "icon-cog",
			"icon": "octicon octicon-file-binary",
			"type": "module",
			"system_manager": 1
		},
		"Integrations": {
			"color": "#36414C",
			"icon": "octicon octicon-plug",
			"type": "module",
			"system_manager": 1
		}
	}
