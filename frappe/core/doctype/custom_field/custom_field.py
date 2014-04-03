# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, cstr
from frappe import _

from frappe.model.document import Document

class CustomField(Document):
		
	def autoname(self):
		self.set_fieldname()
		self.name = self.dt + "-" + self.fieldname

	def set_fieldname(self):
		if not self.fieldname:
			if not self.label:
				frappe.throw(_("Label is mandatory"))
			# remove special characters from fieldname
			self.fieldname = filter(lambda x: x.isdigit() or x.isalpha() or '_', 
				cstr(self.label).lower().replace(' ','_'))

	def validate(self):
		if not self.idx:
			self.idx = len(frappe.get_meta(self.dt).get("fields")) + 1
		
		if not self.fieldname:
			frappe.throw(_("Fieldname not set for Custom Field"))
		
	def on_update(self):
		# validate field
		from frappe.core.doctype.doctype.doctype import validate_fields_for_doctype

		validate_fields_for_doctype(self.dt)

		frappe.clear_cache(doctype=self.dt)
				
		# create property setter to emulate insert after
		self.create_property_setter()

		# update the schema
		if not frappe.flags.in_test:
			from frappe.model.db_schema import updatedb
			updatedb(self.dt)
			
	def on_trash(self):
		# delete property setter entries
		frappe.db.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND field_name = %s""",
				(self.dt, self.fieldname))

		frappe.clear_cache(doctype=self.dt)

	def create_property_setter(self):
		if not self.insert_after: return
		idx_label_list, field_list = get_fields_label(self.dt, 0)
		label_index = idx_label_list.index(self.insert_after)
		if label_index==-1: return

		prev_field = field_list[label_index]
		frappe.db.sql("""\
			DELETE FROM `tabProperty Setter`
			WHERE doc_type = %s
			AND field_name = %s
			AND property = 'previous_field'""", (self.dt, self.fieldname))
		
		frappe.make_property_setter({
			"doctype":self.dt, 
			"fieldname": self.fieldname, 
			"property": "previous_field",
			"value": prev_field
		})
		
@frappe.whitelist()
def get_fields_label(dt=None, form=1):
	"""
		if form=1: Returns a string of field labels separated by \n
		if form=0: Returns lists of field labels and field names
	"""
	import frappe
	from frappe.utils import cstr
	fieldname = None
	if not dt:
		dt = frappe.form_dict.get('doctype')
		fieldname = frappe.form_dict.get('fieldname')
	if not dt: return ""
	
	docfields = frappe.get_meta(dt).get("fields")
	
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
	df = frappe._dict(df)
	if df.fieldname in frappe.db.get_table_columns(doctype) and \
		frappe.db.sql("""select count(*) from `tab{doctype}` 
			where ifnull({fieldname},'')!=''""".format(doctype=doctype, fieldname=df.fieldname))[0][0] and \
		not frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": df.fieldname}):
			frappe.get_doc({
				"doctype":"Custom Field",
				"dt": doctype,
				"permlevel": df.permlevel or 0,
				"label": df.label,
				"fieldname": df.fieldname,
				"fieldtype": df.fieldtype,
				"options": df.options,
				"insert_after": df.insert_after
			}).insert()
		
