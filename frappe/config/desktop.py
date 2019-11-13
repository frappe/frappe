from __future__ import unicode_literals
import frappe
from frappe import _

def get_data():
	return [
		# Administration
		{
			"module_name": "Desk",
			"category": "Administration",
			"label": _("Tools"),
			"color": "#FFF5A7",
			"reverse": 1,
			"icon": "octicon octicon-calendar",
			"type": "module",
			"description": "Todos, notes, calendar and newsletter."
		},
		{
			"module_name": "Settings",
			"category": "Administration",
			"label": _("Settings"),
			"color": "#bdc3c7",
			"reverse": 1,
			"icon": "octicon octicon-settings",
			"type": "module",
			"description": "Data import, printing, email and workflows."
		},
		{
			"module_name": "Users and Permissions",
			"category": "Administration",
			"label": _("Users and Permissions"),
			"color": "#bdc3c7",
			"reverse": 1,
			"icon": "octicon octicon-settings",
			"type": "module",
			"description": "Setup roles and permissions for users on documents."
		},
		{
			"module_name": "Customization",
			"category": "Administration",
			"label": _("Customization"),
			"color": "#bdc3c7",
			"reverse": 1,
			"icon": "octicon octicon-settings",
			"type": "module",
			"description": "Customize forms, custom fields, scripts and translations."
		},
		{
			"module_name": "Integrations",
			"category": "Administration",
			"label": _("Integrations"),
			"color": "#16a085",
			"icon": "octicon octicon-globe",
			"type": "module",
			"description": "DropBox, Woocomerce, AWS, Shopify and GoCardless."
		},
		{
			"module_name": 'Contacts',
			"category": "Administration",
			"label": _("Contacts"),
			"type": 'module',
			"icon": "octicon octicon-book",
			"color": '#ffaedb',
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
			"condition": getattr(frappe.local.conf, 'developer_mode', 0),
			"description": "Doctypes, dev tools and logs."
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
			"description": "Webpages, webforms, blogs and website theme."
		},
		{
			"module_name": 'Social',
			"category": "Places",
			"label": _('Social'),
			"icon": "octicon octicon-heart",
			"type": 'link',
			"link": '#social/home',
			"color": '#FF4136',
			'standard': 1,
			'idx': 15,
			"description": "Build your profile and share posts with other users."
		},
		{
			"module_name": 'Leaderboard',
			"category": "Places",
			"label": _('Leaderboard'),
			"icon": "fa fa-trophy",
			"type": 'link',
			"link": '#social/users',
			"color": '#FF4136',
			'standard': 1,
		},
		{
			"module_name": 'dashboard',
			"category": "Places",
			"label": _('Dashboard'),
			"icon": "octicon octicon-graph",
			"type": "link",
			"link": "#dashboard",
			"color": '#FF4136',
			'standard': 1,
			'idx': 10
		},
	]
