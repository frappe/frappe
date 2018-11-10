import frappe
from frappe.desk.form.linked_with import get_linked_doctypes

# `skip_for_doctype` was a un-normalized way of storing for which
# doctypes the user permission was applicable.
# in this patch, we normalize this into `applicable_for` where
# a new record will be created for each doctype where the user permission
# is applicable
#
# if the user permission is applicable for all doctypes, then only
# one record is created

def execute():
	frappe.reload_doctype('User Permission')
	linked_with_map = {}
	for user_permission in frappe.get_all('User Permission', fields=['*']):
		if not user_permission.skip_for_doctype: continue
		skip_for_doctype = user_permission.skip_for_doctype.split('\n')
		if skip_for_doctype:
			# only specific doctypes are selected
			# split this into multiple records and delete
			if linked_with_map.get(user_permission.allow) == None:
				linked_with_map[user_permission.allow] = get_linked_doctypes(user_permission.allow, True).keys()
			# linked with doctypes that are not in skip_for_doctype
			applicable_for_doctypes = filter(lambda d: d not in skip_for_doctype, linked_with_map[user_permission.allow])
			frappe.db.sql('DELETE FROM `tabUser Permission` WHERE `name`=%s', user_permission.name)
			user_permission.name = None
			user_permission.skip_for_doctype = None
			for doctype in applicable_for_doctypes:
				if doctype:
					new_user_permission = frappe.new_doc('User Permission')
					new_user_permission.update(user_permission)
					new_user_permission.applicable_for = doctype
					new_user_permission.db_insert()