# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.defaults

@webnotes.whitelist()
def get_users_and_links():
	webnotes.only_for(("System Manager", "Administrator"))
	return {
		"users": [d[0] for d in webnotes.conn.sql("""select name from tabProfile where
			ifnull(enabled,0)=1 and
			name not in ("Administrator", "Guest")""")],
		"link_fields": webnotes.conn.sql("""select name, name from tabDocType 
			where ifnull(issingle,0)=0 and ifnull(istable,0)=0""")
	}
	
@webnotes.whitelist()
def get_properties(user=None, key=None):
	webnotes.only_for(("System Manager", "Administrator"))
	return webnotes.conn.sql("""select name, parent, defkey, defvalue 
		from tabDefaultValue
		where parent!='Control Panel' 
		and parenttype='Restriction'
		and substr(defkey,1,1)!='_'
		%s%s order by parent, defkey""" % (\
			user and (" and parent='%s'" % user) or "",
			key and (" and defkey='%s'" % key) or ""), as_dict=True)

@webnotes.whitelist()
def remove(user, name):
	webnotes.only_for(("System Manager", "Administrator"))
	webnotes.defaults.clear_default(name=name)
	
@webnotes.whitelist()
def add(parent, defkey, defvalue):
	webnotes.only_for(("System Manager", "Administrator"))
	webnotes.defaults.add_default(defkey, defvalue, parent, "Restriction")