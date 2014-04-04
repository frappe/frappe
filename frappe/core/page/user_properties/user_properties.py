# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.defaults
import frappe.permissions
from frappe.core.doctype.user.user import get_system_users

@frappe.whitelist()
def get_users_and_links():
	return {
		"users": get_system_users(),
		"link_fields": get_restrictable_doctypes()
	}

@frappe.whitelist()
def get_properties(parent=None, defkey=None, defvalue=None):
	if defkey and not frappe.permissions.can_restrict(defkey, defvalue):
		raise frappe.PermissionError
	
	conditions, values = _build_conditions(locals())
	
	properties = frappe.db.sql("""select name, parent, defkey, defvalue 
		from tabDefaultValue
		where parent not in ('__default', '__global')
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

@frappe.whitelist()
def remove(user, name, defkey, defvalue):
	if not frappe.permissions.can_restrict_user(user, defkey, defvalue):
		raise frappe.PermissionError("Cannot Remove Restriction for User: {user} on DocType: {doctype} and Name: {name}".format(
			user=user, doctype=defkey, name=defvalue))
	
	frappe.defaults.clear_default(name=name)
	
def clear_restrictions(doctype):
	frappe.defaults.clear_default(parenttype="Restriction", key=doctype)
	
@frappe.whitelist()
def add(user, defkey, defvalue):
	if not frappe.permissions.can_restrict_user(user, defkey, defvalue):
		raise frappe.PermissionError("Cannot Restrict User: {user} for DocType: {doctype} and Name: {name}".format(
			user=user, doctype=defkey, name=defvalue))
	
	# check if already exists
	d = frappe.db.sql("""select name from tabDefaultValue 
		where parent=%s and parenttype='Restriction' and defkey=%s and defvalue=%s""", (user, defkey, defvalue))
		
	if not d:
		frappe.defaults.add_default(defkey, defvalue, user, "Restriction")
		
def get_restrictable_doctypes():
	user_roles = frappe.get_roles()
	condition = ""
	values = []
	if "System Manager" not in user_roles:
		condition = """and exists(select `tabDocPerm`.name from `tabDocPerm` 
			where `tabDocPerm`.parent=`tabDocType`.name and `tabDocPerm`.`restrict`=1
			and `tabDocPerm`.role in ({roles}))""".format(roles=", ".join(["%s"]*len(user_roles)))
		values = user_roles
	
	return frappe.db.sql_list("""select name from tabDocType 
		where ifnull(issingle,0)=0 and ifnull(istable,0)=0 {condition}""".format(condition=condition),
		tuple(values))
