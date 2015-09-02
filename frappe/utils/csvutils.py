# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
import json
import csv, cStringIO
from frappe.utils import encode, cstr, cint, flt, comma_or

def read_csv_content_from_uploaded_file(ignore_encoding=False):
	if getattr(frappe, "uploaded_file", None):
		with open(frappe.uploaded_file, "r") as upfile:
			fcontent = upfile.read()
	else:
		from frappe.utils.file_manager import get_uploaded_content
		fname, fcontent = get_uploaded_content()
	return read_csv_content(fcontent, ignore_encoding)

def read_csv_content_from_attached_file(doc):
	fileid = frappe.db.get_value("File", {"attached_to_doctype": doc.doctype,
		"attached_to_name":doc.name}, "name")

	if not fileid:
		msgprint(_("File not attached"))
		raise Exception

	try:
		from frappe.utils.file_manager import get_file
		fname, fcontent = get_file(fileid)
		return read_csv_content(fcontent, frappe.form_dict.get('ignore_encoding_errors'))
	except Exception:
		frappe.msgprint(_("Unable to open attached file. Please try again."))
		raise Exception

def read_csv_content(fcontent, ignore_encoding=False):
	rows = []

	if not isinstance(fcontent, unicode):
		decoded = False
		for encoding in ["utf-8", "windows-1250", "windows-1252"]:
			try:
				fcontent = unicode(fcontent, encoding)
				decoded = True
				break
			except UnicodeDecodeError:
				continue

		if not decoded:
			frappe.msgprint(_("Unknown file encoding. Tried utf-8, windows-1250, windows-1252."),
				raise_exception=True)

	fcontent = fcontent.encode("utf-8").splitlines(True)

	try:
		rows = []
		for row in csv.reader(fcontent):
			r = []
			for val in row:
				# decode everything
				val = unicode(val, "utf-8").strip()

				if val=="":
					# reason: in maraidb strict config, one cannot have blank strings for non string datatypes
					r.append(None)
				else:
					r.append(val)

			rows.append(r)

		return rows

	except Exception:
		frappe.msgprint(_("Not a valid Comma Separated Value (CSV File)"))
		raise

@frappe.whitelist()
def send_csv_to_client(args):
	if isinstance(args, basestring):
		args = json.loads(args)

	args = frappe._dict(args)

	frappe.response["result"] = cstr(to_csv(args.data))
	frappe.response["doctype"] = args.filename
	frappe.response["type"] = "csv"

def to_csv(data):
	writer = UnicodeWriter()
	for row in data:
		writer.writerow(row)

	return writer.getvalue()


class UnicodeWriter:
	def __init__(self, encoding="utf-8"):
		self.encoding = encoding
		self.queue = cStringIO.StringIO()
		self.writer = csv.writer(self.queue, quoting=csv.QUOTE_NONNUMERIC)

	def writerow(self, row):
		row = encode(row, self.encoding)
		self.writer.writerow(row)

	def getvalue(self):
		return self.queue.getvalue()

def check_record(d):
	"""check for mandatory, select options, dates. these should ideally be in doclist"""
	from frappe.utils.dateutils import parse_date
	doc = frappe.get_doc(d)

	for key in d:
		docfield = doc.meta.get_field(key)
		val = d[key]
		if docfield:
			if docfield.reqd and (val=='' or val==None):
				frappe.msgprint(_("{0} is required").format(docfield.label), raise_exception=1)

			if docfield.fieldtype=='Select' and val and docfield.options:
				if val not in docfield.options.split('\n'):
					frappe.throw(_("{0} must be one of {1}").format(_(docfield.label), comma_or(docfield.options.split("\n"))))

			if val and docfield.fieldtype=='Date':
				d[key] = parse_date(val)
			elif val and docfield.fieldtype in ["Int", "Check"]:
				d[key] = cint(val)
			elif val and docfield.fieldtype in ["Currency", "Float", "Percent"]:
				d[key] = flt(val)

def import_doc(d, doctype, overwrite, row_idx, submit=False, ignore_links=False):
	"""import main (non child) document"""
	if d.get("name") and frappe.db.exists(doctype, d['name']):
		if overwrite:
			doc = frappe.get_doc(doctype, d['name'])
			doc.flags.ignore_links = ignore_links
			doc.update(d)
			if d.get("docstatus") == 1:
				doc.update_after_submit()
			else:
				doc.save()
			return 'Updated row (#%d) %s' % (row_idx + 1, getlink(doctype, d['name']))
		else:
			return 'Ignored row (#%d) %s (exists)' % (row_idx + 1,
				getlink(doctype, d['name']))
	else:
		doc = frappe.get_doc(d)
		doc.flags.ignore_links = ignore_links
		doc.insert()

		if submit:
			doc.submit()

		return 'Inserted row (#%d) %s' % (row_idx + 1, getlink(doctype,
			doc.get('name')))

def getlink(doctype, name):
	return '<a href="#Form/%(doctype)s/%(name)s">%(name)s</a>' % locals()
