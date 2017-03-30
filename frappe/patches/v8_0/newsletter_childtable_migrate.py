# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc('email', 'doctype', 'newsletter_email_group')
	frappe.reload_doctype('Newsletter')

	if "email_group" not in frappe.db.get_table_columns("Newsletter"):
		return
		
	newsletters = frappe.get_all("Newsletter", fields=["name", "email_group"])
	for newsletter in newsletters:
		if newsletter.email_group:
			newsletter_doc = frappe.get_doc("Newsletter", newsletter.name)
			if not newsletter_doc.get("email_group"):
				newsletter_doc.append("email_group", {
					"email_group": newsletter.email_group,
				})
				newsletter_doc.flags.ignore_validate = True
				newsletter_doc.flags.ignore_mandatory = True
				newsletter_doc.save()
