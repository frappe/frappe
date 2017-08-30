from __future__ import unicode_literals
from frappe import _
from frappe.desk.moduleview import add_setup_section

def get_data():
	data = [
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
					"type": "page",
					"name": "modules_setup",
					"label": _("Show / Hide Modules"),
					"icon": "fa fa-upload",
					"description": _("Show or hide modules globally.")
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
		{
			"label": _("Settings"),
			"icon": "fa fa-wrench",
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
					"name": "Error Log",
					"description": _("Log of error on automated events (scheduler).")
				},
				{
					"type": "doctype",
					"name": "Error Snapshot",
					"description": _("Log of error during requests.")
				},
			]
		},
		{
			"label": _("Data"),
			"icon": "fa fa-th",
			"items": [
				{
					"type": "page",
					"name": "data-import-tool",
					"label": _("Import / Export Data"),
					"icon": "fa fa-upload",
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
					"type": "doctype",
					"name": "Bulk Update",
					"label": _("Bulk Update"),
					"description": _("Update many values at one time."),
					"hide_count": True
				},
				{
					"type": "page",
					"name": "backups",
					"label": _("Download Backups"),
					"description": _("List of backups available for download"),
					"icon": "fa fa-download"
				},
				{
					"type": "doctype",
					"name": "Deleted Document",
					"label": _("Deleted Documents"),
					"description": _("Restore or permanently delete a document.")
				},
			]
		},
		{
			"label": _("Email"),
			"icon": "fa fa-envelope",
			"items": [
				{
					"type": "doctype",
					"name": "Email Account",
					"description": _("Add / Manage Email Accounts.")
				},
				{
					"type": "doctype",
					"name": "Email Domain",
					"description": _("Add / Manage Email Domains.")
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
				{
					"type": "doctype",
					"name": "Auto Email Report",
					"description": _("Setup Reports to be emailed at regular intervals"),
				},
			]
		},
		{
			"label": _("Printing"),
			"icon": "fa fa-print",
			"items": [
				{
					"type": "page",
					"label": _("Print Format Builder"),
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
				{
					"type": "doctype",
					"name": "Print Style",
					"description": _("Stylesheets for Print Formats")
				},
			]
		},
		{
			"label": _("Workflow"),
			"icon": "fa fa-random",
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
			"label": _("Customize"),
			"icon": "fa fa-glass",
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
					"label": _("Custom Translations"),
					"name": "Translation",
					"description": _("Add your own translations")
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
				},
				{
					"type": "doctype",
					"label": _("Custom Tags"),
					"name": "Tag Category",
					"description": _("Add your own Tag Categories")
				}

			]
		},
		{
			"label": _("Applications"),
			"items":[
				{
					"type": "page",
					"name": "applications",
					"label": _("Application Installer"),
					"description": _("Install Applications."),
					"icon": "fa fa-download"
				},
			]
		}
	]
	add_setup_section(data, "frappe", "website", _("Website"), "fa fa-globe")
	return data
