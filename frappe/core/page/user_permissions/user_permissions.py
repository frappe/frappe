# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import frappe.defaults
import frappe.permissions
from frappe.core.doctype.user.user import get_system_users
from frappe.utils.csvutils import UnicodeWriter, read_csv_content_from_uploaded_file
from frappe.defaults import clear_default

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

	frappe.permissions.add_user_permission(defkey, defvalue, user, with_message=True)

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
		where issingle=0 and istable=0 {condition}""".format(condition=condition),
		tuple(values))

@frappe.whitelist()
def get_user_permissions_csv():
	out = [["User Permissions"], ["User", "Document Type", "Value"]]
	out += [[a.parent, a.defkey, a.defvalue] for a in get_permissions()]

	csv = UnicodeWriter()
	for row in out:
		csv.writerow(row)

	frappe.response['result'] = str(csv.getvalue())
	frappe.response['type'] = 'csv'
	frappe.response['doctype'] = "User Permissions"

@frappe.whitelist()
def import_user_permissions():
	frappe.only_for("System Manager")
	rows = read_csv_content_from_uploaded_file(ignore_encoding=True)
	clear_default(parenttype="User Permission")

	if rows[0][0]!="User Permissions" and rows[1][0] != "User":
		frappe.throw(frappe._("Please upload using the same template as download."))

	for row in rows[2:]:
		frappe.permissions.add_user_permission(row[1], row[2], row[0])
