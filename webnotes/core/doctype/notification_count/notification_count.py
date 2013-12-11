# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes
try:
	from startup.open_count import for_doctype, for_module, for_module_doctypes
	all_doctypes = for_doctype.keys() + for_module_doctypes.keys()
except ImportError:
	for_doctype = {}
	for_module = {}
	for_module_doctypes = []
	all_doctypes = []

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

@webnotes.whitelist()
def get():
	can_read = webnotes.user.get_can_read()
	open_count_doctype = {}
	open_count_module = {}

	notification_count = dict(webnotes.conn.sql("""select for_doctype, open_count 
		from `tabNotification Count` where owner=%s""", webnotes.session.user))

	for d in for_doctype:
		if d in can_read:
			condition = for_doctype[d]
			key = condition.keys()[0]

					
			if d in notification_count:
				open_count_doctype[d] = notification_count[d]
			else:
				result = webnotes.get_list(d, fields=["count(*)"], 
					filters=[[d, key, "=", condition[key]]], as_list=True, limit_page_length=1)[0][0]

				webnotes.doc({"doctype":"Notification Count", "for_doctype":d, 
					"open_count":result}).insert()
					
				open_count_doctype[d] = result

	for m in for_module:
		if m in notification_count:
			open_count_module[m] = notification_count[m]
		else:
			open_count_module[m] = for_module[m]()
			webnotes.doc({"doctype":"Notification Count", "for_doctype":m, 
				"open_count":open_count_module[m]}).insert()

	return {
		"open_count_doctype": open_count_doctype,
		"open_count_module": open_count_module
	}

def delete_notification_count_for(doctype):
	try:
		webnotes.conn.sql("""delete from `tabNotification Count` where for_doctype = %s""", doctype)
	except webnotes.SQLError:
		pass # during install

def clear_doctype_notifications(controller, method=None):
	doctype = controller.doc.doctype
	if doctype in all_doctypes:
		delete_notification_count_for(for_module_doctypes[doctype] if doctype in \
			for_module_doctypes else doctype)

def get_notification_info_for_boot():
	out = get()

	can_read = webnotes.user.get_can_read()
	conditions = {}
	module_doctypes = {}
	doctype_info = dict(webnotes.conn.sql("""select name, module from tabDocType"""))

	try:
		from startup.open_count import for_doctype
	except ImportError:
		for_doctype = {}
	
	for d in list(set(can_read + for_doctype.keys())):
		if d in for_doctype:
			conditions[d] = for_doctype[d]
		
		if d in doctype_info:
			module_doctypes.setdefault(doctype_info[d], []).append(d)
	
	out.update({
		"conditions": conditions,
		"module_doctypes": module_doctypes,
	})
	
	return out
	
def on_doctype_update():
	if not webnotes.conn.sql("""show index from `tabNotification Count` 
		where Key_name="notification_count_owner_index" """):
		webnotes.conn.commit()
		webnotes.conn.sql("""alter table `tabNotification Count` 
			add index notification_count_owner_index(owner)""")
	
