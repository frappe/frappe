from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"module_name": "Email",
			"color": "grey",
			"icon": "octicon octicon-mail",
			"type": "page",
			"link": "email_inbox",
			"label": _("Email Inbox")
		},
		{
			"module_name": "Desk",
			"label": _("Tools"),
			"color": "#FFF5A7",
			"reverse": 1,
			"icon": "octicon octicon-calendar",
			"type": "module"
		},
		{
			"module_name": "File Manager",
			"color": "#AA784D",
			"doctype": "File",
			"icon": "octicon octicon-file-directory",
			"label": _("File Manager"),
			"link": "List/File",
			"type": "list",
			"hidden": 1
		},
		{
			"module_name": "Website",
			"color": "#16a085",
			"icon": "octicon octicon-globe",
			"type": "module",
			"hidden": 1
		},
		{
			"module_name": "Setup",
			"color": "#bdc3c7",
			"reverse": 1,
			"icon": "octicon octicon-settings",
			"type": "module",
			"hidden": 1
		},
		{
			"module_name": "Core",
			"label": _("Developer"),
			"color": "#589494",
			"icon": "octicon octicon-circuit-board",
			"type": "module",
			"system_manager": 1,
			"hidden": 1
		},
	]
