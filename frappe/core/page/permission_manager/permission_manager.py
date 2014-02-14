# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.defaults

@frappe.whitelist()
def get_roles_and_doctypes():
	frappe.only_for("System Manager")
	return {
		"doctypes": [d[0] for d in frappe.conn.sql("""select name from `tabDocType` dt where
			ifnull(istable,0)=0 and
			name not in ('DocType', 'Control Panel') and
			exists(select * from `tabDocField` where parent=dt.name)""")],
		"roles": [d[0] for d in frappe.conn.sql("""select name from tabRole where name not in
			('Guest', 'Administrator')""")]
	}

@frappe.whitelist()
def get_permissions(doctype=None, role=None):
	frappe.only_for("System Manager")
	return frappe.conn.sql("""select * from tabDocPerm
		where %s%s order by parent, permlevel, role""" % (\
			doctype and (" parent='%s'" % doctype) or "",
			role and ((doctype and " and " or "") + " role='%s'" % role) or "",
			), as_dict=True)
			
@frappe.whitelist()
def remove(doctype, name):
	frappe.only_for("System Manager")	
	frappe.conn.sql("""delete from tabDocPerm where name=%s""", name)
	validate_and_reset(doctype, for_remove=True)
	
@frappe.whitelist()
def add(parent, role, permlevel):
	frappe.only_for("System Manager")
	frappe.doc(fielddata={
		"doctype":"DocPerm",
		"__islocal": 1,
		"parent": parent,
		"parenttype": "DocType",
		"parentfield": "permissions",
		"role": role,
		"permlevel": permlevel,
		"read": 1
	}).save()
	
	validate_and_reset(parent)

@frappe.whitelist()
def update(name, doctype, ptype, value=0):
	frappe.only_for("System Manager")
	frappe.conn.sql("""update tabDocPerm set `%s`=%s where name=%s"""\
	 	% (ptype, '%s', '%s'), (value, name))
	validate_and_reset(doctype)
		
def validate_and_reset(doctype, for_remove=False):
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
	validate_permissions_for_doctype(doctype, for_remove)
	clear_doctype_cache(doctype)
	
@frappe.whitelist()
def reset(doctype):
	frappe.only_for("System Manager")
	frappe.reset_perms(doctype)
	clear_doctype_cache(doctype)

def clear_doctype_cache(doctype):
	frappe.clear_cache(doctype=doctype)
	for user in frappe.conn.sql_list("""select distinct tabUserRole.parent from tabUserRole, tabDocPerm 
		where tabDocPerm.parent = %s
		and tabDocPerm.role = tabUserRole.role""", doctype):
		frappe.clear_cache(user=user)

@frappe.whitelist()
def get_users_with_role(role):
	frappe.only_for("System Manager")
	return [p[0] for p in frappe.conn.sql("""select distinct tabProfile.name 
		from tabUserRole, tabProfile where 
			tabUserRole.role=%s
			and tabProfile.name != "Administrator"
			and tabUserRole.parent = tabProfile.name
			and ifnull(tabProfile.enabled,0)=1""", role)]

@frappe.whitelist
def get_standard_permissions():
	# TODO
	pass
