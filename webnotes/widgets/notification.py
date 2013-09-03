# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

@webnotes.whitelist()
def get():
	try:
		from startup.open_count import for_doctype, for_module
	except ImportError, e:
		return {}
	
	can_read = webnotes.user.get_can_read()
	open_count_doctype = {}
	open_count_module = {}

	for d in for_doctype:
		if d in can_read:
			condition = for_doctype[d]
			key = condition.keys()[0]

			result = webnotes.get_list(d, fields=["count(*)"], 
				filters=[[d, key, "=", condition[key]]], as_list=True)[0][0]
			if result:
				open_count_doctype[d] = result

	for m in for_module:
		open_count_module[m] = for_module[m]()

	return {
		"open_count_doctype": open_count_doctype,
		"open_count_module": open_count_module
	}

def get_notification_info_for_boot():
	out = get()
	
	try:
		from startup.open_count import for_doctype
	except ImportError:
		return out
	
	can_read = webnotes.user.get_can_read()
	conditions = {}
	module_doctypes = {}
	doctype_info = dict(webnotes.conn.sql("""select name, module from tabDocType"""))
	
	for d in for_doctype:
		if d in can_read:
			conditions[d] = for_doctype[d]
			module_doctypes.setdefault(doctype_info[d], []).append(d)
	
	out.update({
		"conditions": conditions,
		"module_doctypes": module_doctypes,
	})
	
	return out
	
