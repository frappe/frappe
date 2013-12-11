# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes

from webnotes.utils import cint, cstr

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		self.set_fieldname()
		self.doc.name = self.doc.dt + "-" + self.doc.fieldname

	def set_fieldname(self):
		if not self.doc.fieldname:
			# remove special characters from fieldname
			self.doc.fieldname = filter(lambda x: x.isdigit() or x.isalpha() or '_', cstr(self.doc.label).lower().replace(' ','_'))

	def validate(self):
		from webnotes.model.doctype import get
		temp_doclist = get(self.doc.dt).get_parent_doclist()
				
		# set idx
		if not self.doc.idx:
			max_idx = max(d.idx for d in temp_doclist if d.doctype=='DocField')
			self.doc.idx = cint(max_idx) + 1
		
	def on_update(self):
		# validate field
		from webnotes.core.doctype.doctype.doctype import validate_fields_for_doctype

		validate_fields_for_doctype(self.doc.dt)

		webnotes.clear_cache(doctype=self.doc.dt)
				
		# create property setter to emulate insert after
		self.create_property_setter()

		# update the schema
		from webnotes.model.db_schema import updatedb
		updatedb(self.doc.dt)

	def on_trash(self):
		# delete property setter entries
		webnotes.conn.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND field_name = %s""",
				(self.doc.dt, self.doc.fieldname))

		webnotes.clear_cache(doctype=self.doc.dt)

	def create_property_setter(self):
		if not self.doc.insert_after: return
		idx_label_list, field_list = get_fields_label(self.doc.dt, 0)
		label_index = idx_label_list.index(self.doc.insert_after)
		if label_index==-1: return

		prev_field = field_list[label_index]
		webnotes.conn.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND field_name = %s
			AND property = 'previous_field'""", (self.doc.dt, self.doc.fieldname))
		
		webnotes.make_property_setter({
			"doctype":self.doc.dt, 
			"fieldname": self.doc.fieldname, 
			"property": "previous_field",
			"value": prev_field
		})
		
@webnotes.whitelist()
def get_fields_label(dt=None, form=1):
	"""
		if form=1: Returns a string of field labels separated by \n
		if form=0: Returns lists of field labels and field names
	"""
	import webnotes
	from webnotes.utils import cstr
	import webnotes.model.doctype
	fieldname = None
	if not dt:
		dt = webnotes.form_dict.get('doctype')
		fieldname = webnotes.form_dict.get('fieldname')
	if not dt: return ""
	
	doclist = webnotes.model.doctype.get(dt)
	docfields = sorted(doclist.get({"parent": dt, "doctype": "DocField"}),
		key=lambda d: d.idx)
	
	if fieldname:
		idx_label_list = [cstr(d.label) or cstr(d.fieldname) or cstr(d.fieldtype)
			for d in docfields if d.fieldname != fieldname]
	else:
		idx_label_list = [cstr(d.label) or cstr(d.fieldname) or cstr(d.fieldtype)
			for d in docfields]
	if form:
		return "\n".join(idx_label_list)
	else:
		# return idx_label_list, field_list
		field_list = [cstr(d.fieldname) for d in docfields]
		return idx_label_list, field_list

def create_custom_field_if_values_exist(doctype, df):
	df = webnotes._dict(df)
	if df.fieldname in webnotes.conn.get_table_columns(doctype) and \
		webnotes.conn.sql("""select count(*) from `tab{doctype}` 
			where ifnull({fieldname},'')!=''""".format(doctype=doctype, fieldname=df.fieldname))[0][0] and \
		not webnotes.conn.get_value("Custom Field", {"dt": doctype, "fieldname": df.fieldname}):
			webnotes.bean({
				"doctype":"Custom Field",
				"dt": doctype,
				"permlevel": df.permlevel or 0,
				"label": df.label,
				"fieldname": df.fieldname,
				"fieldtype": df.fieldtype,
				"options": df.options,
				"insert_after": df.insert_after
			}).insert()
		
