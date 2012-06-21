import webnotes

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
	import webnotes, csv
	from cStringIO import StringIO
	import webnotes.model.doctype
	global doctype_dl

	doctype = webnotes.form_dict['doctype']
	parenttype = webnotes.form_dict.get('parent_doctype')
	
	doctype_dl = webnotes.model.doctype.get(doctype)
	tablecolumns = [f[0] for f in webnotes.conn.sql('desc `tab%s`' % doctype)]
	
	def getinforow(docfield):
		"""make info comment"""
		if docfield.fieldtype == 'Select':
			if docfield.options.startswith('link:'):
				return 'Valid %s' % docfield.options[5:]
			else:
				return 'One of: %s' % ', '.join(filter(None, docfield.options.split('\n')))
		if docfield.fieldtype == 'Link':
			return 'Valid %s' % docfield.options
		if docfield.fieldtype in ('Int'):
			return 'Integer'
		else:
			return ''
			
	tobj = StringIO()
	w = csv.writer(tobj)
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
			row = ['']
			for c in columns:
				val = d.get(c, '')
				if type(val) is unicode:
					val = val.encode('utf-8')
				row.append(val)
			w.writerow(row)

	# write out response as a type csv
	webnotes.response['result'] = tobj.getvalue()
	webnotes.response['type'] = 'csv'
	webnotes.response['doctype'] = doctype

def getdocfield(fieldname):
	"""get docfield from doclist of doctype"""
	l = [d for d in doctype_dl if d.doctype=='DocField' and d.fieldname==fieldname]
	return l and l[0] or None

@webnotes.whitelist(allow_roles=['System Manager', 'Administrator'])
def upload():
	"""upload data"""
	import csv
	global doctype_dl
	from webnotes.utils.file_manager import get_uploaded_content
	import webnotes.model.doctype
	from webnotes.model.doc import Document
	
	fname, fcontent = get_uploaded_content()
	overwrite = webnotes.form_dict.get('overwrite')

	ret, rows = [], []
	try:
		reader = csv.reader(fcontent.splitlines())
		# decode everything
		csvrows = [[val for val in row] for row in reader]
		
		for row in csvrows:
			newrow = []
			for val in row:
				if webnotes.form_dict.get('ignore_encoding_errors'):
					newrow.append(unicode(val.strip(), 'utf-8', errors='ignore'))
				else:
					try:
						newrow.append(unicode(val.strip(), 'utf-8'))
					except UnicodeDecodeError, e:
						raise Exception, """Some character(s) in row #%s, column #%s are
							not readable by utf-8. Ignoring them. If you are importing a non
							english language, please make sure your file is saved in the 'utf-8'
							encoding.""" % (csvrows.index(row)+1, row.index(val)+1)
					
			rows.append(newrow)
			
	except Exception, e:
		webnotes.msgprint("Not a valid Comma Separated Value (CSV File)")
		raise e

	
	# doctype
	doctype = rows[0][0].split(':')[1].strip()
	doctype_dl = webnotes.model.doctype.get(doctype, form=0)
	
	if doctype in ['Customer', 'Supplier'] and len(rows[8:]) > 100:
		webnotes.msgprint("Please upload only upto 100 %ss at a time" % doctype)
		raise Exception
	
	parenttype, parentfield = None, None
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
			webnotes.msgprint("Did not find parentfield for %s (%s)" % (parenttype, doctype),
				raise_exception=1)
			
	# columns
	columns = rows[3][1:]
	
	if parenttype and overwrite:
		delete_child_rows(rows, doctype)
		
	for row in rows[8:]:
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
				ret.append('Inserted row for %s at #%s' % (getlink(parenttype, doc.parent), 
					str(doc.idx)))
			else:
				ret.append(import_doc(d, doctype, overwrite))
		except Exception, e:
			ret.append('Error for ' + row[1] + ': ' + str(e))
			webnotes.errprint(webnotes.getTraceback())
	return ret

def check_record(d, parenttype):
	"""check for mandatory, select options, dates. these should ideally be in doclist"""
	if parenttype and not d.get('parent'):
		raise Exception, "parent is required."

	for key in d:
		docfield = getdocfield(key)
		val = d[key]
		if docfield:
			if docfield.reqd and (val=='' or val==None):
				raise Exception, "%s is mandatory." % key

			if docfield.fieldtype=='Select':
				if docfield.options.startswith('link:'):
					if val:
						link_doctype = docfield.options.split(':')[1]
						if not webnotes.conn.exists(link_doctype, val):
							raise Exception, "%s must be a valid %s" % (key, link_doctype)
				else:
					if val and (val not in docfield.options.split('\n')):
						raise Exception, "%s must be one of:" % key
						
			if docfield.fieldtype=='Date' and val:
				import datetime
				dateformats = {
					'yyyy-mm-dd':'%Y-%m-%d',
					'dd/mm/yyyy':'%d/%m/%Y',
					'mm/dd/yyyy':'%m/%d/%Y'
				}
				d[key] = datetime.datetime.strptime(val, 
					dateformats[webnotes.form_dict['date_format']]).strftime('%Y-%m-%d')

def getlink(doctype, name):
	return '<a href="#Form/%(doctype)s/%(name)s">%(name)s</a>' % locals()

def delete_child_rows(rows, doctype):
	"""delete child rows for all parents"""
	import webnotes
	for p in list(set([r[1] for r in rows[8:]])):
		webnotes.conn.sql("""delete from `tab%s` where parent=%s""" % (doctype, '%s'), p)

def import_doc(d, doctype, overwrite):
	"""import main (non child) document"""
	import webnotes
	from webnotes.model.doc import Document
	from webnotes.model.doclist import DocList

	if webnotes.conn.exists(doctype, d['name']):
		if overwrite:
			doc = Document(doctype, d['name'])
			doc.fields.update(d)
			DocList([doc]).save()
			return 'Updated ' + getlink(doctype, d['name'])
		else:
			return 'Ignored ' + getlink(doctype, d['name']) + ' (exists)'
	else:
		d['__islocal'] = 1
		DocList([Document(fielddata = d)]).save()
		return 'Inserted ' + getlink(doctype, d['name'])