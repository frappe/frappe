import frappe

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
	for user_permission in frappe.get_all('User Permission', fields=['*']):
		skip_for_doctype = user_permission.skip_for_doctype.split('\n')
		if skip_for_doctype:
			# only specific doctypes are selected
			# split this into multiple records and delete
			frappe.db.sql('delete from `tabUser Permission` where name=%s', user_permission.name)
			user_permission.name = None
			user_permission.skip_for_doctype = None
			for doctype in skip_for_doctype:
				if doctype:
					new_user_permission = frappe.new_doc('User Permission')
					new_user_permission.update(user_permission)
					print(test)
					new_user_permission.applicable_for = doctype
					new_user_permission.db_insert()