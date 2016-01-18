from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doctype("Communication")

	for doctype, name in frappe.db.sql("""select distinct reference_doctype, reference_name
		from `tabCommunication`
		where
			(reference_doctype is not null and reference_doctype != '')
			and (reference_name is not null and reference_name != '')
			and (reference_owner is null or reference_owner = '')
		for update"""):

		owner = frappe.db.get_value(doctype, name, "owner")

		if not owner:
			continue

		frappe.db.sql("""update `tabCommunication`
			set reference_owner=%(owner)s
			where
				reference_doctype=%(doctype)s
				and reference_name=%(name)s
				and (reference_owner is null or reference_owner = '')""".format(doctype=doctype), {
					"doctype": doctype,
					"name": name,
					"owner": owner
				})

		frappe.db.commit()
