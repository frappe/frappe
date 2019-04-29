from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Users"),
			"icon": "fa fa-group",
			"items": [
				{
					"type": "doctype",
					"name": "User",
					"description": _("System and Website Users")
				},
				{
					"type": "doctype",
					"name": "Role",
					"description": _("User Roles")
				},
				{
					"type": "doctype",
					"name": "Role Profile",
					"description": _("Role Profile")
				}
			]
		},
		{
			"label": _("Permissions"),
			"icon": "fa fa-lock",
			"items": [
				{
					"type": "page",
					"name": "permission-manager",
					"label": _("Role Permissions Manager"),
					"icon": "fa fa-lock",
					"description": _("Set Permissions on Document Types and Roles")
				},
				{
					"type": "doctype",
					"name": "User Permission",
					"label": _("User Permissions"),
					"icon": "fa fa-lock",
					"description": _("Restrict user for specific document")
				},
				{
					"type": "doctype",
					"name": "Role Permission for Page and Report",
					"description": _("Set custom roles for page and report")
				},
				{
					"type": "report",
					"is_query_report": True,
					"doctype": "User",
					"icon": "fa fa-eye-open",
					"name": "Permitted Documents For User",
					"description": _("Check which Documents are readable by a User")
				},
				{
					"type": "report",
					"doctype": "DocShare",
					"icon": "fa fa-share",
					"name": "Document Share Report",
					"description": _("Report of all document shares")
				}
			]
		},
	]