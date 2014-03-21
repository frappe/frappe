# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
from frappe.utils import cint, flt
from frappe.model import default_fields
from frappe.model.db_schema import type_map
from frappe.model.naming import set_new_name

# validation - links, mandatory
# once_only validation
# permissions
# methods
# timestamps and docstatus
# defaults (insert)

class BaseDocument(object):
	def __init__(self, d):
		self.update(d)

	def __getattr__(self, key):
		if self.__dict__.has_key(key):
			return self.__dict__[key]
		if key != "_table_columns" and key in self.get_table_columns():
			return None
		raise AttributeError, key

	def update(self, d):
		if "doctype" in d:
			self.set("doctype", d.get("doctype"))
		for key, value in d.iteritems():
			self.set(key, value)
		
	def get(self, key=None, default=None):
		if key:
			return self.__dict__.get(key, default)
		else:
			return self.__dict__
				
	def set(self, key, value):
		if isinstance(value, list):
			for v in value:
				self.set(key, v)
			return
		else:
			if isinstance(value, dict):
				# appending
				if not self.get(key):
					self.__dict__[key] = []
				self.get(key).append(self._init_child(value, key))
				return
			
		self.__dict__[key] = value
	
	def _init_child(self, value, key):
		if not self.doctype:
			return value
		if not isinstance(value, BaseDocument):
			if not value.get("doctype"):
				value["doctype"] = self.meta.get({"fieldname":key})[0].options
			if not value.get("doctype"):
				raise AttributeError, key
			value = BaseDocument(value)
			
		value.parent = self.name
		value.parenttype = self.doctype
		value.parentfield = key
		if not value.idx:
			value.idx = len(self.get(key))
				
		return value

		
	@property
	def meta(self):
		if not self.get("_meta"):
			self._meta = frappe.get_doctype(self.doctype)
		return self._meta
		
	def get_valid_dict(self):
		d = {}
		for fieldname in self.table_columns:
			d[fieldname] = self.get(fieldname)
		return d
			
	@property
	def table_columns(self):
		return self.get_table_columns()

	def get_table_columns(self):
		if not hasattr(self, "_table_columns"):
			doctype = self.__dict__.get("doctype")
			self._table_columns = default_fields[1:] + \
				[df.fieldname for df in frappe.get_doctype(doctype).get_docfields()
					if df.fieldtype in type_map]
		
		return self._table_columns
	
	def insert_row(self):
		set_new_name(self)
		d = self.get_valid_dict()
		columns = d.keys()
		frappe.db.sql("""insert into `tab{doctype}` 
			({columns}) values ({values})""".format(
				doctype = self.doctype,
				columns = ", ".join(["`"+c+"`" for c in columns]),
				values = ", ".join(["%s"] * len(columns))
			), d.values())
			
	def fix_numeric_types(self):
		for df in self.meta.get_docfields():
			if df.fieldtype in ("Int", "Check"):
				self.set(df.fieldname, cint(self.get(df.fieldname)))
			elif df.fieldtype in ("Float", "Currency"):
				self.set(df.fieldname, flt(self.get(df.fieldname)))
		
		if self.docstatus is not None:	
			self.docstatus = cint(self.docstatus)
			

class Document(BaseDocument):
	def __init__(self, arg1, arg2=None):
		self.doctype = self.name = None
		if isinstance(arg1, basestring) and not arg2:
			# single
			self.doctype = self.name = arg1
		if arg1 and isinstance(arg1, basestring) and arg2:
			self.doctype = arg1
			if isinstance(arg2, dict):
				# filter
				self.name = frappe.db.get_value(arg1, arg2, "name")
				if self.name is None:
					raise frappe.DoesNotExistError
			else:
				self.name = arg2
					
			self.load_from_db()
		elif isinstance(arg1, dict):
			super(Document, self).__init__(arg1)

	def load_from_db(self):
		if self.meta[0].issingle:
			self.update(frappe.db.get_singles_dict(self.doctype))
			self.fix_numeric_types()
		else:
			d = frappe.db.get_value(self.doctype, self.name, "*", as_dict=1)
			for df in self.meta.get({"doctype":"DocField", "fieldtype":"Table"}):
				d[df.fieldname] = frappe.db.get_values(df.options, 
					{"parent": self.name}, "*", as_dict=True)
			self.update(d)
					
	def insert(self):
		# check links
		# check permissions
		
		# parent
		if self.meta[0].issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.insert_row()
		
		# children
		for df in self.meta.get({"fieldtype":"Table"}):
			value = self.get(df.fieldname)
			if isinstance(value, list):
				for d in value:
					d.parent = self.name
					print d.__dict__
					d.insert_row()

	def update_single(self, d):
		frappe.db.sql("""delete from tabSingles where doctype=%s""", d.get("doctype"))
		for field, value in d.iteritems():
			if field not in ("doctype"):
				frappe.db.sql("""insert into tabSingles(doctype, field, value) 
					values (%s, %s, %s)""", (d.get("doctype", field, value)))
	
	
					
