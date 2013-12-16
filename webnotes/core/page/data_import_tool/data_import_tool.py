# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import webnotes, json
import webnotes.model.doc
import webnotes.model.doctype
from webnotes.model.meta import get_table_fields
from webnotes.model.doc import Document
from webnotes.utils import cstr
from webnotes.utils.datautils import UnicodeWriter, check_record, import_doc, getlink, cint, flt
from webnotes import _

data_keys = webnotes._dict({
	"data_separator": 'Start entering data below this line',
	"main_table": "Table:",
	"parent_table": "Parent Table:",
	"columns": "Column Name:",
	"doctype": "DocType:"
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

@webnotes.whitelist()
def get_template(doctype=None, parent_doctype=None, all_doctypes="No", with_data="No"):
	webnotes.check_admin_or_system_manager()
	all_doctypes = all_doctypes=="Yes"
	if not parent_doctype:
		parent_doctype = doctype
	
	column_start_end = {}
	
	if all_doctypes:
		doctype_parentfield = {}
		child_doctypes = []
		for d in get_table_fields(doctype):
			child_doctypes.append(d[0])
			doctype_parentfield[d[0]] = d[1]
		
	def add_main_header():
		w.writerow(['Data Import Template'])
		w.writerow([data_keys.main_table, doctype])
		
		if parent_doctype != doctype:
			w.writerow([data_keys.parent_table, parent_doctype])
		else:
			w.writerow([''])

		w.writerow([''])
		w.writerow(['Notes:'])
		w.writerow(['Please do not change the template headings.'])
		w.writerow(['First data column must be blank.'])
		w.writerow(['If you are uploading new records, leave the "name" (ID) column blank.'])
		w.writerow(['If you are uploading new records, "Naming Series" becomes mandatory, if present.'])
		w.writerow(['Only mandatory fields are necessary for new records. You can delete non-mandatory columns if you wish.'])
		w.writerow(['For updating, you can update only selective columns.'])
		w.writerow(['You can only upload upto 5000 records in one go. (may be less in some cases)'])
		if key == "parent":
			w.writerow(['"Parent" signifies the parent table in which this row must be added'])
			w.writerow(['If you are updating, please select "Overwrite" else existing rows will not be deleted.'])

	def build_field_columns(dt):
		doctype_dl = webnotes.model.doctype.get(dt)

		tablecolumns = filter(None, 
			[doctype_dl.get_field(f[0]) for f in webnotes.conn.sql('desc `tab%s`' % dt)])

		tablecolumns.sort(lambda a, b: a.idx - b.idx)

		if dt==doctype:
			column_start_end[dt] = webnotes._dict({"start": 0})
		else:
			column_start_end[dt] = webnotes._dict({"start": len(columns)})
			
			append_field_column(webnotes._dict({
				"fieldname": "name",
				"label": "ID",
				"fieldtype": "Data",
				"reqd": 1,
				"idx": 0,
				"info": "Leave blank for new records"
			}), True)
			
		for docfield in tablecolumns:
			append_field_column(docfield, True)

		# all non mandatory fields
		for docfield in tablecolumns:
			append_field_column(docfield, False)

		# append DocType name
		tablerow[column_start_end[dt].start + 1] = dt
		if dt!=doctype:
			tablerow[column_start_end[dt].start + 2] = doctype_parentfield[dt]

		column_start_end[dt].end = len(columns) + 1
			
	def append_field_column(docfield, mandatory):
		if docfield and ((mandatory and docfield.reqd) or not (mandatory or docfield.reqd)) \
			and (docfield.fieldname not in ('parenttype', 'trash_reason')) and not docfield.hidden:
			tablerow.append("")
			fieldrow.append(docfield.fieldname)
			labelrow.append(docfield.label)
			mandatoryrow.append(docfield.reqd and 'Yes' or 'No')
			typerow.append(docfield.fieldtype)
			inforow.append(getinforow(docfield))
			columns.append(docfield.fieldname)
			
	def append_empty_field_column():
		tablerow.append("~")
		fieldrow.append("~")
		labelrow.append("")
		mandatoryrow.append("")
		typerow.append("")
		inforow.append("")
		columns.append("")

	def getinforow(docfield):
		"""make info comment for options, links etc."""
		if docfield.fieldtype == 'Select':
			if not docfield.options:
				return ''
			elif docfield.options.startswith('link:'):
				return 'Valid %s' % docfield.options[5:]
			else:
				return 'One of: %s' % ', '.join(filter(None, docfield.options.split('\n')))
		elif docfield.fieldtype == 'Link':
			return 'Valid %s' % docfield.options
		elif docfield.fieldtype in ('Int'):
			return 'Integer'
		elif docfield.fieldtype == "Check":
			return "0 or 1"
		elif docfield.info:
			return docfield.info
		else:
			return ''

	def add_field_headings():
		w.writerow(tablerow)
		w.writerow(labelrow)
		w.writerow(fieldrow)
		w.writerow(mandatoryrow)
		w.writerow(typerow)
		w.writerow(inforow)
		w.writerow([data_keys.data_separator])

	def add_data():
		def add_data_row(row_group, dt, doc, rowidx):
			d = doc.copy()
			if all_doctypes:
				d.name = '"'+ d.name+'"'

			if len(row_group) < rowidx + 1:
				row_group.append([""] * (len(columns) + 1))
			row = row_group[rowidx]
			for i, c in enumerate(columns[column_start_end[dt].start:column_start_end[dt].end]):
				row[column_start_end[dt].start + i + 1] = d.get(c, "")

		if with_data=='Yes':			
			data = webnotes.conn.sql("""select * from `tab%s` where docstatus<2""" \
				% doctype, as_dict=1)
			for doc in data:
				# add main table
				row_group = []
					
				add_data_row(row_group, doctype, doc, 0)
				
				if all_doctypes:
					# add child tables
					for child_doctype in child_doctypes:
						for ci, child in enumerate(webnotes.conn.sql("""select * from `tab%s` 
							where parent=%s order by idx""" % (child_doctype, "%s"), doc.name, as_dict=1)):
							add_data_row(row_group, child_doctype, child, ci)
					
				for row in row_group:
					w.writerow(row)
	
	w = UnicodeWriter()
	key = 'parent' if parent_doctype != doctype else 'name'
	
	add_main_header()

	w.writerow([''])
	tablerow = [data_keys.doctype, ""]
	labelrow = ["Column Labels:", "ID"]
	fieldrow = [data_keys.columns, key]
	mandatoryrow = ['Mandatory:', 'Yes']
	typerow = ['Type:', 'Data (text)']
	inforow = ['Info:', '']
	columns = [key]

	build_field_columns(doctype)
	if all_doctypes:
		for d in child_doctypes:
			append_empty_field_column()
			build_field_columns(d)
	
	add_field_headings()
	add_data()
	
	# write out response as a type csv
	webnotes.response['result'] = cstr(w.getvalue())
	webnotes.response['type'] = 'csv'
	webnotes.response['doctype'] = doctype

@webnotes.whitelist()
def upload(rows = None, submit_after_import=None, ignore_encoding_errors=False, overwrite=False, ignore_links=False):
	"""upload data"""
	webnotes.flags.mute_emails = True
	webnotes.check_admin_or_system_manager()
	# extra input params
	params = json.loads(webnotes.form_dict.get("params") or '{}')
	
	if params.get("_submit"):
		submit_after_import = True
	if params.get("ignore_encoding_errors"):
		ignore_encoding_errors = True

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
		return get_header_row_and_idx(key)[0]

	def get_header_row_and_idx(key):
		for i, row in enumerate(header):
			if row and row[0]==key:
				return row, i
		return [], -1

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

	def make_column_map():
		doctype_row, row_idx = get_header_row_and_idx(data_keys.doctype)
		if row_idx == -1: # old style
			return
			
		dt = None
		for i, d in enumerate(doctype_row[1:]):
			if d not in ("~", "-"):
				if d: # value in doctype_row
					if doctype_row[i]==dt:
						# prev column is doctype (in case of parentfield)
						doctype_parentfield[dt] = doctype_row[i+1]
					else:
						dt = d
						doctypes.append(d)
						column_idx_to_fieldname[dt] = {}
						column_idx_to_fieldtype[dt] = {}
				if dt:
					column_idx_to_fieldname[dt][i+1] = rows[row_idx + 2][i+1]
					column_idx_to_fieldtype[dt][i+1] = rows[row_idx + 4][i+1]

	def get_doclist(start_idx):
		if doctypes:
			doclist = []
			for idx in xrange(start_idx, len(rows)):
				if (not len(doclist)) or main_doc_empty(rows[idx]):
					for dt in doctypes:
						d = {}
						for column_idx in column_idx_to_fieldname[dt]:
							try:
								fieldname = column_idx_to_fieldname[dt][column_idx]
								fieldtype = column_idx_to_fieldtype[dt][column_idx]
								
								d[fieldname] = rows[idx][column_idx]
								if fieldtype in ("Int", "Check"):
									d[fieldname] = cint(d[fieldname])
								elif fieldtype in ("Float", "Currency"):
									d[fieldname] = flt(d[fieldname])
							except IndexError, e:
								pass
								
						# scrub quotes from name and modified
						if d.get("name") and d["name"].startswith('"'):
							d["name"] = d["name"][1:-1]

						if sum([0 if not val else 1 for val in d.values()]):
							d['doctype'] = dt
							if dt != doctype:
								if not overwrite:
									d['parent'] = doclist[0]["name"]
								d['parenttype'] = doctype
								d['parentfield'] = doctype_parentfield[dt]
							doclist.append(d)
				else:
					break
				
			return doclist
		else:
			d = webnotes._dict(zip(columns, rows[start_idx][1:]))
			d['doctype'] = doctype
			return [d]

	def main_doc_empty(row):
		return not (row and ((len(row) > 1 and row[1]) or (len(row) > 2 and row[2])))
		
	# header
	if not rows:
		rows = read_csv_content_from_uploaded_file(ignore_encoding_errors)
	start_row = get_start_row()
	header = rows[:start_row]
	data = rows[start_row:]
	doctype = get_header_row(data_keys.main_table)[1]
	columns = filter_empty_columns(get_header_row(data_keys.columns)[1:])
	doctypes = []
	doctype_parentfield = {}
	column_idx_to_fieldname = {}
	column_idx_to_fieldtype = {}
	
	if submit_after_import and not cint(webnotes.conn.get_value("DocType", 
			doctype, "is_submittable")):
		submit_after_import = False
		

	parenttype = get_header_row(data_keys.parent_table)
	
	if len(parenttype) > 1:
		parenttype = parenttype[1]
		parentfield = get_parent_field(doctype, parenttype)
		
	# allow limit rows to be uploaded
	check_data_length()
	make_column_map()
	
	webnotes.conn.begin()
	if not overwrite:
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
		if main_doc_empty(row):
			continue
		
		row_idx = i + start_row
		bean = None
		
		doclist = get_doclist(row_idx)
		try:
			webnotes.local.message_log = []
			if len(doclist) > 1:
				for d in doclist:
					# ignoring parent check as it will be automatically added
					check_record(d, None, doctype_dl)
				
				if overwrite and webnotes.conn.exists(doctype, doclist[0]["name"]):
					bean = webnotes.bean(doctype, doclist[0]["name"])
					bean.ignore_links = ignore_links
					bean.doclist.update(doclist)
					bean.save()
					ret.append('Updated row (#%d) %s' % (row_idx + 1, getlink(bean.doc.doctype, bean.doc.name)))
				else:
					bean = webnotes.bean(doclist)
					bean.ignore_links = ignore_links
					bean.insert()
					ret.append('Inserted row (#%d) %s' % (row_idx + 1, getlink(bean.doc.doctype, bean.doc.name)))
				if submit_after_import:
					bean.submit()
					ret.append('Submitted row (#%d) %s' % (row_idx + 1, getlink(bean.doc.doctype, bean.doc.name)))
			else:
				check_record(doclist[0], parenttype, doctype_dl)

				if parenttype:
					# child doc
					doc = Document(doctype)
					doc.fields.update(doclist[0])
					if parenttype:
						doc.parenttype = parenttype
						doc.parentfield = parentfield
					doc.save()
					ret.append('Inserted row for %s at #%s' % (getlink(parenttype,
						doc.parent), unicode(doc.idx)))
					parent_list.append(doc.parent)
				else:
					ret.append(import_doc(doclist[0], doctype, overwrite, row_idx, submit_after_import, ignore_links))

		except Exception, e:
			error = True
			if bean:
				webnotes.errprint(bean.doclist)
			err_msg = webnotes.local.message_log and "<br>".join(webnotes.local.message_log) or cstr(e)
			ret.append('Error for row (#%d) %s : %s' % (row_idx + 1, 
				len(row)>1 and row[1] or "", err_msg))
			webnotes.errprint(webnotes.get_traceback())
	
	ret, error = validate_parent(parent_list, parenttype, ret, error)
	
	if error:
		webnotes.conn.rollback()		
	else:
		webnotes.conn.commit()
		
	webnotes.flags.mute_emails = False
	
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
				webnotes.errprint(webnotes.get_traceback())
				
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
		
def import_file_by_path(path, ignore_links=False, overwrite=False):
	from webnotes.utils.datautils import read_csv_content
	print "Importing " + path
	with open(path, "r") as infile:
		upload(rows = read_csv_content(infile.read()), ignore_links=ignore_links, overwrite=overwrite)

def export_csv(doctype, path):		
	with open(path, "w") as csvfile:
		get_template(doctype=doctype, all_doctypes="Yes", with_data="Yes")
		csvfile.write(webnotes.response.result.encode("utf-8"))

def export_json(doctype, name, path):
	from webnotes.handler import json_handler
	if not name or name=="-":
		name = doctype
	with open(path, "w") as outfile:
		doclist = [d.fields for d in webnotes.bean(doctype, name).doclist]
		for d in doclist:
			if d.get("parent"):
				del d["parent"]
				del d["name"]
			d["__islocal"] = 1
		outfile.write(json.dumps(doclist, default=json_handler, indent=1, sort_keys=True))

def import_doclist(path, overwrite=False):
	import os
	if os.path.isdir(path):
		files = [os.path.join(path, f) for f in os.listdir(path)]
	else:
		files = [path]
			
	for f in files:
		if f.endswith(".json"):
			with open(f, "r") as infile:
				b = webnotes.bean(json.loads(infile.read())).insert_or_update()
				print "Imported: " + b.doc.doctype + " / " + b.doc.name
				webnotes.conn.commit()
		if f.endswith(".csv"):
			import_file_by_path(f, ignore_links=True, overwrite=overwrite)
			webnotes.conn.commit()