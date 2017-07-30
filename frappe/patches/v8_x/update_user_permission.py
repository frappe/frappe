import frappe

def execute():
	frappe.reload_doc('core', 'doctype', 'user_permission')
	frappe.delete_doc('core', 'page', 'user-permissions')
	for perm in frappe.db.sql("""
		select
			name, parent, defkey, defvalue
		from
			tabDefaultValue
		where
			parent not in ('__default', '__global')
		and
			substr(defkey,1,1)!='_'
		and
			parenttype='User Permission'
		""", as_dict=True):
		frappe.get_doc(dict(
			doctype='User Permission',
			user=perm.parent,
			allow=perm.defkey,
			for_value=perm.defvalue
		)).insert(ignore_permissions = True)

	frappe.db.sql('delete from tabDefaultValue where parenttype="User Permission"')
