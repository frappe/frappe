# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.defaults
from frappe.modules.import_file import get_file_path, read_doc_from_file
from frappe.translate import send_translations
from frappe.desk.notifications import delete_notification_count_for
from frappe.permissions import reset_perms, get_linked_doctypes, get_all_perms, setup_custom_perms
from frappe import _

@frappe.whitelist()
def get_roles_and_doctypes():
	frappe.only_for("System Manager")
	send_translations(frappe.get_lang_dict("doctype", "DocPerm"))
	return {
		"doctypes": [d[0] for d in frappe.db.sql("""select name from `tabDocType` dt where
			istable=0 and name not in ('DocType')""")],
		"roles": [d[0] for d in frappe.db.sql("""select name from tabRole where
			name != 'Administrator' and disabled=0""")]
	}

@frappe.whitelist()
def get_permissions(doctype=None, role=None):
	frappe.only_for("System Manager")
	if role:
		out = get_all_perms(role)
		if doctype:
			out = [p for p in out if p.parent == doctype]
	else:
		out = frappe.get_all('Custom DocPerm', fields='*', filters=dict(parent = doctype), order_by="permlevel")
		if not out:
			out = frappe.get_all('DocPerm', fields='*', filters=dict(parent = doctype), order_by="permlevel")

	linked_doctypes = {}
	for d in out:
		if not d.parent in linked_doctypes:
			linked_doctypes[d.parent] = get_linked_doctypes(d.parent)
		d.linked_doctypes = linked_doctypes[d.parent]

	return out

@frappe.whitelist()
def add(parent, role, permlevel):
	frappe.only_for("System Manager")
	setup_custom_perms(parent)

	frappe.get_doc({
		"doctype":"Custom DocPerm",
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
def update(doctype, role, permlevel, ptype, value=None):
	frappe.only_for("System Manager")

	out = None
	if setup_custom_perms(doctype):
		out = 'refresh'

	name = frappe.get_value('Custom DocPerm', dict(parent=doctype, role=role, permlevel=permlevel))

	frappe.db.sql("""update `tabCustom DocPerm` set `%s`=%s where name=%s"""\
	 	% (frappe.db.escape(ptype), '%s', '%s'), (value, name))
	validate_and_reset(doctype)

	return out

@frappe.whitelist()
def remove(doctype, role, permlevel):
	frappe.only_for("System Manager")
	setup_custom_perms(doctype)

	name = frappe.get_value('Custom DocPerm', dict(parent=doctype, role=role, permlevel=permlevel))

	frappe.db.sql('delete from `tabCustom DocPerm` where name=%s', name)
	if not frappe.get_all('Custom DocPerm', dict(parent=doctype)):
		frappe.throw(_('There must be atleast one permission rule.'), title=_('Cannot Remove'))

	validate_and_reset(doctype, for_remove=True)

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
	for user in frappe.db.sql_list("""select distinct `tabHas Role`.parent from `tabHas Role`,
		tabDocPerm
			where tabDocPerm.parent = %s
			and tabDocPerm.role = `tabHas Role`.role""", doctype):
		frappe.clear_cache(user=user)

@frappe.whitelist()
def get_users_with_role(role):
	frappe.only_for("System Manager")
	return [p[0] for p in frappe.db.sql("""select distinct tabUser.name
		from `tabHas Role`, tabUser where
			`tabHas Role`.role=%s
			and tabUser.name != "Administrator"
			and `tabHas Role`.parent = tabUser.name
			and tabUser.enabled=1""", role)]

@frappe.whitelist()
def get_standard_permissions(doctype):
	frappe.only_for("System Manager")
	module = frappe.db.get_value("DocType", doctype, "module")
	path = get_file_path(module, "DocType", doctype)
	return read_doc_from_file(path).get("permissions")
