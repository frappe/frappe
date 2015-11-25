from __future__ import unicode_literals
from frappe import _
from frappe.desk.moduleview import add_setup_section

def get_data():
	data = [
		{
			"label": _("Users"),
			"icon": "icon-group",
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
				}
			]
		},
		{
			"label": _("Permissions"),
			"icon": "icon-lock",
			"items": [
				{
					"type": "page",
					"name": "permission-manager",
					"label": _("Role Permissions Manager"),
					"icon": "icon-lock",
					"description": _("Set Permissions on Document Types and Roles")
				},
				{
					"type": "page",
					"name": "user-permissions",
					"label": _("User Permissions Manager"),
					"icon": "icon-shield",
					"description": _("Set Permissions per User")
				},
				{
					"type": "page",
					"name": "modules_setup",
					"label": _("Show / Hide Modules"),
					"icon": "icon-upload",
					"description": _("Show or hide modules globally.")
				},
				{
					"type": "report",
					"is_query_report": True,
					"doctype": "User",
					"icon": "icon-eye-open",
					"name": "Permitted Documents For User",
					"description": _("Check which Documents are readable by a User")
				},
				{
					"type": "report",
					"doctype": "DocShare",
					"icon": "icon-share",
					"name": "Document Share Report",
					"description": _("Report of all document shares")
				}
			]
		},
		{
			"label": _("Settings"),
			"icon": "icon-wrench",
			"items": [
				{
					"type": "doctype",
					"name": "System Settings",
					"label": _("System Settings"),
					"description": _("Language, Date and Time settings"),
					"hide_count": True
				},
				{
					"type": "doctype",
					"name": "Scheduler Log",
					"description": _("Log of error on automated events (scheduler).")
				},
			]
		},
		{
			"label": _("Data"),
			"icon": "icon-th",
			"items": [
				{
					"type": "page",
					"name": "data-import-tool",
					"label": _("Import / Export Data"),
					"icon": "icon-upload",
					"description": _("Import / Export Data from .csv files.")
				},
				{
					"type": "doctype",
					"name": "Naming Series",
					"description": _("Set numbering series for transactions."),
					"hide_count": True
				},
				{
					"type": "doctype",
					"name": "Rename Tool",
					"label": _("Bulk Rename"),
					"description": _("Rename many items by uploading a .csv file."),
					"hide_count": True
				},
				{
					"type": "page",
					"name": "backups",
					"label": _("Download Backups"),
					"description": _("List of backups available for download"),
					"icon": "icon-download"
				},
			]
		},
		{
			"label": _("Email"),
			"icon": "icon-envelope",
			"items": [
				{
					"type": "doctype",
					"name": "Email Account",
					"description": _("Add / Manage Email Accounts.")
				},
				{
					"type": "doctype",
					"name": "Email Alert",
					"description": _("Setup Email Alert based on various criteria.")
				},
				{
					"type": "doctype",
					"name": "Standard Reply",
					"description": _("Standard replies to common queries.")
				},
			]
		},
		{
			"label": _("Printing"),
			"icon": "icon-print",
			"items": [
				{
					"type": "page",
					"label": "Print Format Builder",
					"name": "print-format-builder",
					"description": _("Drag and Drop tool to build and customize Print Formats.")
				},
				{
					"type": "doctype",
					"name": "Print Settings",
					"description": _("Set default format, page size, print style etc.")
				},
				{
					"type": "doctype",
					"name": "Print Format",
					"description": _("Customized HTML Templates for printing transactions.")
				},
			]
		},
		{
			"label": _("Workflow"),
			"icon": "icon-random",
			"items": [
				{
					"type": "doctype",
					"name": "Workflow",
					"description": _("Define workflows for forms.")
				},
				{
					"type": "doctype",
					"name": "Workflow State",
					"description": _("States for workflow (e.g. Draft, Approved, Cancelled).")
				},
				{
					"type": "doctype",
					"name": "Workflow Action",
					"description": _("Actions for workflow (e.g. Approve, Cancel).")
				},
			]
		},
		{
			"label": _("Integrations"),
			"icon": "icon-star",
			"items": [
				{
					"type": "page",
					"name": "applications",
					"label": _("Application Installer"),
					"description": _("Install Applications."),
					"icon": "icon-download"
				},
				{
					"type": "doctype",
					"name": "Social Login Keys",
					"description": _("Enter keys to enable login via Facebook, Google, GitHub."),
				},
				{
					"type": "doctype",
					"name": "Dropbox Backup",
					"description": _("Manage cloud backups on Dropbox"),
					"hide_count": True
				}
			]
		},
		{
			"label": _("Customize"),
			"icon": "icon-glass",
			"items": [
				{
					"type": "doctype",
					"name": "Customize Form",
					"description": _("Change field properties (hide, readonly, permission etc.)"),
					"hide_count": True
				},
				{
					"type": "doctype",
					"name": "Custom Field",
					"description": _("Add fields to forms.")
				},
				{
					"type": "doctype",
					"name": "Custom Script",
					"description": _("Add custom javascript to forms.")
				},
				{
					"type": "doctype",
					"name": "DocType",
					"description": _("Add custom forms.")
				}

			]
		},
	]
	add_setup_section(data, "frappe", "website", _("Website"), "icon-globe")
	return data
