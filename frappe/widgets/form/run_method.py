# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
from frappe import _

@frappe.whitelist()
def runserverobj():
	"""
		Run server objects
	"""
	import frappe.model.code
	from frappe.model.bean import Bean
	from frappe.utils import cint

	wrapper = None
	method = frappe.form_dict.get('method')
	arg = frappe.form_dict.get('args', frappe.form_dict.get("arg"))
	dt = frappe.form_dict.get('doctype')
	dn = frappe.form_dict.get('docname')
	
	frappe.response["docs"] = []
	
	if dt: # not called from a doctype (from a page)
		if not dn: dn = dt # single
		so = frappe.model.code.get_obj(dt, dn)

	else:
		bean = Bean()
		bean.from_compressed(frappe.form_dict.get('docs'), dn)
		if not bean.has_read_perm():
			frappe.msgprint(_("No Permission"), raise_exception = True)
		so = bean.make_controller()
		bean.check_if_latest(method="runserverobj")

	check_guest_access(so.doc)
	
	if so:
		r = frappe.model.code.run_server_obj(so, method, arg)
		if r:
			#build output as csv
			if cint(frappe.form_dict.get('as_csv')):
				make_csv_output(r, so.doc.doctype)
			else:
				frappe.response['message'] = r
		
		frappe.response['docs'] += so.doclist

def check_guest_access(doc):
	if frappe.session['user']=='Guest' and not frappe.db.sql("select name from tabDocPerm where role='Guest' and parent=%s and ifnull(`read`,0)=1", doc.doctype):
		frappe.msgprint("Guest not allowed to call this object")
		raise Exception

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