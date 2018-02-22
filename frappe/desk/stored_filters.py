from __future__ import unicode_literals
import frappe
import json

@frappe.whitelist()
def get_filters(dt):

	# global filters
	global_filters = frappe.get_all("Stored Filter", \
		filters={"filter_doctype": dt, "user_id": ""}, \
		order_by="label"
	)

	# user filters
	user_filters = frappe.get_all("Stored Filter", \
		filters={"filter_doctype": dt, "user_id": frappe.session.user}, \
		order_by="label"
	)

	result = []

	for f in global_filters:
		doc = frappe.get_doc("Stored Filter", f["name"])
		result.append(doc.as_dict())

	for f in user_filters:
		doc = frappe.get_doc("Stored Filter", f["name"])
		result.append(doc.as_dict())

	frappe.response["docs"] = result
	return "Success" if len(result) > 0 else "Empty"

@frappe.whitelist()
def remove(name):
	frappe.delete_doc("Stored Filter", name, ignore_permissions=1)
	return

@frappe.whitelist()
def add(label, filter_doctype, filter_list, user=None):

	if isinstance(filter_list, unicode):
		filter_list = json.loads(filter_list)

	doc = frappe.get_doc({
		"doctype": "Stored Filter",
		"label": label,
		"filter_doctype": filter_doctype,
		"user_id": user
	})

	doc.flags.ignore_permissions=1
	doc.insert()

	for f in filter_list:
		f["doctype"] = "Stored Filter Item"
		doc.append("filter_list", f)

	doc.save()

	frappe.db.commit()

	return
