from __future__ import unicode_literals
import webnotes
from webnotes.utils import cstr

@webnotes.whitelist()
def get_doctypes():
    return [r[0] for r in webnotes.conn.sql("""select name from `tabDocType` 
		where document_type = 'Master'""")]	
		
@webnotes.whitelist()
def get_doctype_options():
	import webnotes
	doctype = webnotes.form_dict['doctype']
	import webnotes.model.doctype
	return [doctype] + filter(None, map(lambda d: \
		d.doctype=='DocField' and d.fieldtype=='Table' and d.options or None, 
		webnotes.model.doctype.get(doctype, form=0)))

data_separator = '----Start entering data below this line----'

doctype_dl = None

@webnotes.whitelist(allow_roles=['System Manager', 'Administrator'])
def get_template():
	import webnotes
	import webnotes.model.doctype
	global doctype_dl

	doctype = webnotes.form_dict['doctype']
	parenttype = webnotes.form_dict.get('parent_doctype')
	
	doctype_dl = webnotes.model.doctype.get(doctype)
	tablecolumns = [f[0] for f in webnotes.conn.sql('desc `tab%s`' % doctype)]
	
	def getinforow(docfield):
		"""make info comment"""
		if docfield.fieldtype == 'Select':
			if not docfield.options:
				return ''
			elif docfield.options.startswith('link:'):
				return 'Valid %s' % docfield.options[5:]
			else:
				return 'One of: %s' % ', '.join(filter(None, docfield.options.split('\n')))
		if docfield.fieldtype == 'Link':
			return 'Valid %s' % docfield.options
		if docfield.fieldtype in ('Int'):
			return 'Integer'
		else:
			return ''
			
	w = UnicodeWriter()
	key = 'name'
	
	w.writerow(['Upload Template for: %s' % doctype])
	
	if parenttype != doctype:
		w.writerow(['This is a child table for: %s' % parenttype])
		key = 'parent'
	else:
		w.writerow([''])
	
	w.writerow(['----'])
	
	fieldrow = ['Column Name:', key]
	mandatoryrow = ['Mandatory:', 'Yes']
	typerow = ['Type:', 'Data (text)']
	inforow = ['Info:', 'ID']
	columns = [key]
	
	def append_row(t, mandatory):
		docfield = getdocfield(t)
		if docfield and ((mandatory and docfield.reqd) or (not mandatory and not docfield.reqd)) \
			and (t not in ('parenttype', 'trash_reason', 'file_list')):
			fieldrow.append(t)
			mandatoryrow.append(docfield.reqd and 'Yes' or 'No')
			typerow.append(docfield.fieldtype)
			inforow.append(getinforow(docfield))
			columns.append(t)
	
	# get all mandatory fields
	for t in tablecolumns:
		append_row(t, True)

	# all non mandatory fields
	for t in tablecolumns:
		append_row(t, False)

	w.writerow(fieldrow)
	w.writerow(mandatoryrow)
	w.writerow(typerow)
	w.writerow(inforow)
	
	w.writerow([data_separator])

	if webnotes.form_dict.get('with_data')=='Yes':
		data = webnotes.conn.sql("""select * from `tab%s` where docstatus<2""" % doctype, as_dict=1)
		for d in data:
			row = [""]
			for c in columns:
				row.append(d.get(c, ""))
			w.writerow(row)

	# write out response as a type csv
	webnotes.response['result'] = cstr(w.getvalue())
	webnotes.response['type'] = 'csv'
	webnotes.response['doctype'] = doctype

def getdocfield(fieldname):
	"""get docfield from doclist of doctype"""
	l = [d for d in doctype_dl if d.doctype=='DocField' and d.fieldname==fieldname]
	return l and l[0] or None

@webnotes.whitelist(allow_roles=['System Manager', 'Administrator'])
def upload():
	"""upload data"""
	global doctype_dl
	import webnotes.model.doctype
	from webnotes.model.doc import Document
	from webnotes.utils.datautils import read_csv_content_from_uploaded_file
	
	rows = read_csv_content_from_uploaded_file()
	doctype = rows[0][0].split(':')[1].strip()
	
	# allow limit rows to be uploaded
	max_rows = 500
	if len(rows[8:]) > max_rows:
		webnotes.msgprint("Please upload only upto %d %ss at a time" % \
			(max_rows, doctype))
		raise Exception

	webnotes.conn.begin()
	
	overwrite = webnotes.form_dict.get('overwrite')
	doctype_dl = webnotes.model.doctype.get(doctype, form=0)
	columns = rows[3][1:]
	
	# parent details
	parenttype, parentfield = get_parent_details(rows)
	if parenttype and overwrite:
		delete_child_rows(rows, doctype)

	ret = []
	error = False
	start_row = 8
	for i, row in enumerate(rows[start_row:]):
		# bypass empty rows
		if not row: continue
		
		row_idx = (i + 1) + start_row
		
		d = dict(zip(columns, row[1:]))
		d['doctype'] = doctype
				
		try:
			check_record(d, parenttype)
			if parenttype:
				# child doc
				doc = Document(doctype)
				doc.fields.update(d)
				if parenttype:
					doc.parenttype = parenttype
					doc.parentfield = parentfield
				doc.save()
				ret.append('Inserted row for %s at #%s' % (getlink(parenttype,
					doc.parent), unicode(doc.idx)))
			else:
				ret.append(import_doc(d, doctype, overwrite, row_idx))
		except Exception, e:
			error = True
			ret.append('Error for row (#%d) %s : %s' % (row_idx, row[1], cstr(e)))
			webnotes.errprint(webnotes.getTraceback())
	
	if error:
		webnotes.conn.rollback()		
	else:
		webnotes.conn.commit()
	
	return {"messages": ret, "error": error}
	
def get_parent_details(rows):
	parenttype, parentfield = None, None
	
	# get parenttype
	if len(rows[1]) > 0 and ':' in rows[1][0]:
		parenttype = rows[1][0].split(':')[1].strip()
		
	# get parentfield
	if parenttype:
		import webnotes.model.doctype
		for d in webnotes.model.doctype.get(parenttype):
			if d.fieldtype=='Table' and d.options==doctype:
				parentfield = d.fieldname
				break
	
		if not parentfield:
			webnotes.msgprint("Did not find parentfield for %s (%s)" % \
				(parenttype, doctype))
			raise Exception
	
	return parenttype, parentfield
	
def check_record(d, parenttype):
	"""check for mandatory, select options, dates. these should ideally be in doclist"""
	
	from webnotes.utils.dateutils import parse_date
	
	if parenttype and not d.get('parent'):
		raise Exception, "parent is required."

	for key in d:
		docfield = getdocfield(key)
		val = d[key]
		if docfield:
			if docfield.reqd and (val=='' or val==None):
				raise Exception, "%s is mandatory." % key

			if docfield.fieldtype=='Select' and val:
				if docfield.options and docfield.options.startswith('link:'):
					link_doctype = docfield.options.split(':')[1]
					if not webnotes.conn.exists(link_doctype, val):
						raise Exception, "%s must be a valid %s" % (key, link_doctype)
				elif not docfield.options:
					raise Exception, "Select options are missing for %s"
				elif val not in docfield.options.split('\n'):
					raise Exception, "%s must be one of: %s" % (key, 
						", ".join(filter(None, docfield.options.split("\n"))))
					
			if val and docfield.fieldtype=='Date':
				d[key] = parse_date(val)

def getlink(doctype, name):
	return '<a href="#Form/%(doctype)s/%(name)s">%(name)s</a>' % locals()

def delete_child_rows(rows, doctype):
	"""delete child rows for all parents"""
	import webnotes
	for p in list(set([r[1] for r in rows[8:]])):
		webnotes.conn.sql("""delete from `tab%s` where parent=%s""" % (doctype, '%s'), p)
		
def import_doc(d, doctype, overwrite, row_idx):
	"""import main (non child) document"""
	import webnotes
	import webnotes.model.doc
	from webnotes.model.doclist import DocList

	if webnotes.conn.exists(doctype, d['name']):
		if overwrite:
			doclist = webnotes.model.doc.get(doctype, d['name'])
			doclist[0].fields.update(d)
			DocList(doclist).save()
			return 'Updated row (#%d) %s' % (row_idx, getlink(doctype, d['name']))
		else:
			return 'Ignored row (#%d) %s (exists)' % (row_idx, 
				getlink(doctype, d['name']))
	else:
		d['__islocal'] = 1
		dl = DocList([webnotes.model.doc.Document(fielddata = d)])
		dl.save()
		return 'Inserted row (#%d) %s' % (row_idx, getlink(doctype,
			dl.doc.fields['name']))

import csv, cStringIO
from webnotes.utils import encode
class UnicodeWriter:
	def __init__(self, encoding="utf-8"):
		self.encoding = encoding
		self.queue = cStringIO.StringIO()
		self.writer = csv.writer(self.queue)
	
	def writerow(self, row):
		row = encode(row, self.encoding)
		self.writer.writerow(row)
	
	def getvalue(self):
		return self.queue.getvalue()