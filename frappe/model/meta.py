# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

# metadata

from __future__ import unicode_literals
import frappe
from frappe.utils import cstr, cint
from frappe.model import integer_docfield_properties
from frappe.model.document import Document

######

def get_meta(doctype, cached=True):
	# TODO: cache to be cleared

	if cached:
		if doctype not in frappe.local.meta:
			frappe.local.meta[doctype] = frappe.cache().get_value("meta:" + doctype, lambda: Meta(doctype))
		return frappe.local.meta.get(doctype)
	else:
		return Meta(doctype)

class Meta(Document):
	_metaclass = True
	def __init__(self, doctype):
		super(Meta, self).__init__("DocType", doctype)
		
	def get_link_fields(self):
		tmp = self.get("fields", {"fieldtype":"Link"})
		tmp.extend(self.get("fields", {"fieldtype":"Select", "options": "^link:"}))
		return tmp			
	
	def get_table_fields(self):
		return [
			frappe._dict({"fieldname": "fields", "options": "DocField"}), 
			frappe._dict({"fieldname": "permissions", "options": "DocPerm"})
		]
		
	def get_valid_columns(self):
		if not hasattr(self, "_valid_columns"):
			doctype = self.__dict__.get("doctype")
			self._valid_columns = frappe.db.get_table_columns(doctype)
		
		return self._valid_columns
		
	def get_table_field_doctype(self, fieldname):
		return { "fields": "DocField", "permissions": "DocPerm"}.get(fieldname)

	def process(self):
		self.add_custom_fields()
		self.apply_property_setters()
		self.sort_fields()
		
	def add_custom_fields(self):
		try:
			self.extend("fields", frappe.db.sql("""SELECT * FROM `tabCustom Field`
				WHERE dt = %s AND docstatus < 2""", (doctype,), as_dict=1))
		except Exception, e:
			if e.args[0]==1146:
				return
			else:
				raise
	
	def apply_property_setters(self):
		for ps in frappe.db.sql("""select * from `tabProperty Setter` where
			doc_type=%s""", (doctype,), as_dict=1):
			if ps['doctype_or_field']=='DocType':
				if ps.get('property_type', None) in ('Int', 'Check'):
					ps['value'] = cint(ps['value'])

				self.set(ps["property"], ps["value"])
			else:
				docfield = self.get("fields", {"fieldname":ps["fieldname"]}, limit=1)[0]

				if not docfield: continue
				if ps["property"] in integer_docfield_properties:
					ps['value'] = cint(ps['value'])

				docfield.set(ps["property"], ps["value"])
				
	def sort_fields(self):
		"""sort on basis of previous_field"""
		newlist = []
		pending = self.get("fields")

		if self.get("_idx"):
			for fieldname in json.loads(self.get("_idx")):
				d = self.get("fields", {"fieldname": fieldname}, limit=1)
				if d:
					newlist.append(d[0])
					pending.remove(d[0])
		else:
			maxloops = 20
			while (pending and maxloops>0):
				maxloops -= 1
				for d in pending[:]:
					if d.previous_field:
						# field already added
						for n in newlist:
							if n.fieldname==d.previous_field:
								newlist.insert(newlist.index(n)+1, d)
								pending.remove(d)
								break
					else:
						newlist.append(d)
						pending.remove(d)

		# recurring at end	
		if pending:
			newlist += pending

		# renum
		idx = 1
		for d in newlist:
			d.idx = idx
			idx += 1

		self.set("fields", newlist)
		
	def get_restricted_fields(self, restricted_types):
		restricted_fields = self.get("fields", {
			"fieldtype":"Link", 
			"parent": self.name, 
			"ignore_restrictions":("!=", 1), 
			"options":("in", restricted_types)
		})
		if self.name in restricted_types:
			restricted_fields.append(frappe._dict({
				"label":"Name", "fieldname":"name", "options": self.name
			}))
		return restricted_fields


#######

def is_single(doctype):
	try:
		return frappe.db.get_value("DocType", doctype, "issingle")
	except IndexError, e:
		raise Exception, 'Cannot determine whether %s is single' % doctype

def get_parent_dt(dt):
	parent_dt = frappe.db.sql("""select parent from tabDocField 
		where fieldtype="Table" and options=%s and (parent not like "old_parent:%%") 
		limit 1""", dt)
	return parent_dt and parent_dt[0][0] or ''

def set_fieldname(field_id, fieldname):
	frappe.db.set_value('DocField', field_id, 'fieldname', fieldname)

def get_link_fields(doctype):
	"""
		Returns list of link fields for a doctype in tuple (fieldname, options, label)
	"""
	import frappe.model.doctype
	doclist = frappe.model.doctype.get(doctype)
	return [(d.fields.get('fieldname'), d.fields.get('options'), d.fields.get('label')) 
		for d in doclist.get_link_fields() if d.fields.get('fieldname')!='owner']

def get_table_fields(doctype):
	child_tables = [[d[0], d[1]] for d in frappe.db.sql("""select options, fieldname 
		from tabDocField where parent=%s and fieldtype='Table'""", doctype, as_list=1)]
	
	try:
		custom_child_tables = [[d[0], d[1]] for d in frappe.db.sql("""select options, fieldname 
			from `tabCustom Field` where dt=%s and fieldtype='Table'""", doctype, as_list=1)]
	except Exception, e:
		if e.args[0]!=1146:
			raise
		custom_child_tables = []

	return child_tables + custom_child_tables

def has_field(doctype, fieldname, parent=None, parentfield=None):
	return get_field(doctype, fieldname, parent=None, parentfield=None) and True or False
		
def get_field(doctype, fieldname, parent=None, parentfield=None):
	doclist = frappe.get_doctype(doctype)
	return doclist.get_field(fieldname, parent, parentfield)
	
def get_field_currency(df, doc):
	"""get currency based on DocField options and fieldvalue in doc"""
	currency = None
	
	if ":" in cstr(df.options):
		split_opts = df.options.split(":")
		if len(split_opts)==3:
			currency = frappe.db.get_value(split_opts[0], doc.fields.get(split_opts[1]), 
				split_opts[2])
	else:
		currency = doc.fields.get(df.options)

	return currency
	
def get_field_precision(df, doc):
	"""get precision based on DocField options and fieldvalue in doc"""
	from frappe.utils import get_number_format_info
	
	number_format = None
	if df.fieldtype == "Currency":
		currency = get_field_currency(df, doc)
		if currency:
			number_format = frappe.db.get_value("Currency", currency, "number_format")
		
	if not number_format:
		number_format = frappe.db.get_default("number_format") or "#,###.##"
		
	decimal_str, comma_str, precision = get_number_format_info(number_format)

	if df.fieldtype == "Float":
		precision = cint(frappe.db.get_default("float_precision")) or 3

	return precision