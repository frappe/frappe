# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

from __future__ import unicode_literals
import webnotes
from webnotes import msgprint
import json
import csv, cStringIO
from webnotes.utils import encode, cstr, cint, flt

def read_csv_content_from_uploaded_file(ignore_encoding=False):
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
	try:
		reader = csv.reader(fcontent.splitlines())
		# decode everything
		csvrows = [[val for val in row] for row in reader]
		
		for row in csvrows:
			newrow = []
			for val in row:
				if ignore_encoding:
					newrow.append(cstr(val.strip()))
				else:
					try:
						newrow.append(unicode(val.strip(), 'utf-8'))
					except UnicodeDecodeError, e:
						webnotes.msgprint("""Some character(s) in row #%s, column #%s are
							not readable by utf-8. Ignoring them. If you are importing a non
							english language, please make sure your file is saved in the 'utf-8'
							encoding.""" % (csvrows.index(row)+1, row.index(val)+1))
						raise Exception
					
			rows.append(newrow)
		
		return rows
	except Exception, e:
		webnotes.msgprint("Not a valid Comma Separated Value (CSV File)")
		raise e

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
						webnotes.msgprint("%s must be a valid %s" % (docfield.label, link_doctype), 
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

def import_doc(d, doctype, overwrite, row_idx, submit=False):
	"""import main (non child) document"""
	if webnotes.conn.exists(doctype, d['name']):
		if overwrite:
			bean = webnotes.bean(doctype, d['name'])
			bean.doc.fields.update(d)
			if d.get("docstatus") == 1:
				bean.update_after_submit()
			else:
				bean.save()
			return 'Updated row (#%d) %s' % (row_idx, getlink(doctype, d['name']))
		else:
			return 'Ignored row (#%d) %s (exists)' % (row_idx, 
				getlink(doctype, d['name']))
	else:
		bean = webnotes.bean([d])
		bean.insert()
		
		if submit:
			bean.submit()
		
		return 'Inserted row (#%d) %s' % (row_idx, getlink(doctype,
			bean.doc.fields['name']))
			
def getlink(doctype, name):
	return '<a href="#Form/%(doctype)s/%(name)s">%(name)s</a>' % locals()
