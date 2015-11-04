from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		"File Manager": {
			"color": "#AA784D",
			"doctype": "File",
			"icon": "octicon octicon-file-directory",
			"label": _("File Manager"),
			"link": "List/File",
			"type": "list"
		},
		"Website": {
			"color": "#16a085",
			"icon": "octicon octicon-globe",
			"type": "module"
		},
		"Setup": {
			"color": "#bdc3c7",
			"reverse": 1,
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
		"Desk": {
			"label": _("Tools"),
			"color": "#FFF5A7",
			"reverse": 1,
			"icon": "octicon octicon-calendar",
			"type": "module",
			"system_manager": 1
		}
	}
