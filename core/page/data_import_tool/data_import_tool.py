from __future__ import unicode_literals

import webnotes
import webnotes.model.doc
import webnotes.model.doctype
from webnotes.model.doc import Document
from webnotes.utils import cstr
from webnotes.utils.datautils import UnicodeWriter, check_record, import_doc, getlink
from webnotes import _

data_keys = webnotes._dict({
	"data_separator": 'Start entering data below this line',
	"main_table": "Table:",
	"parent_table": "Parent Table:",
	"columns": "Column Name:"
})

@webnotes.whitelist()
def get_doctypes():
    return [r[0] for r in webnotes.conn.sql("""select name from `tabDocType` 
		where document_type = 'Master' or allow_import = 1""")]
		
@webnotes.whitelist()
def get_doctype_options():
	doctype = webnotes.form_dict['doctype']
	return [doctype] + filter(None, map(lambda d: \
		d.doctype=='DocField' and d.fieldtype=='Table' and d.options or None, 
		webnotes.model.doctype.get(doctype)))

@webnotes.whitelist(allow_roles=['System Manager', 'Administrator'])
def get_template():
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
		if docfield.fieldtype == "Check":
			return "0 or 1"
		else:
			return ''
			
	w = UnicodeWriter()
	key = 'name'

	w.writerow(['Data Import Template'])	
	w.writerow([data_keys.main_table, doctype])
	
	if parenttype != doctype:
		w.writerow([data_keys.parent_table, parenttype])
		key = 'parent'
	else:
		w.writerow([''])
	
	w.writerow([''])
	w.writerow(['Notes:'])
	w.writerow(['Please do not change the template headings.'])
	w.writerow(['First data column must be blank.'])
	w.writerow(['Only mandatory fields are necessary for new records. You can delete non-mandatory columns if you wish.'])
	w.writerow(['For updating, you can update only selective columns.'])
	w.writerow(['If you are uploading new records, leave the "name" (ID) column blank.'])
	w.writerow(['If you are uploading new records, "Naming Series" becomes mandatory, if present.'])
	w.writerow(['You can only upload upto 5000 records in one go. (may be less in some cases)'])
	if key == "parent":
		w.writerow(['"Parent" signifies the parent table in which this row must be added'])
		w.writerow(['If you are updating, please select "Overwrite" else existing rows will not be deleted.'])
	w.writerow([''])
	labelrow = ["Column Labels", "ID"]
	fieldrow = [data_keys.columns, key]
	mandatoryrow = ['Mandatory:', 'Yes']
	typerow = ['Type:', 'Data (text)']
	inforow = ['Info:', '']
	columns = [key]
	
	def append_row(t, mandatory):
		docfield = doctype_dl.get_field(t)
		
		if docfield and ((mandatory and docfield.reqd) or not (mandatory or docfield.reqd)) \
			and (t not in ('parenttype', 'trash_reason')) and not docfield.hidden:
			fieldrow.append(t)
			labelrow.append(docfield.label)
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

	w.writerow(labelrow)
	w.writerow(fieldrow)
	w.writerow(mandatoryrow)
	w.writerow(typerow)
	w.writerow(inforow)
	
	w.writerow([data_keys.data_separator])

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

@webnotes.whitelist(allow_roles=['System Manager', 'Administrator'])
def upload():
	"""upload data"""
	webnotes.mute_emails = True
	
	from webnotes.utils.datautils import read_csv_content_from_uploaded_file
	
	def bad_template():
		webnotes.msgprint("Please do not change the rows above '%s'" % data_keys.data_separator,
			raise_exception=1)
			
	def check_data_length():
		max_rows = 5000
		if not data:
			webnotes.msgprint("No data found", raise_exception=True)
		elif len(data) > max_rows:
			webnotes.msgprint("Please upload only upto %d %ss at a time" % \
				(max_rows, doctype), raise_exception=True)
	
	def get_start_row():
		for i, row in enumerate(rows):
			if row and row[0]==data_keys.data_separator:
				return i+1
		bad_template()
				
	def get_header_row(key):
		for i, row in enumerate(header):
			if row and row[0]==key:
				return row
		return []
		
	def filter_empty_columns(columns):
		empty_cols = filter(lambda x: x in ("", None), columns)
		
		if empty_cols:
			if columns[-1*len(empty_cols):] == empty_cols:
				# filter empty columns if they exist at the end
				columns = columns[:-1*len(empty_cols)]
			else:
				webnotes.msgprint(_("Please make sure that there are no empty columns in the file."),
					raise_exception=1)
		
		return columns
		
	# extra input params
	import json
	params = json.loads(webnotes.form_dict.get("params") or '{}')
	
	# header
	rows = read_csv_content_from_uploaded_file(params.get("ignore_encoding_errors"))
	start_row = get_start_row()
	header = rows[:start_row]
	data = rows[start_row:]
	doctype = get_header_row(data_keys.main_table)[1]
	columns = filter_empty_columns(get_header_row(data_keys.columns)[1:])

	parenttype = get_header_row(data_keys.parent_table)
	
	if len(parenttype) > 1:
		parenttype = parenttype[1]
		parentfield = get_parent_field(doctype, parenttype)
		
	# allow limit rows to be uploaded
	check_data_length()
	
	webnotes.conn.begin()
	
	overwrite = params.get('overwrite')
	doctype_dl = webnotes.model.doctype.get(doctype)
	
	# delete child rows (if parenttype)
	if parenttype and overwrite:
		delete_child_rows(data, doctype)

	ret = []
	error = False
	parent_list = []
	for i, row in enumerate(data):
		# bypass empty rows
		if not row: continue
		
		row_idx = (i + 1) + start_row
		
		d = webnotes._dict(zip(columns, row[1:]))
		d['doctype'] = doctype
		
		try:
			check_record(d, parenttype, doctype_dl)
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
				parent_list.append(doc.parent)
			else:
				ret.append(import_doc(d, doctype, overwrite, row_idx, params.get("_submit")))
		except Exception, e:
			error = True
			err_msg = webnotes.message_log and "<br>".join(webnotes.message_log) or cstr(e)
			ret.append('Error for row (#%d) %s : %s' % (row_idx, 
				len(row)>1 and row[1] or "", err_msg))
			webnotes.errprint(webnotes.getTraceback())
			webnotes.message_log = []
	
	ret, error = validate_parent(parent_list, parenttype, ret, error)
	
	if error:
		webnotes.conn.rollback()		
	else:
		webnotes.conn.commit()
		
	webnotes.mute_emails = False
	
	return {"messages": ret, "error": error}
	
def validate_parent(parent_list, parenttype, ret, error):
	if parent_list:
		parent_list = list(set(parent_list))
		for p in parent_list:
			try:
				obj = webnotes.bean(parenttype, p)
				obj.run_method("validate")
				obj.run_method("on_update")
			except Exception, e:
				error = True
				ret.append('Validation Error for %s %s: %s' % (parenttype, p, cstr(e)))
				webnotes.errprint(webnotes.getTraceback())
				
	return ret, error
	
def get_parent_field(doctype, parenttype):
	parentfield = None
			
	# get parentfield
	if parenttype:
		for d in webnotes.model.doctype.get(parenttype):
			if d.fieldtype=='Table' and d.options==doctype:
				parentfield = d.fieldname
				break
	
		if not parentfield:
			webnotes.msgprint("Did not find parentfield for %s (%s)" % \
				(parenttype, doctype))
			raise Exception
	
	return parentfield

def delete_child_rows(rows, doctype):
	"""delete child rows for all parents"""
	for p in list(set([r[1] for r in rows])):
		webnotes.conn.sql("""delete from `tab%s` where parent=%s""" % (doctype, '%s'), p)
