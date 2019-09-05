# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals

import frappe

from frappe import _

def install():
	update_genders_and_salutations()
	update_global_search_doctypes()

def update_genders_and_salutations():
	default_genders = [_("Male"), _("Female"), _("Other")]
	default_salutations = [_("Mr"), _("Ms"), _('Mx'), _("Dr"), _("Mrs"), _("Madam"), _("Miss"), _("Master"), _("Prof")]
	records = [{'doctype': 'Gender', 'gender': d} for d in default_genders]
	records += [{'doctype': 'Salutation', 'salutation': d} for d in default_salutations]
	for record in records:
		doc = frappe.new_doc(record.get("doctype"))
		doc.update(record)

		try:
			doc.insert(ignore_permissions=True)
		except frappe.DuplicateEntryError as e:
			# pass DuplicateEntryError and continue
			if e.args and e.args[0]==doc.doctype and e.args[1]==doc.name:
				# make sure DuplicateEntryError is for the exact same doc and not a related doc
				pass
			else:
				raise

def update_global_search_doctypes():
	global_searches_doctypes = ["Global Search Settings", "Customize Form", "Web Page", "Webhook", "Google Contacts",
		"Google Drive", "Energy Point Log", "Energy Point Rule", "Address", "Contact", "Event", "Google Calendar",
		"Google Settings", "Auto Repeat", "Notification", "LDAP Settings", "Email Account", "Website Theme",
		"Website Settings", "Print Format", "Personal Data Download Request", "Auto Email Report", "Integration Request",
		"ToDo", "Milestone Tracker", "Milestone", "Assignment Rule", "Dashboard", "Print Settings", "S3 Backup Settings",
		"Dashboard Chart", "Dashboard Chart Source", "Energy Point Settings", "Custom Script", "Custom Field", "Post",
		"List View Setting", "Document Follow", "Website Slideshow", "Website Route Meta", "Personal Data Deletion Request",
		"Letter Head", "Blog Post", "Web Form", "Desktop Icon", "Email Queue", "Dropbox Settings", "Post Comment", "Workflow Action",
		"Blogger", "Route History", "Note", "Social Login Key", "Email Rule", "Country", "Currency", "Chat Room",
		"Data Migration Run", "Data Migration Plan", "Calendar View", "Workflow", "Stripe Settings", "Slack Webhook URL",
		"Help Article", "Workflow Action Master", "Email Template", "Chat Message", "Chat Token", "List Filter",
		"Braintree Settings", "Chat Profile", "Data Migration Connector", "OAuth Client", "Data Migration Mapping",
		"Email Flag Queue", "Unhandled Email", "Newsletter", "Contact Us Settings", "Print Style", "Print Heading",
		"Address Template", "Salutation", "Gender", "Kanban Board", "OAuth Bearer Token", "OAuth Authorization Code",
		"Blog Category", "Email Group", "Workflow State", "Email Group Member", "About Us Settings", "Blog Settings",
		"Website Script", "Bulk Update", "Razorpay Settings", "PayPal Settings", "Portal Settings", "OAuth Provider Settings",
		"Email Unsubscribe", "Help Category", "Property Setter", "Website Sidebar", "Email Domain"]

	global_search_settings = frappe.get_single("Global Search Settings")
	global_search_settings.enabled = 1
	global_search_settings.allowed_in_global_search = []
	for d in global_searches_doctypes:
		global_search_settings.append("allowed_in_global_search", {"document": d})
	global_search_settings.save(ignore_permissions=True)