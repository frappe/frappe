# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class CommunicationReconciliation(Document):
	def fetch(self):
		dt = self.reference_doctype
		dn = self.reference_name
		conditions = "<=>"
		if (dn =="" or dn== None):
			if (dt =="" or dt== None):
				dt = dn = None
			else:
				conditions = "like"
				dn = "%"

		select= """select name, content , sender , creation, recipients, communication_medium as comment_type, subject, status ,reference_doctype,reference_name,timeline_label
					from tabCommunication
					where reference_doctype <=> %s and reference_name {0} %s
					and communication_type ='Communication'
					order by creation desc""".format(conditions)

		self.communication_list = []
		communications = frappe.db.sql(select,(dt,dn),as_dict=1)
		for c in communications:
			comm = self.append('communication_list', {})

			comm.name = c.get('name')
			comm.reference_doctype = c.get('reference_doctype')
			comm.reference_name = c.get('reference_name')
			if c.get('recipients') != None:
				comm.recipients = c.get('recipients').replace('"',"").strip("<>")
			comm.sender = c.get('sender')
			comm.subject = c.get('subject')
			comm.status = c.get('status')
			comm.content = c.get('content')
			comm.timeline_label =c.get('timeline_label')
			
		return self

	def relink_bulk(self,changed_list):
		for comm in changed_list:
			
			original_reference_doctype=frappe.db.get_value("Communication",changed_list[comm]["name"],"reference_doctype")
			original_reference_name=frappe.db.get_value("Communication",changed_list[comm]["name"],"reference_name")
			communication_medium=frappe.db.get_value("Communication",changed_list[comm]["name"],"communication_medium")
			subject=frappe.db.get_value("Communication",changed_list[comm]["name"],"subject")
			subject_link = '<a href="/desk#Form/Communication/' + changed_list[comm]["name"] +'" target="_blank">' + subject
			content= 'Relinked ' + communication_medium + ' ' + subject_link + '</a>'

			if original_reference_doctype:
				from_link = '<a href="/desk#Form/' + original_reference_doctype +'/'+ original_reference_name +'" target="_blank">'
				content += ' from ' + from_link + original_reference_doctype+' '+original_reference_name+'</a>'
			
			frappe.db.sql("""update `tabCommunication`
			set reference_doctype = %(ref_doc)s ,reference_name = %(ref_name)s ,status = "Linked"
			where name = %(name)s or timeline_hide = %(name)s; """,{'ref_doc':changed_list[comm]["reference_doctype"],'ref_name':changed_list[comm]["reference_name"],'name':changed_list[comm]["name"]})
			
			dup_list = [{"name": changed_list[comm]["name"],"timeline_label":False}] + frappe.db.get_values("Communication", {"timeline_hide": changed_list[comm]["name"]},["name", "timeline_label"], as_dict=1)
			for comm in dup_list:
				if not comm["timeline_label"]:
					doc = frappe.get_doc("Communication", comm["name"])
					if not doc.timeline_label:
						doc.timeline_doctype = None
						doc.timeline_name = None
						doc.save(ignore_permissions=True)

			comment = frappe.get_doc({
				"doctype": "Communication",
				"communication_type": "Comment",
				"comment_type": "Relinked",
				"reference_doctype": changed_list[comm]["reference_doctype"],
				"reference_name": changed_list[comm]["reference_name"],
				"subject": subject,
				"communication_medium": communication_medium,
				"reference_owner": frappe.db.get_value(changed_list[comm]["reference_doctype"], changed_list[comm]["reference_name"], "owner"),
				"content": content,
				"sender":frappe.session.user
			}).insert(ignore_permissions=True)

		return self.fetch()

@frappe.whitelist()
def relink(name,reference_doctype,reference_name):
		dt = reference_doctype
		dn = reference_name
		if dt=="" or dt==None or dn == "" or dn == None:
			return 

		original_reference_doctype=frappe.db.get_value("Communication",name,"reference_doctype")
		original_reference_name=frappe.db.get_value("Communication",name,"reference_name")
		communication_medium=frappe.db.get_value("Communication",name,"communication_medium")
		subject=frappe.db.get_value("Communication",name,"subject")
		subject_link = '<a href="/desk#Form/Communication/' + name +'" target="_blank">' + subject
		content= 'Relinked ' + communication_medium + ' ' + subject_link + '</a>'

		if original_reference_doctype:
			from_link = '<a href="/desk#Form/' + original_reference_doctype +'/'+ original_reference_name +'" target="_blank">'
			content += ' from ' + from_link + original_reference_doctype+' '+original_reference_name+'</a>'

		frappe.db.sql("""UPDATE `tabCommunication`
					SET reference_doctype = %(ref_doc)s ,reference_name = %(ref_name)s ,STATUS = "Linked"
					WHERE name = %(name)s OR timeline_hide = %(name)s; """,
		              {'ref_doc': dt,
		               'ref_name': dn, 'name': name})

		dup_list = [{"name":name,"timeline_label":False}] + frappe.db.get_values("Communication", {"timeline_hide": name}, ["name","timeline_label"],as_dict=1)
		for comm in dup_list:
			if not comm["timeline_label"]:
				doc = frappe.get_doc("Communication", comm["name"])
				if not doc.timeline_label:
					doc.timeline_doctype = None
					doc.timeline_name = None
					doc.save(ignore_permissions=True)

		frappe.get_doc({
				"doctype": "Communication",
				"communication_type": "Comment",
				"comment_type": "Relinked",
				"reference_doctype": dt,
				"reference_name": dn,
				"subject": subject,
				"communication_medium": frappe.db.get_value("Communication",name,"communication_medium"),
				"reference_owner": frappe.db.get_value(dt, dn, "owner"),
				"content": content,
				"sender":frappe.session.user
			}).insert(ignore_permissions=True)

def get_communication_doctype(doctype, txt, searchfield, start, page_len, filters):
	user_perms = frappe.utils.user.UserPermissions(frappe.session.user)
	user_perms.build_permissions()
	can_read = user_perms.can_read

	com_doctypes = [d[0] for d in frappe.db.get_values("DocType", {"issingle": 1,"istable": 1,"hide_toolbar": 1})]

	out = []
	for dt in can_read:
		if txt.lower().replace("%", "") in dt.lower() and dt not in com_doctypes:
			out.append([dt])
	return out
