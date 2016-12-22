# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe.model.document import Document
from frappe.desk.form.load import get_attachments


@frappe.whitelist()
def get_list(email_account,start,page_length):
	inbox_list = []
	communications = frappe.db.sql("""select name, sender, sender_full_name, actualdate, recipients, communication_medium as comment_type, subject, status ,reference_doctype,reference_name,timeline_doctype,timeline_name,timeline_label,sent_or_received,uid,message_id, seen,nomatch,has_attachment
				from tabCommunication
				where email_account = %(email_account)s and deleted = 0
				ORDER BY actualdate DESC
				LIMIT %(page_length)s OFFSET %(start)s""",{"email_account":email_account,"start":int(start),"page_length":int(page_length)},as_dict=1)
	for c in communications:
		comm = {}

		comm["name"] = c.get('name')
		comm["reference_doctype"] = c.get('reference_doctype')
		comm["reference_name"] = c.get('reference_name')
		if c.get('recipients') != None:
			comm["recipients"] = c.get('recipients').replace('"',"").strip("<>")
		comm["sender"] = c.get('sender')
		comm["sender_full_name"] = c.get('sender_full_name')
		comm["actualdate"] = c.get('actualdate')
		comm["subject"] = c.get('subject')
		comm["status"] = c.get('status')
		comm["content"] = c.get('content')
		comm["timeline_doctype"] = c.get('timeline_doctype')
		comm["timeline_name"] = c.get('timeline_name')
		comm["timeline_label"] = c.get('timeline_label')
		comm["sent_or_received"] = c.get('sent_or_received')
		comm["uid"]= c.get('uid')
		comm["message_id"]=c.get("message_id")
		comm["seen"] = c.get('seen')
		comm["nomatch"] =c.get('nomatch')
		comm["has_attachment"]=c.get('has_attachment')
		inbox_list.append(comm)
	return inbox_list

@frappe.whitelist()
def get_email_content(name):
	docinfo = frappe.desk.form.load.get_attachments("Communication",name)
	content = frappe.db.get_value("Communication", name,"content")
	return docinfo, content

@frappe.whitelist()
def create_flag_queue(names,action,flag,field):
	names = json.loads(names)
	class Found(Exception):
		pass

	for item in names:
		if item["u"]:
			state = frappe.db.get_value("Communication", item["n"], field)
			if (action =='+FLAGS' and state ==0) or (action =='-FLAGS' and state ==1): #check states are correct
				try:
					queue = frappe.db.sql("""select name,action,flag from `tabEmail Flag Queue`
					where comm_name = %(name)s""",{"name":item["n"]},as_dict=1)
					for q in queue:
						if q.flag==flag:#is same email with same flag
							if q.action!=action:#to prevent flag local and server states being out of sync
								frappe.delete_doc("Email Flag Queue", q.name)
							raise Found
	
					flag_queue = frappe.get_doc({
						"doctype": "Email Flag Queue",
						"comm_name": str(item["n"]),
						"action":action,
						"flag":flag
					})
					flag_queue.save(ignore_permissions=True);
				except Found:
					pass

@frappe.whitelist()
def setnomatch(name):
	frappe.db.set_value("Communication", str(name), "nomatch", 1, update_modified=False)

@frappe.whitelist()
def update_local_flags(names,field,val):
	names = json.loads(names)
	for d in names:
		frappe.db.set_value("Communication", str(d["n"]), field, val,update_modified=False)

@frappe.whitelist()
def get_length(email_account):
	try:
		return frappe.db.sql("""select count(name)
			from tabCommunication
			where deleted = 0 and email_account= %(email_account)s""",{"email_account":email_account})
	except:
		return 0

@frappe.whitelist()
def get_accounts(user):
	try:
		return frappe.db.sql("""select email_account,email_id
		from `tabUser Emails`
		where parent = %(user)s
		order by idx""",{"user":user},as_dict=1)
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
