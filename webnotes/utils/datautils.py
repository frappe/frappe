# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import msgprint, _
import json
import csv, cStringIO
from webnotes.utils import encode, cstr, cint, flt

def read_csv_content_from_uploaded_file(ignore_encoding=False):
	if getattr(webnotes, "uploaded_file", None):
		with open(webnotes.uploaded_file, "r") as upfile:
			fcontent = upfile.read()
	else:
		from webnotes.utils.file_manager import get_uploaded_content
		fname, fcontent = get_uploaded_content()
	return read_csv_content(fcontent, ignore_encoding)

def read_csv_content_from_attached_file(doc):
	fileid = webnotes.conn.get_value("File Data", {"attached_to_doctype": doc.doctype,
		"attached_to_name":doc.name}, "name")
	if not fileid:
		msgprint("File not attached!")
		raise Exception

	try:
		from webnotes.utils.file_manager import get_file
		fname, fcontent = get_file(fileid)
		return read_csv_content(fcontent, webnotes.form_dict.get('ignore_encoding_errors'))
	except Exception, e:
		webnotes.msgprint("""Unable to open attached file. Please try again.""")
		raise Exception

def read_csv_content(fcontent, ignore_encoding=False):
	rows = []

	decoded = False
	for encoding in ["utf-8", "windows-1250", "windows-1252"]:
		try:
			fcontent = unicode(fcontent, encoding)
			decoded = True
			break
		except UnicodeDecodeError, e:
			continue

	if not decoded:
		webnotes.msgprint(webnotes._("Unknown file encoding. Tried utf-8, windows-1250, windows-1252."), 
			raise_exception=True)

	try:
		reader = csv.reader(fcontent.encode("utf-8").splitlines(True))
		# decode everything
		rows = [[unicode(val, "utf-8").strip() for val in row] for row in reader]
		return rows
	except Exception, e:
		webnotes.msgprint("Not a valid Comma Separated Value (CSV File)")
		raise

@webnotes.whitelist()
def send_csv_to_client(args):
	if isinstance(args, basestring):
		args = json.loads(args)
	
	args = webnotes._dict(args)
	
	webnotes.response["result"] = cstr(to_csv(args.data))
	webnotes.response["doctype"] = args.filename
	webnotes.response["type"] = "csv"
	
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
		
def check_record(d, parenttype=None, doctype_dl=None):
	"""check for mandatory, select options, dates. these should ideally be in doclist"""
	from webnotes.utils.dateutils import parse_date
	if parenttype and not d.get('parent'):
		webnotes.msgprint(_("Parent is required."), raise_exception=1)

	if not doctype_dl:
		doctype_dl = webnotes.model.doctype.get(d.doctype)

	for key in d:
		docfield = doctype_dl.get_field(key)
		val = d[key]
		if docfield:
			if docfield.reqd and (val=='' or val==None):
				webnotes.msgprint("%s is mandatory." % docfield.label, raise_exception=1)

			if docfield.fieldtype=='Select' and val and docfield.options:
				if docfield.options.startswith('link:'):
					link_doctype = docfield.options.split(':')[1]
					if not webnotes.conn.exists(link_doctype, val):
						webnotes.msgprint("%s: %s must be a valid %s" % (docfield.label, val, link_doctype), 
							raise_exception=1)
				elif docfield.options == "attach_files:":
					pass
					
				elif val not in docfield.options.split('\n'):
					webnotes.msgprint("%s must be one of: %s" % (docfield.label, 
						", ".join(filter(None, docfield.options.split("\n")))), raise_exception=1)
					
			if val and docfield.fieldtype=='Date':
				d[key] = parse_date(val)
			elif val and docfield.fieldtype in ["Int", "Check"]:
				d[key] = cint(val)
			elif val and docfield.fieldtype in ["Currency", "Float"]:
				d[key] = flt(val)

def import_doc(d, doctype, overwrite, row_idx, submit=False, ignore_links=False):
	"""import main (non child) document"""
	if d.get("name") and webnotes.conn.exists(doctype, d['name']):
		if overwrite:
			bean = webnotes.bean(doctype, d['name'])
			bean.ignore_links = ignore_links
			bean.doc.fields.update(d)
			if d.get("docstatus") == 1:
				bean.update_after_submit()
			else:
				bean.save()
			return 'Updated row (#%d) %s' % (row_idx + 1, getlink(doctype, d['name']))
		else:
			return 'Ignored row (#%d) %s (exists)' % (row_idx + 1, 
				getlink(doctype, d['name']))
	else:
		bean = webnotes.bean([d])
		bean.ignore_links = ignore_links
		bean.insert()
		
		if submit:
			bean.submit()
		
		return 'Inserted row (#%d) %s' % (row_idx + 1, getlink(doctype,
			bean.doc.fields['name']))
			
def getlink(doctype, name):
	return '<a href="#Form/%(doctype)s/%(name)s">%(name)s</a>' % locals()
