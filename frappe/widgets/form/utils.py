# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, json
import frappe.widgets.form.meta
import frappe.widgets.form.load

from frappe import _

@frappe.whitelist()
def remove_attach():
	"""remove attachment"""
	import frappe.utils.file_manager
	fid = frappe.form_dict.get('fid')
	frappe.utils.file_manager.remove_file(fid)

@frappe.whitelist()
def get_fields():
	"""get fields"""
	r = {}
	args = {
		'select':frappe.form_dict.get('select')
		,'from':frappe.form_dict.get('from')
		,'where':frappe.form_dict.get('where')
	}
	ret = frappe.db.sql("select %(select)s from `%(from)s` where %(where)s limit 1" % args)
	if ret:
		fl, i = frappe.form_dict.get('fields').split(','), 0
		for f in fl:
			r[f], i = ret[0][i], i+1
	frappe.response['message']=r

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

	if frappe.db.sql("select name from `tab%s` where name=%s" % (options, '%s'), (value,)):

		# get fetch values
		if fetch:
			frappe.response['fetch_values'] = [frappe.utils.parse_val(c) \
				for c in frappe.db.sql("select %s from `tab%s` where name=%s" \
					% (fetch, options, '%s'), (value,))[0]]

		frappe.response['message'] = 'Ok'

@frappe.whitelist()
def add_comment(doc):
	"""allow any logged user to post a comment"""
	doc = frappe.get_doc(json.loads(doc))
	doc.insert(ignore_permissions = True)

	return doc.as_dict()

@frappe.whitelist()
def get_next(doctype, name, prev):
	import frappe.widgets.reportview

	prev = int(prev)
	field = "`tab%s`.name" % doctype
	res = frappe.widgets.reportview.execute(doctype,
		fields = [field],
		filters = [[doctype, "name", "<" if prev else ">", name]],
		order_by = field + " " + ("desc" if prev else "asc"),
		limit_start=0, limit_page_length=1, as_list=True)

	if not res:
		frappe.msgprint(_("No further records"))
		return None
	else:
		return res[0][0]

@frappe.whitelist()
def get_linked_docs(doctype, name, metadata_loaded=None):
	if not metadata_loaded: metadata_loaded = []
	meta = frappe.widgets.form.meta.get_meta(doctype)
	linkinfo = meta.get("__linked_with")
	results = {}
	for dt, link in linkinfo.items():
		link["doctype"] = dt
		link_meta_bundle = frappe.widgets.form.load.get_meta_bundle(dt)
		linkmeta = link_meta_bundle[0]
		if not linkmeta.get("issingle"):
			fields = [d.fieldname for d in linkmeta.get("fields", {"in_list_view":1,
				"fieldtype": ["not in", ["Image", "HTML", "Button", "Table"]]})] \
				+ ["name", "modified", "docstatus"]

			fields = ["`tab{dt}`.`{fn}`".format(dt=dt, fn=sf.strip()) for sf in fields if sf]

			if link.get("child_doctype"):
				ret = frappe.get_list(doctype=dt, fields=fields,
					filters=[[link.get('child_doctype'), link.get("fieldname"), '=', name]])

			else:
				ret = frappe.get_list(doctype=dt, fields=fields,
					filters=[[dt, link.get("fieldname"), '=', name]])

			if ret:
				results[dt] = ret

			if not dt in metadata_loaded:
				frappe.local.response.docs.extend(link_meta_bundle)


	return results
