# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import frappe
from frappe import _, msgprint
from frappe.utils import cint, flt, cstr, now
from frappe.model import default_fields
from frappe.model.db_schema import type_map
from frappe.model.naming import set_new_name

# save / update
# once_only validation
# permissions
# methods
# timestamps and docstatus

class BaseDocument(object):
	def __init__(self, d, valid_columns=None):
		self.update(d, valid_columns=valid_columns)

	def __getattr__(self, key):
		if self.__dict__.has_key(key):
			return self.__dict__[key]

		if key!= "_valid_columns" and key in self.get_valid_columns():
			return None

		raise AttributeError(key)

	def update(self, d, valid_columns=None):
		if valid_columns:
			self.__dict__["_valid_columns"] = valid_columns
		if "doctype" in d:
			self.set("doctype", d.get("doctype"))
		for key, value in d.iteritems():
			self.set(key, value)
		
	def get(self, key=None, filters=None, limit=None, default=None):
		if key:
			if filters:
				return _filter(self.__dict__.get(key), filters, limit=limit)
			else:
				return self.__dict__.get(key, default)
		else:
			return self.__dict__
				
	def set(self, key, value, valid_columns=None):
		if isinstance(value, list):
			tmp = []
			for v in value:
				tmp.append(self._init_child(v, key, valid_columns))
			value = tmp

		self.__dict__[key] = value
			
	def append(self, key, value):
		if isinstance(value, dict):
			if not self.get(key):
				self.__dict__[key] = []
			self.get(key).append(self._init_child(value, key))
		else:
			raise ValueError
			
	def extend(self, key, value):
		if isinstance(value, list):
			for v in value:
				self.append(v)
		else:
			raise ValueError
	
	def _init_child(self, value, key, valid_columns=None):
		if not self.doctype:
			return value
		if not isinstance(value, BaseDocument):
			if not value.get("doctype"):
				value["doctype"] = self.get_table_field_doctype(key)
			if not value.get("doctype"):
				raise AttributeError, key
			value = BaseDocument(value, valid_columns=valid_columns)
			
		value.parent = self.name
		value.parenttype = self.doctype
		value.parentfield = key
		if not value.idx:
			value.idx = len(self.get(key) or []) + 1
				
		return value

	@property
	def meta(self):
		if not self.get("_meta"):
			self._meta = frappe.get_meta(self.doctype)
		return self._meta
		
	def get_valid_dict(self):
		d = {}
		for fieldname in self.valid_columns:
			d[fieldname] = self.get(fieldname)
		return d
					
	@property
	def valid_columns(self):
		return self.get_valid_columns()

	def get_valid_columns(self):
		if not hasattr(self, "_valid_columns"):
			doctype = self.__dict__.get("doctype")
			self._valid_columns = default_fields[1:] + \
				[df.fieldname for df in frappe.get_meta(doctype).get("fields")
					if df.fieldtype in type_map]
		
		return self._valid_columns
		
	def get_table_field_doctype(self, fieldname):
		return self.meta.get("fields", {"fieldname":fieldname})[0].options
	
	def db_insert(self):
		set_new_name(self)
		d = self.get_valid_dict()
		columns = d.keys()
		frappe.db.sql("""insert into `tab{doctype}` 
			({columns}) values ({values})""".format(
				doctype = self.doctype,
				columns = ", ".join(["`"+c+"`" for c in columns]),
				values = ", ".join(["%s"] * len(columns))
			), d.values())
		self.set("__islocal", False)

	def db_update(self):
		d = self.get_valid_dict()
		columns = d.keys()
		frappe.db.sql("""update `tab{doctype}` 
			set {values} where name=%s""".format(
				doctype = self.doctype,
				values = ", ".join(["`"+c+"`=%s" for c in columns])
			), d.values() + [d.get("name")])
			
	def fix_numeric_types(self):
		for df in self.meta.get("fields"):
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
		
		for df in self.meta.get("fields", {"reqd": 1}):
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
		if not getattr(self, "_metaclass", False) and self.meta.issingle:
			self.update(frappe.db.get_singles_dict(self.doctype))
			self.fix_numeric_types()
		
		else:
			d = frappe.db.get_value(self.doctype, self.name, "*", as_dict=1)
			self.update(d, valid_columns = d.keys())

			for df in self.get_table_fields():
				children = frappe.db.get_values(df.options, 
					{"parent": self.name, "parenttype": self.doctype, "parentfield": df.fieldname}, 
					"*", as_dict=True)
				if children:
					self.set(df.fieldname, children, children[0].keys())
				else:
					self.set(df.fieldname, [])
			
	def get_table_fields(self):
		return self.meta.get('fields', {"fieldtype":"Table"})
					
	def insert(self):
		# check links
		# check permissions
		
		self._set_defaults()
		self._set_docstatus_user_and_timestamp()
		self._validate()
		
		# run validate, on update etc.
		
		# parent
		if self.meta.issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.db_insert()
		
		# children
		for d in self.get_all_children():
			d.parent = self.name
			d.db_insert()

	def save(self):
		if self.get("__islocal") or not self.get("name"):
			self.insert()
			return

		self._set_docstatus_user_and_timestamp()
		self._validate()

		# parent
		if self.meta.issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.db_update()

		# children
		for d in self.get_all_children():
			d.parent = self.name
			d.db_update()
			
	def update_single(self, d):
		frappe.db.sql("""delete from tabSingles where doctype=%s""", self.doctype)
		for field, value in d.iteritems():
			if field not in ("doctype"):
				frappe.db.sql("""insert into tabSingles(doctype, field, value) 
					values (%s, %s, %s)""", (self.doctype, field, value))

	def _set_docstatus_user_and_timestamp(self):
		self._original_modified = self.modified
		self.modified = now()
		self.modified_by = frappe.session.user
		if not self.creation:
			self.creation = self.modified
		if not self.owner:
			self.owner = self.modified_by
		if self.docstatus==None:
			self.docstatus=0
		
		for d in self.get_all_children():
			d.docstatus = self.docstatus
			d.modified = self.modified
			d.modified_by = self.modified_by
			if not d.owner:
				d.owner = self.owner
			if not d.creation:
				d.creation = self.creation
			
	def _set_defaults(self):
		if frappe.flags.in_import:
			return
		
		new_doc = frappe.new_doc(self.doctype).fields
		self.set_missing_values(new_doc)

		# children
		for df in self.meta.get("fields", {"fieldtype":"Table"}):
			new_doc = frappe.new_doc(df.options).fields
			value = self.get(df.fieldname)
			if isinstance(value, list):
				for d in value:
					d.set_missing_values(new_doc)

	def _validate(self):
		self.check_if_latest()
		self.validate_mandatory()
		self.validate_links()
			
		# check restrictions
		
	def check_if_latest(self):
		conflict = False
		if not self.get('__islocal'):
			if self.meta.issingle:
				modified = frappe.db.get_value(self.doctype, self.name, "modified")
				if cstr(modified) and cstr(modified) != cstr(self._original_modified):
					conflict = True
			else:
				tmp = frappe.db.get_value(self.doctype, self.name, 
					["modified", "docstatus"], as_dict=True)

				if not tmp:
					frappe.msgprint("""This record does not exist. Please refresh.""", raise_exception=1)

				modified = cstr(tmp.modified)
								
				if modified and modified != cstr(self._original_modified):
					conflict = True
			
				self.check_docstatus_transition(tmp.docstatus)
				
			if conflict:
				frappe.msgprint(_("Error: Document has been modified after you have opened it") \
				+ (" (%s, %s). " % (modified, self.modified)) \
				+ _("Please refresh to get the latest document."), 
					raise_exception=frappe.TimestampMismatchError)

	def check_docstatus_transition(self, docstatus):
		if not self.docstatus:
			self.docstatus = 0
		if docstatus==0:
			if self.docstatus==0:
				self._action = "save"
			elif self.docstatus==1:
				self._action = "submit"
			else:
				raise frappe.DocstatusTransitionError
		
		elif docstatus==1:
			if self.docstatus==1:
				self._action = "update_after_submit"
				self.validate_update_after_submit()
			elif self.docstatus==2:
				self._action = "cancel"
			else:
				raise frappe.DocstatusTransitionError
				
		elif docstatus==2:
			raise frappe.ValidationError
	
	def validate_update_after_submit(self):
		# check only allowed values are updated
		pass
	
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
		for df in self.meta.get("fields", {"fieldtype": "Table"}):
			value = self.get(df.fieldname)
			if isinstance(value, list):
				ret.extend(value)
		return ret
			
	def trigger(self, func, *args, **kwargs):
		return
		
def _filter(data, filters, limit=None):
	"""pass filters as:
		{"key": "val", "key": ["!=", "val"],
		"key": ["in", "val"], "key": ["not in", "val"], "key": "^val",
		"key" : True (exists), "key": False (does not exist) }"""

	out = []
	
	for d in data:
		add = True
		for f in filters:
			fval = filters[f]
			
			if fval is True:
				fval = ["not None", fval]
			elif fval is False:
				fval = ["None", fval]
			elif not isinstance(fval, (tuple, list)):
				if isinstance(fval, basestring) and fval.startswith("^"):
					fval = ["^", fval[1:]]
				else:
					fval = ["=", fval]
			
			if not frappe.compare(d.get(f), fval[0], fval[1]):
				add = False
				break

		if add:
			out.append(d)
			if limit and (len(out)-1)==limit:
				break
	
	return out