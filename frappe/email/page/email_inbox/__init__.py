# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from frappe.desk.form.load import get_attachments

@frappe.whitelist()
def get_email_content(docname):
	docinfo = frappe.desk.form.load.get_attachments("Communication", docname)
	content = frappe.db.get_value("Communication", docname, "content")
	return docinfo, content

@frappe.whitelist()
def create_flag_queue(docnames, action, flag, field):
	class Found(Exception):
		pass

	docnames = json.loads(docnames)

	for docname in docnames:
		if not docname.get("uid"):
			continue

		state = frappe.db.get_value("Communication", docname.get("name"), field)

		# check states are correct
		if (action =='+FLAGS' and state == 0) or (action == '-FLAGS' and state == 1):
			try:
				email_flag_queue = frappe.db.get_values("Email Flag Queue", { "comm_name": docname.get("name") },
							["name", "action", "flag"], as_dict=True)

				for email_flag in email_flag_queue:
					# Is same email with same flag
					if email_flag.flag == flag:
						# To prevent flag local and server states being out of sync
						if email_flag.action != action:
							frappe.delete_doc("Email Flag Queue", email_flag.name)
						
						raise Found

				frappe.get_doc({
					"doctype": "Email Flag Queue",
					"comm_name": docname.get("name"),
					"action": action,
					"flag": flag
				}).save(ignore_permissions=True);

			except Found:
				pass

@frappe.whitelist()
def setnomatch(docname):
	frappe.db.set_value("Communication", docname, "nomatch", 1, update_modified=False)

@frappe.whitelist()
def update_local_flags(docnames, field, val):
	docnames = json.loads(docnames)
	for docname in docnames:
		frappe.db.set_value("Communication", docname.get("name"), field, val, update_modified=False)

@frappe.whitelist()
def get_accounts(user):
	try:
		return frappe.db.get_values("User Email", { "parent": user },
				[ "email_account", "email_id" ], order_by="idx", as_dict=True)
	except:
		return

# for the selection/deletion of multiple items
def set_multiple_status(names, status):
	names = json.loads(names)
	for name in names:
		set_status(name, status)

def set_status(name, status):
	issue = frappe.get_doc("Issue", names)
	issue.status = status
	issue.save()
