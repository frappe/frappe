# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
import frappe.desk.form.meta
import frappe.desk.form.load

from frappe import _

@frappe.whitelist()
def remove_attach():
	"""remove attachment"""
	import frappe.utils.file_manager
	fid = frappe.form_dict.get('fid')
	return frappe.utils.file_manager.remove_file(fid)

@frappe.whitelist()
def validate_link():
	"""validate link when updated by user"""
	import frappe
	import frappe.utils

	value, options, fetch = frappe.form_dict.get('value'), frappe.form_dict.get('options'), frappe.form_dict.get('fetch')

	# no options, don't validate
	if not options or options=='null' or options=='undefined':
		frappe.response['message'] = 'Ok'
		return

	if frappe.db.sql("select name from `tab%s` where name=%s" % (frappe.db.escape(options), '%s'), (value,)):

		# get fetch values
		if fetch:
			# escape with "`"
			fetch = ", ".join(("`{0}`".format(frappe.db.escape(f.strip())) for f in fetch.split(",")))

			frappe.response['fetch_values'] = [frappe.utils.parse_val(c) \
				for c in frappe.db.sql("select %s from `tab%s` where name=%s" \
					% (fetch, frappe.db.escape(options), '%s'), (value,))[0]]

		frappe.response['message'] = 'Ok'

@frappe.whitelist()
def add_comment(doc):
	"""allow any logged user to post a comment"""
	doc = frappe.get_doc(json.loads(doc))

	if doc.doctype != "Comment":
		frappe.throw(_("This method can only be used to create a Comment"), frappe.PermissionError)

	doc.insert(ignore_permissions = True)

	return doc.as_dict()

@frappe.whitelist()
def get_next(doctype, value, prev, filters=None, order_by="modified desc"):
	import frappe.desk.reportview

	prev = not int(prev)
	sort_field, sort_order = order_by.split(" ")

	if not filters: filters = []
	if isinstance(filters, basestring):
		filters = json.loads(filters)

	# condition based on sort order
	condition = ">" if sort_order.lower()=="desc" else "<"

	# switch the condition
	if prev:
		condition = "<" if condition==">" else "<"
	else:
		sort_order = "asc" if sort_order.lower()=="desc" else "desc"

	# add condition for next or prev item
	if not order_by[0] in [f[1] for f in filters]:
		filters.append([doctype, sort_field, condition, value])

	res = frappe.desk.reportview.execute(doctype,
		fields = ["name"],
		filters = filters,
		order_by = sort_field + " " + sort_order,
		limit_start=0, limit_page_length=1, as_list=True)

	if not res:
		frappe.msgprint(_("No further records"))
		return None
	else:
		return res[0][0]

