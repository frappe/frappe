# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from frappe.desk.form.load import get_attachments

@frappe.whitelist()
def get_email_content(name):
	docinfo = frappe.desk.form.load.get_attachments("Communication", name)
	content = frappe.db.get_value("Communication", name, "content")
	return docinfo, content

@frappe.whitelist()
def create_flag_queue(names, action, flag):
	names = json.loads(names)
	class Found(Exception):
		pass

	for item in names:
		if item.get("uid"):
			state = frappe.db.get_value("Communication", item.get("name"), "seen")
			frappe.errprint(state)

			# check states are correct
			if (action =='Read' and state == 0) or (action =='Unread' and state == 1):
				try:
					queue = frappe.db.sql("""select name, action, flag from `tabEmail Flag Queue`
						where communication = %(name)s""", {"name":item.get("name")}, as_dict=True)
					for q in queue:
						# is same email with same flag
						if q.flag == flag:
							# to prevent flag local and server states being out of sync
							if q.action != action:
								frappe.delete_doc("Email Flag Queue", q.name)
							raise Found
	
					flag_queue = frappe.get_doc({
						"doctype": "Email Flag Queue",
						"communication": item.get("name"),
						"action": action,
						"flag": flag
					})
					flag_queue.save(ignore_permissions=True);
				except Found:
					pass

@frappe.whitelist()
def setnomatch(name):
	frappe.db.set_value("Communication", name, "nomatch", 1, update_modified=False)

@frappe.whitelist()
def update_local_flags(names, field, val):
	names = json.loads(names)
	for d in names:
		frappe.db.set_value("Communication", d.get("name"), field, val, update_modified=False)

@frappe.whitelist()
def get_accounts(user):
	email_accounts = []

	accounts = frappe.get_all("User Email", filters={ "parent": user },
		fields=["email_account as account", "email_id as title"],
		distinct=True, order_by="idx")

	if not accounts:
		return None

	all_accounts = ",".join([ account.get("account") for account in accounts ])
	if len(accounts) > 1:
		email_accounts.append({
			"account": all_accounts,
			"title": "All Accounts"
		})

	email_accounts.extend(accounts)

	return {
		"email_accounts": email_accounts,
		"all_accounts": all_accounts
	}
