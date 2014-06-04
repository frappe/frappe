# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.defaults
import frappe.permissions
from frappe.core.doctype.user.user import get_system_users

@frappe.whitelist()
def get_users_and_links():
	return {
		"users": get_system_users(),
		"link_fields": get_doctypes_for_user_permissions()
	}

@frappe.whitelist()
def get_permissions(parent=None, defkey=None, defvalue=None):
	if defkey and not frappe.permissions.can_set_user_permissions(defkey, defvalue):
		raise frappe.PermissionError

	conditions, values = _build_conditions(locals())

	permissions = frappe.db.sql("""select name, parent, defkey, defvalue
		from tabDefaultValue
		where parent not in ('__default', '__global')
		and substr(defkey,1,1)!='_'
		and parenttype='User Permission'
		{conditions}
		order by parent, defkey""".format(conditions=conditions), values, as_dict=True)

	if not defkey:
		out = []
		doctypes = get_doctypes_for_user_permissions()
		for p in permissions:
			if p.defkey in doctypes:
				out.append(p)
		permissions = out

	return permissions

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
	if not frappe.permissions.can_set_user_permissions(defkey, defvalue):
		frappe.throw(_("Cannot remove permission for DocType: {0} and Name: {1}").format(
			defkey, defvalue), frappe.PermissionError)

	frappe.permissions.remove_user_permission(defkey, defvalue, user, name)

@frappe.whitelist()
def add(user, defkey, defvalue):
	if not frappe.permissions.can_set_user_permissions(defkey, defvalue):
		frappe.throw(_("Cannot set permission for DocType: {0} and Name: {1}").format(
			defkey, defvalue), frappe.PermissionError)

	frappe.permissions.add_user_permission(defkey, defvalue, user)

def get_doctypes_for_user_permissions():
	user_roles = frappe.get_roles()
	condition = ""
	values = []
	if "System Manager" not in user_roles:
		condition = """and exists(select `tabDocPerm`.name from `tabDocPerm`
			where `tabDocPerm`.parent=`tabDocType`.name and `tabDocPerm`.`set_user_permissions`=1
			and `tabDocPerm`.role in ({roles}))""".format(roles=", ".join(["%s"]*len(user_roles)))
		values = user_roles

	return frappe.db.sql_list("""select name from tabDocType
		where ifnull(issingle,0)=0 and ifnull(istable,0)=0 {condition}""".format(condition=condition),
		tuple(values))
