# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint
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

		if key in self.get_table_columns():
			return None

		raise AttributeError(key)

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
		if isinstance(value, dict):
			# appending
			if not self.get(key):
				self.__dict__[key] = []
			self.get(key).append(self._init_child(value, key))
		elif isinstance(value, list):
			for v in value:
				self.set(key, v)
		else:
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
			self._meta = frappe.get_meta(self.doctype)
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
				[df.fieldname for df in frappe.get_meta(doctype).get_docfields()
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
			
	def set_missing_values(self, d):
		for key, value in d.iteritems():
			if self.get(key) is None:
				self.set(key, value)
				
	def get_missing_mandatory_fields(self):
		"""Get mandatory fields that do not have any values"""
		def get_msg(df):
			if df.fieldtype == "Table":
				return "{}: {}: {}".format(_("Error"), _("Data missing in table"), _(df.label))
	
			elif self.parentfield:
				return "{}: {} #{}: {}: {}".format(_("Error"), _("Row"), self.idx,
					_("Value missing for"), _(df.label))

			else:
				return "{}: {}: {}".format(_("Error"), _("Value missing for"), _(df.label))
				
		missing = []
		
		for df in self.meta.get({"doctype": "DocField", "reqd": 1}):
			if self.get(df.fieldname) in (None, []):
				missing.append((df.fieldname, get_msg(df)))
		
		return missing
		
	def get_invalid_links(self):
		def get_msg(df, docname):
			if self.parentfield:
				return "{} #{}: {}: {}".format(_("Row"), self.idx, _(df.label), docname)
			else:
				return "{}: {}".format(_(df.label), docname)
		
		invalid_links = []
		for df in self.meta.get_link_fields():
			doctype = df.options
			
			if not doctype:
				frappe.throw("Options not set for link field: {}".format(df.fieldname))
			
			elif doctype.lower().startswith("link:"):
				doctype = doctype[5:]
				
			docname = self.get(df.fieldname)
			if docname and not frappe.db.get_value(doctype, docname):
				invalid_links.append((df.fieldname, docname, get_msg(df, docname)))
		
		return invalid_links
		
class Document(BaseDocument):
	def __init__(self, arg1, arg2=None):
		self.doctype = self.name = None
		if arg1 and isinstance(arg1, basestring):
			if not arg2:
				# single
				self.doctype = self.name = arg1
			else:
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
		
		else:
			# incorrect arguments. let's not proceed.
			raise frappe.DataError("Document({0}, {1})".format(arg1, arg2))

	def load_from_db(self):
		if self.meta[0].issingle:
			self.update(frappe.db.get_singles_dict(self.doctype))
			self.fix_numeric_types()
		
		else:
			d = frappe.db.get_value(self.doctype, self.name, "*", as_dict=1)
			for df in self.meta.get({"doctype":"DocField", "fieldtype":"Table"}):
				d[df.fieldname] = frappe.db.get_values(df.options, 
					{"parent": self.name, "parenttype": self.doctype, "parentfield": df.fieldname}, 
					"*", as_dict=True)
			self.update(d)
					
	def insert(self):
		# check links
		# check permissions
		
		self.set_defaults()
		self._validate()
		
		# run validate, on update etc.
		
		# parent
		if self.meta[0].issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.insert_row()
		
		# children
		for d in self.get_all_children():
			d.parent = self.name
			d.insert_row()

	def update_single(self, d):
		frappe.db.sql("""delete from tabSingles where doctype=%s""", d.get("doctype"))
		for field, value in d.iteritems():
			if field not in ("doctype"):
				frappe.db.sql("""insert into tabSingles(doctype, field, value) 
					values (%s, %s, %s)""", (d.get("doctype", field, value)))
	
			
	def set_defaults(self):
		if frappe.flags.in_import:
			return
		
		new_doc = frappe.new_doc(self.doctype).fields
		self.set_missing_values(new_doc)

		# children
		for df in self.meta.get({"fieldtype":"Table"}):
			new_doc = frappe.new_doc(df.options).fields
			value = self.get(df.fieldname)
			if isinstance(value, list):
				for d in value:
					d.set_missing_values(new_doc)

	def _validate(self):
		self.trigger("validate")
		self.validate_mandatory()
		self.validate_links()
			
		# check restrictions
		
	def validate_mandatory(self):
		if self.get("ignore_mandatory"):
			return
			
		missing = self.get_missing_mandatory_fields()
		for d in self.get_all_children():
			missing.extend(d.get_missing_mandatory_fields())
		
		if not missing:
			return
		
		for fieldname, msg in missing:
			msgprint(msg)
		
		raise frappe.MandatoryError(", ".join((each[0] for each in missing)))
			
	def validate_links(self):
		if self.get("ignore_links"):
			return
		
		invalid_links = self.get_invalid_links()
		for d in self.get_all_children():
			invalid_links.extend(d.get_invalid_links())
		
		if not invalid_links:
			return
			
		msg = ", ".join((each[2] for each in invalid_links))
		frappe.throw("{}: {}".format(_("Could not find the following documents"), msg),
			frappe.LinkValidationError)
			
	def get_all_children(self):
		ret = []
		for df in self.meta.get({"fieldtype": "Table"}):
			value = self.get(df.fieldname)
			if isinstance(value, list):
				ret.extend(value)
		return ret
			
	def trigger(self, func, *args, **kwargs):
		return