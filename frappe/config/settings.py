from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.desk.moduleview import add_setup_section

def get_data():
	data = [
		{
			"label": _("Core"),
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
					"name": "Global Defaults",
					"label": _("Global Defaults"),
					"description": _("Company, Fiscal Year and Currency defaults"),
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
				{
					"type": "doctype",
					"name": "Domain Settings",
					"label": _("Domain Settings"),
					"description": _("Enable / Disable Domains"),
					"hide_count": True
				},
			]
		},
		{
			"label": _("Data"),
			"icon": "fa fa-th",
			"items": [
				{
					"type": "doctype",
					"name": "Data Import",
					"label": _("Import Data"),
					"icon": "octicon octicon-cloud-upload",
					"description": _("Import Data from CSV / Excel files.")
				},
				{
					"type": "doctype",
					"name": "Data Export",
					"label": _("Export Data"),
					"icon": "octicon octicon-cloud-upload",
					"description": _("Export Data in CSV / Excel format.")
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
			"label": _("Email / Notifications"),
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
					"name": "Notification",
					"description": _("Setup Notifications based on various criteria.")
				},
				{
					"type": "doctype",
					"name": "Email Template",
					"description": _("Email Templates for common queries.")
				},
				{
					"type": "doctype",
					"name": "Auto Email Report",
					"description": _("Setup Reports to be emailed at regular intervals"),
				},
				{
					"type": "doctype",
					"name": "Newsletter",
					"description": _("Create and manage newsletter")
				},
				{
					"type": "doctype",
					"route": "Form/Notification Settings/{}".format(frappe.session.user),
					"name": "Notification Settings",
					"description": _("Configure notifications for mentions, assignments, energy points and more.")
				}
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
		}
	]
	add_setup_section(data, "frappe", "website", _("Website"), "fa fa-globe")
	return data
