# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import webnotes.defaults
import webnotes.permissions

@webnotes.whitelist()
def get_users_and_links():
	return {
		"users": webnotes.conn.sql_list("""select name from tabProfile where
			ifnull(enabled,0)=1 and
			name not in ("Administrator", "Guest")"""),
		"link_fields": get_restrictable_doctypes()
	}

@webnotes.whitelist()
def get_properties(parent=None, defkey=None, defvalue=None):
	if defkey and not webnotes.permissions.can_restrict(defkey, defvalue):
		raise webnotes.PermissionError
	
	conditions, values = _build_conditions(locals())
	
	properties = webnotes.conn.sql("""select name, parent, defkey, defvalue 
		from tabDefaultValue
		where parent not in ('Control Panel', '__global')
		and substr(defkey,1,1)!='_'
		and parenttype='Restriction'
		{conditions}
		order by parent, defkey""".format(conditions=conditions), values, as_dict=True)
	
	if not defkey:
		out = []
		doctypes = get_restrictable_doctypes()
		for p in properties:
			if p.defkey in doctypes:
				out.append(p)
		properties = out
	
	return properties
			
def _build_conditions(filters):
	conditions = []
	values = {}
	for key, value in filters.items():
		if filters.get(key):
			conditions.append("and `{key}`=%({key})s".format(key=key))
			values[key] = value
		
	return "\n".join(conditions), values

@webnotes.whitelist()
def remove(user, name, defkey, defvalue):
	if not webnotes.permissions.can_restrict_user(user, defkey, defvalue):
		raise webnotes.PermissionError("Cannot Remove Restriction for User: {user} on DocType: {doctype} and Name: {name}".format(
			user=user, doctype=defkey, name=defvalue))
	
	webnotes.defaults.clear_default(name=name)
	
@webnotes.whitelist()
def add(user, defkey, defvalue):
	if not webnotes.permissions.can_restrict_user(user, defkey, defvalue):
		raise webnotes.PermissionError("Cannot Restrict User: {user} for DocType: {doctype} and Name: {name}".format(
			user=user, doctype=defkey, name=defvalue))
	
	# check if already exists
	d = webnotes.conn.sql("""select name from tabDefaultValue 
		where parent=%s and parenttype='Restriction' and defkey=%s and defvalue=%s""", (user, defkey, defvalue))
		
	if not d:
		webnotes.defaults.add_default(defkey, defvalue, user, "Restriction")
		
def get_restrictable_doctypes():
	user_roles = webnotes.get_roles()
	condition = ""
	values = []
	if "System Manager" not in user_roles:
		condition = """and exists(select `tabDocPerm`.name from `tabDocPerm` 
			where `tabDocPerm`.parent=`tabDocType`.name and restrict=1
			and `tabDocPerm`.name in ({roles}))""".format(roles=", ".join(["%s"]*len(user_roles)))
		values = user_roles
	
	return webnotes.conn.sql_list("""select name from tabDocType 
		where ifnull(issingle,0)=0 and ifnull(istable,0)=0 {condition}""".format(condition=condition),
		values)
