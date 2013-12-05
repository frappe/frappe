# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.defaults

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_users_and_links():
	links, all_fields = [], []

	for l in webnotes.conn.sql("""select tabDocField.fieldname, tabDocField.options
		from tabDocField, tabDocType 
		where tabDocField.fieldtype='Link' 
		and tabDocField.parent = tabDocType.name
		and ifnull(tabDocType.istable,0)=0
		and ifnull(tabDocType.issingle,0)=0
		and tabDocField.parent not in ('[Select]', 'DocType', 'Module Def')
		""") + webnotes.conn.sql("""select fieldname, options
		from `tabCustom Field` where fieldtype='Link'"""):
		if not l[0] in all_fields:
			links.append([l[0], l[1]])
			all_fields.append(l[0])
			
	links.sort()

	return {
		"users": [d[0] for d in webnotes.conn.sql("""select name from tabProfile where
			ifnull(enabled,0)=1 and
			name not in ("Administrator", "Guest")""")],
		"link_fields": links
	}
	
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def get_properties(user=None, key=None):
	return webnotes.conn.sql("""select name, parent, defkey, defvalue 
		from tabDefaultValue
		where parent!='Control Panel' 
		and substr(defkey,1,1)!='_'
		%s%s order by parent, defkey""" % (\
			user and (" and parent='%s'" % user) or "",
			key and (" and defkey='%s'" % key) or ""), as_dict=True)

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def remove(user, name):
	webnotes.defaults.clear_default(name=name)
	
@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def add(parent, defkey, defvalue):
	webnotes.defaults.add_user_default(defkey, defvalue, parent)
	
def get_defvalue(doctype, txt, searchfield, start, page_len, filters):
	return webnotes.conn.sql("""select name from `tab%s` where name like %s limit 20""" % 
		(filters.get("doctype"), "%s"), "%s%%" % (txt,))