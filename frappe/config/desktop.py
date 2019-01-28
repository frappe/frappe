from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
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
			"module_name": 'Email Inbox',
			"type": 'list',
			"label": 'Email Inbox',
			"_label": _('Email Inbox'),
			"_id": 'Email Inbox',
			"_doctype": 'Communication',
			"icon": 'fa fa-envelope-o',
			"color": '#589494',
			"link": 'List/Communication/Inbox'
		},


		# Administration
		{
			"module_name": "Desk",
			"category": "Administration",
			"label": _("Tools"),
			"color": "#FFF5A7",
			"reverse": 1,
			"icon": "octicon octicon-calendar",
			"type": "module",
			"description": "Todos, Notes and other basic tools to help you track your work."
		},
		{
			"module_name": "Settings",
			"category": "Administration",
			"label": _("Settings"),
			"color": "#bdc3c7",
			"reverse": 1,
			"icon": "octicon octicon-settings",
			"type": "module",
			"hidden": 1,
			"description": "Configure your ERPNext account."
		},
		{
			"module_name": "Integrations",
			"category": "Administration",
			"label": _("Integrations"),
			"color": "#16a085",
			"icon": "octicon octicon-globe",
			"type": "module",
			"hidden": 1,
			"description": "DropBox, Woocomerce, AWS, Shopify and GoCardless."
		},
		{
			"module_name": 'Contacts',
			"category": "Administration",
			"label": _("Contacts"),
			"type": 'module',
			"icon": "octicon octicon-book",
			"color": '#ffaedb',
			"hidden": 1,
			"description": "People Contacts and Address Book."
		},
		{
			"module_name": "Core",
			"category": "Administration",
			"_label": _("Developer"),
			"label": "Developer",
			"color": "#589494",
			"icon": "octicon octicon-circuit-board",
			"type": "module",
			"system_manager": 1,
			"hidden": 1,
			"description": "The Frappe innards of ERPNext. (Only active when developer mode is enabled)"
		},

		# Places
		{
			"module_name": "Website",
			"category": "Places",
			"label": _("Website"),
			"_label": _("Website"),
			"color": "#16a085",
			"icon": "octicon octicon-globe",
			"type": "module",
			"hidden": 1,
			"description": "Webpages and the Portal Side of Things."
		},
		{
			"module_name": 'Social',
			"category": "Places",
			"label": _('Social'),
			"icon": "octicon octicon-heart",
			"type": 'link',
			"link": 'social/home',
			"color": '#FF4136',
			'standard': 1,
			'idx': 15,
			"description": "Build your profile and share posts on the feed with other users."
		},
	]
