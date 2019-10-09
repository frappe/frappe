# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import json, inspect
import frappe
from frappe import _
from frappe.utils import cint
from six import text_type, string_types

@frappe.whitelist()
def runserverobj(method, docs=None, dt=None, dn=None, arg=None, args=None):
	"""run controller method - old style"""
	if not args: args = arg or ""

	if dt: # not called from a doctype (from a page)
		if not dn: dn = dt # single
		doc = frappe.get_doc(dt, dn)

	else:
		doc = frappe.get_doc(json.loads(docs))
		doc._original_modified = doc.modified
		doc.check_if_latest()

	if not doc.has_permission("read"):
		frappe.msgprint(_("Not permitted"), raise_exception = True)

	if doc:
		try:
			args = json.loads(args)
		except ValueError:
			args = args

		try:
			fnargs, varargs, varkw, defaults = inspect.getargspec(getattr(doc, method))
		except ValueError:
			fnargs = inspect.getfullargspec(getattr(doc, method)).args
			varargs = inspect.getfullargspec(getattr(doc, method)).varargs
			varkw = inspect.getfullargspec(getattr(doc, method)).varkw
			defaults = inspect.getfullargspec(getattr(doc, method)).defaults

		if not fnargs or (len(fnargs)==1 and fnargs[0]=="self"):
			r = doc.run_method(method)

		elif "args" in fnargs or not isinstance(args, dict):
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

	from six import StringIO
	import csv

	f = StringIO()
	writer = csv.writer(f)
	for r in res:
		row = []
		for v in r:
			if isinstance(v, string_types):
				v = v.encode("utf-8")
			row.append(v)
		writer.writerow(row)

	f.seek(0)

	frappe.response['result'] = text_type(f.read(), 'utf-8')
	frappe.response['type'] = 'csv'
	frappe.response['doctype'] = dt.replace(' ','')
