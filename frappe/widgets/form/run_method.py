# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import json, inspect
import frappe
from frappe import _

@frappe.whitelist()
def runserverobj():
	"""
		Run server objects
	"""
	from frappe.utils import cint

	method = frappe.form_dict.get('method')
	dt = frappe.form_dict.get('doctype')
	dn = frappe.form_dict.get('docname')

	if dt: # not called from a doctype (from a page)
		if not dn: dn = dt # single
		doc = frappe.get_doc(dt, dn)

	else:
		doc = frappe.get_doc(json.loads(frappe.form_dict.get('docs')))
		doc._original_modified = doc.modified
		doc.check_if_latest()

	if not doc.has_permission("read"):
		frappe.msgprint(_("Not permitted"), raise_exception = True)

	if doc:
		try:
			args = frappe.form_dict.get('args', frappe.form_dict.get("arg"))
			args = json.loads(args)
		except ValueError:
			try:
				r = doc.run_method(method, args)
			except TypeError:
				r = doc.run_method(method)
			else:
				fnargs, varargs, varkw, defaults = inspect.getargspec(getattr(doc, method))
				if "args" in fnargs:
					r = doc.run_method(method, args)
				else:
					r = doc.run_method(method, **args)

		if r:
			#build output as csv
			if cint(frappe.form_dict.get('as_csv')):
				make_csv_output(r, doc.doctype)
			else:
				frappe.response['message'] = r

		frappe.response.docs.append(doc)

def make_csv_output(res, dt):
	"""send method response as downloadable CSV file"""
	import frappe

	from cStringIO import StringIO
	import csv

	f = StringIO()
	writer = csv.writer(f)
	for r in res:
		row = []
		for v in r:
			if isinstance(v, basestring):
				v = v.encode("utf-8")
			row.append(v)
		writer.writerow(row)

	f.seek(0)

	frappe.response['result'] = unicode(f.read(), 'utf-8')
	frappe.response['type'] = 'csv'
	frappe.response['doctype'] = dt.replace(' ','')
