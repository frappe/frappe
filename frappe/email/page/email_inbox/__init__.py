# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.desk.form.load import get_attachments

@frappe.whitelist()
def get_email_content(name):
	docinfo = frappe.desk.form.load.get_attachments("Communication", name)
	content = frappe.db.get_value("Communication", name, "content")
	return docinfo, content

@frappe.whitelist()
def create_flag_queue(names, action, flag, field):
	names = json.loads(names)

	class Found(Exception):
		pass

	for item in names:
		if item["uid"]:
			state = frappe.db.get_value("Communication", item["name"], field)
			if (action == '+FLAGS' and state == 0) or (action == '-FLAGS' and state == 1):  # check states are correct
				try:
					queue = frappe.db.sql("""SELECT name,action,flag FROM `tabEmail Flag Queue`
					WHERE comm_name = %(name)s""", {"name": item["name"]}, as_dict=1)
					for q in queue:
						if q.flag == flag:  # is same email with same flag
							if q.action != action:  # to prevent flag local and server states being out of sync
								frappe.delete_doc("Email Flag Queue", q.name, ignore_permissions=True)
							raise Found

					flag_queue = frappe.get_doc({
						"doctype": "Email Flag Queue",
						"comm_name": str(item["name"]),
						"action": action,
						"flag": flag
					})
					flag_queue.save(ignore_permissions=True);
				except Found:
					pass

@frappe.whitelist()
def setnomatch(name):
	frappe.db.set_value("Communication", str(name), "nomatch", 1, update_modified=False)

@frappe.whitelist()
def update_local_flags(names, field, val):
	names = json.loads(names)
	for d in names:
		frappe.db.set_value("Communication", str(d["name"]), field, val, update_modified=False)

@frappe.whitelist()
def get_length(email_account):
	try:
		return frappe.db.sql("""SELECT count(name)
			FROM tabCommunication
			WHERE deleted = 0 AND email_account= %(email_account)s""", {"email_account": email_account})
	except:
		return 0

@frappe.whitelist()
def get_accounts(user):
	try:
		return frappe.db.sql("""SELECT email_account,email_id
		FROM `tabUser Email`
		WHERE parent = %(user)s
		ORDER BY idx""", {"user": user}, as_dict=1)
	except:
		return

# for the selection/deletion of multiple items
def set_multiple_status(names, status):
	names = json.loads(names)
	for name in names:
		set_status(name, status)

def set_status(name, status):
	st = frappe.get_doc("Issue", name)
	st.status = status
	st.save()