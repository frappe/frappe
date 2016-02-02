from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doctype("Feed")

	frappe.db.sql("update `tabFeed` set seen=1")

	for doctype, name in frappe.db.sql("""select distinct doc_type, doc_name from `tabFeed`
		where
			(doc_type is not null and doc_type != '')
			and (doc_name is not null and doc_name != '')
			and doc_type != 'Feed'
		for update"""):

		owner = frappe.db.get_value(doctype, name, "owner")

		if not owner:
			continue

		frappe.db.sql("""update `tabFeed`
			set doc_owner=%(owner)s
			where
				doc_type=%(doctype)s
				and doc_name=%(name)s
				and (doc_owner is null or doc_owner = '')""".format(doctype=doctype), {
					"doctype": doctype,
					"name": name,
					"owner": owner
				})

		frappe.db.commit()
