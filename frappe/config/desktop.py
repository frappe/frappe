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
			"description": "Todos, Notes and other basic tools to help you track your work."
		},
		{
			"module_name": "Setup",
			"category": "Administration",
			"label": _("Setup"),
			"color": "#bdc3c7",
			"reverse": 1,
			"icon": "octicon octicon-settings",
			"type": "module",
			"hidden": 1,
			"description": "Configure Users, Permissions, Printing, Email and Customization."
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
			"condition": getattr(frappe.local.conf, 'developer_mode', 0),
			"hidden": 1,
			"description": "Doctypes, dev tools and logs. (Only active when developer mode is enabled)"
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
			"link": '#social/home',
			"color": '#FF4136',
			'standard': 1,
			'idx': 15,
			"description": "Build your profile and share posts on the feed with other users."
		},
	]
