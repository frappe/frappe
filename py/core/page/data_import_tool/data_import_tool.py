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
		webnotes.model.doctype.get(doctype)))

data_separator = '----Start entering data below this line----'

@webnotes.whitelist()
def get_template():
	import webnotes, csv
	from cStringIO import StringIO
	import webnotes.model.doctype

	doctype = webnotes.form_dict['doctype']
	parentdoctype = webnotes.form_dict.get('parent_doctype')
	
	doclist = webnotes.model.doctype.get(doctype)
	tablefields = [f[0] for f in webnotes.conn.sql('desc `tab%s`' % doctype)]

	def getdocfield(fieldname):
		l = [d for d in doclist if d.doctype=='DocField' and d.fieldname==fieldname]
		return l and l[0] or None

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
	
	if parentdoctype != doctype:
		w.writerow(['This is a child table for %s' % parentdoctype])
		key = 'parent'
	else:
		w.writerow([''])
	
	w.writerow(['----'])
	
	fieldrow = ['Column Name:', key]
	mandatoryrow = ['Mandatory:', 'Yes']
	typerow = ['Type:', 'Data (text)']
	inforow = ['Info:', 'ID']
			
	# get all mandatory fields
	for t in tablefields:
		docfield = getdocfield(t)
		if docfield and docfield.reqd:
			fieldrow.append(t)
			mandatoryrow.append('Yes')
			typerow.append(docfield.fieldtype)			
			inforow.append(getinforow(docfield))

	# all non mandatory fields
	for t in tablefields:
		docfield = getdocfield(t)
		if docfield and not docfield.reqd:
			fieldrow.append(t)
			mandatoryrow.append('No')
			typerow.append(docfield.fieldtype)			
			inforow.append(getinforow(docfield))
			
	w.writerow(fieldrow)
	w.writerow(mandatoryrow)
	w.writerow(typerow)
	w.writerow(inforow)
	
	w.writerow([data_separator])

	# write out response as a type csv
	webnotes.response['result'] = tobj.getvalue()
	webnotes.response['type'] = 'csv'
	webnotes.response['doctype'] = doctype
	
@webnotes.whitelist()
def upload():
	"""upload data"""
	import csv
	from webnotes.utils.file_manager import get_uploaded_content
	from webnotes.model.doc import Document
	from webnotes.model.doclist import DocList

	fname, fcontent = get_uploaded_content()

	ret, rows = [], []
	for row in csv.reader(fcontent.splitlines()):
		rows.append([c.strip() for c in row])
	
	# doctype
	doctype = rows[0][0].split(':')[1].strip()
	
	# columns
	columns = rows[3][1:]
		
	for row in rows[8:]:
		d = dict(zip(columns, row[1:]))
		d['doctype'] = doctype
		
		try:
			if not webnotes.conn.exists(doctype, d['name']):
				d['__islocal'] = 1
				
			DocList([Document(fielddata = d)]).save()
			ret.append('Uploaded ' + row[1])
		except Exception, e:
			ret.append('Error for ' + row[1] + ': ' + str(e))
		
	return ret
			
