# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.defaults
from frappe.modules.import_file import get_file_path, read_doc_from_file
from frappe.translate import send_translations
from frappe.desk.notifications import delete_notification_count_for
from frappe.permissions import reset_perms, get_linked_doctypes

@frappe.whitelist()
def get_roles_and_doctypes():
	frappe.only_for("System Manager")
	send_translations(frappe.get_lang_dict("doctype", "DocPerm"))
	return {
		"doctypes": [d[0] for d in frappe.db.sql("""select name from `tabDocType` dt where
			istable=0 and
			name not in ('DocType') and
			exists(select * from `tabDocField` where parent=dt.name)""")],
		"roles": [d[0] for d in frappe.db.sql("""select name from tabRole where name not in
			('Administrator')""")]
	}

@frappe.whitelist()
def get_permissions(doctype=None, role=None):
	frappe.only_for("System Manager")
	out = frappe.db.sql("""select * from tabDocPerm
		where %s%s order by parent, permlevel, role""" %
		(doctype and (" parent='%s'" % frappe.db.escape(doctype)) or "",
		role and ((doctype and " and " or "") + " role='%s'" % frappe.db.escape(role)) or ""),
		as_dict=True)

	linked_doctypes = {}
	for d in out:
		d.linked_doctypes = linked_doctypes.setdefault(d.parent, get_linked_doctypes(d.parent))

	return out

@frappe.whitelist()
def remove(doctype, name):
	frappe.only_for("System Manager")
	frappe.db.sql("""delete from tabDocPerm where name=%s""", name)
	validate_and_reset(doctype, for_remove=True)

@frappe.whitelist()
def add(parent, role, permlevel):
	frappe.only_for("System Manager")
	frappe.get_doc({
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
def update(name, doctype, ptype, value=None):
	frappe.only_for("System Manager")
	frappe.db.sql("""update tabDocPerm set `%s`=%s where name=%s"""\
	 	% (frappe.db.escape(ptype), '%s', '%s'), (value, name))
	validate_and_reset(doctype)

def validate_and_reset(doctype, for_remove=False):
	from frappe.core.doctype.doctype.doctype import validate_permissions_for_doctype
	validate_permissions_for_doctype(doctype, for_remove)
	clear_doctype_cache(doctype)

@frappe.whitelist()
def reset(doctype):
	frappe.only_for("System Manager")
	reset_perms(doctype)
	clear_doctype_cache(doctype)

def clear_doctype_cache(doctype):
	frappe.clear_cache(doctype=doctype)
	delete_notification_count_for(doctype)
	for user in frappe.db.sql_list("""select distinct tabUserRole.parent from tabUserRole, tabDocPerm
		where tabDocPerm.parent = %s
		and tabDocPerm.role = tabUserRole.role""", doctype):
		frappe.clear_cache(user=user)

@frappe.whitelist()
def get_users_with_role(role):
	frappe.only_for("System Manager")
	return [p[0] for p in frappe.db.sql("""select distinct tabUser.name
		from tabUserRole, tabUser where
			tabUserRole.role=%s
			and tabUser.name != "Administrator"
			and tabUserRole.parent = tabUser.name
			and tabUser.enabled=1""", role)]

@frappe.whitelist()
def get_standard_permissions(doctype):
	frappe.only_for("System Manager")
	module = frappe.db.get_value("DocType", doctype, "module")
	path = get_file_path(module, "DocType", doctype)
	return read_doc_from_file(path).get("permissions")
