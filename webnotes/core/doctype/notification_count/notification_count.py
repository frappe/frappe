# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl

@webnotes.whitelist()
def get_notifications():
	config = get_notification_config()
	can_read = webnotes.user.get_can_read()
	open_count_doctype = {}
	open_count_module = {}

	notification_count = dict(webnotes.conn.sql("""select for_doctype, open_count 
		from `tabNotification Count` where owner=%s""", webnotes.session.user))

	for d in config.for_doctype:
		if d in can_read:
			condition = config.for_doctype[d]
			key = condition.keys()[0]

			if d in notification_count:
				open_count_doctype[d] = notification_count[d]
			else:
				result = webnotes.get_list(d, fields=["count(*)"], 
					filters=[[d, key, "=", condition[key]]], as_list=True, limit_page_length=1)[0][0]

				webnotes.doc({"doctype":"Notification Count", "for_doctype":d, 
					"open_count":result}).insert()
					
				open_count_doctype[d] = result

	for m in config.for_module:
		if m in notification_count:
			open_count_module[m] = notification_count[m]
		else:
			open_count_module[m] = webnotes.get_attr(config.for_module[m])()
			webnotes.doc({"doctype":"Notification Count", "for_doctype":m, 
				"open_count":open_count_module[m]}).insert()

	return {
		"open_count_doctype": open_count_doctype,
		"open_count_module": open_count_module
	}

def delete_notification_count_for(doctype):
	if webnotes.flags.in_import: return
	webnotes.conn.sql("""delete from `tabNotification Count` where for_doctype = %s""", doctype)

def delete_event_notification_count():
	delete_notification_count_for("Event")

def clear_doctype_notifications(controller, method=None):
	if webnotes.flags.in_import:
		return
		
	config = get_notification_config()
	doctype = controller.doc.doctype

	if doctype in config.for_doctype:
		delete_notification_count_for(doctype)
		return
	
	if doctype in config.for_module_doctypes:
		delete_notification_count_for(config.for_module_doctypes[doctype])
		
def get_notification_info_for_boot():
	out = get_notifications()

	config = get_notification_config()

	can_read = webnotes.user.get_can_read()
	conditions = {}
	module_doctypes = {}
	doctype_info = dict(webnotes.conn.sql("""select name, module from tabDocType"""))
	
	for d in list(set(can_read + config.for_doctype.keys())):
		if d in config.for_doctype:
			conditions[d] = config.for_doctype[d]
		
		if d in doctype_info:
			module_doctypes.setdefault(doctype_info[d], []).append(d)
	
	out.update({
		"conditions": conditions,
		"module_doctypes": module_doctypes,
	})
	
	return out

def get_notification_config():
	config = webnotes._dict()	
	for notification_config in webnotes.get_hooks().notification_config:
		nc = webnotes.get_attr(notification_config)()
		for key in ("for_doctype", "for_module", "for_module_doctypes"):
			config.setdefault(key, {})
			config[key].update(nc.get(key, {}))
	return config

def on_doctype_update():
	if not webnotes.conn.sql("""show index from `tabNotification Count` 
		where Key_name="notification_count_owner_index" """):
		webnotes.conn.commit()
		webnotes.conn.sql("""alter table `tabNotification Count` 
			add index notification_count_owner_index(owner)""")
	
