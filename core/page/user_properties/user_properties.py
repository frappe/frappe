# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.defaults

@webnotes.whitelist()
def get_users_and_links():
	webnotes.only_for(("System Manager", "Administrator"))
	return {
		"users": webnotes.conn.sql_list("""select name from tabProfile where
			ifnull(enabled,0)=1 and
			name not in ("Administrator", "Guest")"""),
		"link_fields": webnotes.conn.sql("""select name, name from tabDocType 
			where ifnull(issingle,0)=0 and ifnull(istable,0)=0""")
	}

@webnotes.whitelist()
def get_properties(parent=None, defkey=None, defvalue=None):
	webnotes.only_for(("System Manager", "Administrator"))
	conditions, values = _build_conditions(locals())
	
	return webnotes.conn.sql("""select name, parent, defkey, defvalue 
		from tabDefaultValue
		where parent not in ('Control Panel', '__global')
		and substr(defkey,1,1)!='_'
		and parenttype='Restriction'
		{conditions}
		order by parent, defkey""".format(conditions=conditions), values, as_dict=True)
			
def _build_conditions(filters):
	conditions = []
	values = {}
	for key, value in filters.items():
		if filters.get(key):
			conditions.append("and `{key}`=%({key})s".format(key=key))
			values[key] = value
		
	return "\n".join(conditions), values

@webnotes.whitelist()
def remove(user, name):
	webnotes.only_for(("System Manager", "Administrator"))
	webnotes.defaults.clear_default(name=name)
	
@webnotes.whitelist()
def add(user, defkey, defvalue):
	webnotes.only_for(("System Manager", "Administrator"))

	# check if already exists
	d = webnotes.conn.sql("""select name from tabDefaultValue 
		where parent=%s and parenttype='Restriction' and defkey=%s and defvalue=%s""", (user, defkey, defvalue))
		
	if not d:
		webnotes.defaults.add_default(defkey, defvalue, user, "Restriction")