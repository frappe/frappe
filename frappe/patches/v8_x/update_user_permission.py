import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'user_permission')
	frappe.delete_doc('core', 'page', 'user-permissions')
	for perm in frappe.db.sql("""
		select
			defval.name, defval.parent, defval.defkey, defval.defvalue
		from
			tabDefaultValue as defval,
			tabUser as usr
		where
			defval.parent not in ('__default', '__global')
		and
			substr(defval.defkey,1,1)!='_'
		and
			defval.parenttype='User Permission'
		and 
			usr.name=defval.parent
		""", as_dict=True):

			frappe.get_doc(dict(
				doctype='User Permission',
				user=perm.parent,
				allow=perm.defkey,
				for_value=perm.defvalue,
				apply_for_all_roles=0,
			)).insert(ignore_permissions = True)


	frappe.db.sql('delete from tabDefaultValue where parenttype="User Permission"')
