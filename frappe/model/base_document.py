# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe, sys
from frappe import _
from frappe.utils import cint, flt, now, cstr, strip_html, getdate, get_datetime, to_timedelta
from frappe.model import default_fields
from frappe.model.naming import set_new_name
from frappe.modules import load_doctype_module
from frappe.model import display_fieldtypes

_classes = {}

def get_controller(doctype):
	"""Returns the **class** object of the given DocType.
	For `custom` type, returns `frappe.model.document.Document`.

	:param doctype: DocType name as string."""
	from frappe.model.document import Document
	if not doctype in _classes:
		module_name, custom = frappe.db.get_value("DocType", doctype, ["module", "custom"]) \
			or ["Core", False]

		if custom:
			_class = Document
		else:
			module = load_doctype_module(doctype, module_name)
			classname = doctype.replace(" ", "").replace("-", "")
			if hasattr(module, classname):
				_class = getattr(module, classname)
				if issubclass(_class, BaseDocument):
					_class = getattr(module, classname)
				else:
					raise ImportError, doctype
			else:
				raise ImportError, doctype
		_classes[doctype] = _class

	return _classes[doctype]

class BaseDocument(object):
	ignore_in_getter = ("doctype", "_meta", "meta", "_table_fields", "_valid_columns")

	def __init__(self, d):
		self.update(d)
		self.dont_update_if_missing = []

		if hasattr(self, "__setup__"):
			self.__setup__()

	@property
	def meta(self):
		if not hasattr(self, "_meta"):
			self._meta = frappe.get_meta(self.doctype)

		return self._meta

	def update(self, d):
		if "doctype" in d:
			self.set("doctype", d.get("doctype"))

		# first set default field values of base document
		for key in default_fields:
			if key in d:
				self.set(key, d.get(key))

		for key, value in d.iteritems():
			self.set(key, value)

		return self

	def update_if_missing(self, d):
		if isinstance(d, BaseDocument):
			d = d.get_valid_dict()

		if "doctype" in d:
			self.set("doctype", d.get("doctype"))
		for key, value in d.iteritems():
			# dont_update_if_missing is a list of fieldnames, for which, you don't want to set default value
			if (self.get(key) is None) and (value is not None) and (key not in self.dont_update_if_missing):
				self.set(key, value)

	def get_db_value(self, key):
		return frappe.db.get_value(self.doctype, self.name, key)

	def get(self, key=None, filters=None, limit=None, default=None):
		if key:
			if isinstance(key, dict):
				return _filter(self.get_all_children(), key, limit=limit)
			if filters:
				if isinstance(filters, dict):
					value = _filter(self.__dict__.get(key, []), filters, limit=limit)
				else:
					default = filters
					filters = None
					value = self.__dict__.get(key, default)
			else:
				value = self.__dict__.get(key, default)

			if value is None and key not in self.ignore_in_getter \
				and key in (d.fieldname for d in self.meta.get_table_fields()):
				self.set(key, [])
				value = self.__dict__.get(key)

			return value
		else:
			return self.__dict__

	def getone(self, key, filters=None):
		return self.get(key, filters=filters, limit=1)[0]

	def set(self, key, value, as_value=False):
		if isinstance(value, list) and not as_value:
			self.__dict__[key] = []
			self.extend(key, value)
		else:
			self.__dict__[key] = value

	def delete_key(self, key):
		if key in self.__dict__:
			del self.__dict__[key]

	def append(self, key, value=None):
		if value==None:
			value={}
		if isinstance(value, (dict, BaseDocument)):
			if not self.__dict__.get(key):
				self.__dict__[key] = []
			value = self._init_child(value, key)
			self.__dict__[key].append(value)

			# reference parent document
			value.parent_doc = self
			return value
		else:
			raise ValueError, "Document attached to child table must be a dict or BaseDocument, not " + str(type(value))[1:-1]

	def extend(self, key, value):
		if isinstance(value, list):
			for v in value:
				self.append(key, v)
		else:
			raise ValueError

	def remove(self, doc):
		self.get(doc.parentfield).remove(doc)

	def _init_child(self, value, key):
		if not self.doctype:
			return value
		if not isinstance(value, BaseDocument):
			if "doctype" not in value:
				value["doctype"] = self.get_table_field_doctype(key)
				if not value["doctype"]:
					raise AttributeError, key
			value = get_controller(value["doctype"])(value)
			value.init_valid_columns()

		value.parent = self.name
		value.parenttype = self.doctype
		value.parentfield = key

		if not getattr(value, "idx", None):
			value.idx = len(self.get(key) or []) + 1

		if not getattr(value, "name", None):
			value.__dict__['__islocal'] = 1

		return value

	def get_valid_dict(self):
		d = {}
		for fieldname in self.meta.get_valid_columns():
			d[fieldname] = self.get(fieldname)

			if d[fieldname]=="":
				df = self.meta.get_field(fieldname)
				if df and df.fieldtype in ("Datetime", "Date"):
					d[fieldname] = None

		return d

	def init_valid_columns(self):
		for key in default_fields:
			if key not in self.__dict__:
				self.__dict__[key] = None

		for key in self.get_valid_columns():
			if key not in self.__dict__:
				self.__dict__[key] = None

	def get_valid_columns(self):
		if self.doctype not in frappe.local.valid_columns:
			if self.doctype in ("DocField", "DocPerm") and self.parent in ("DocType", "DocField", "DocPerm"):
				from frappe.model.meta import get_table_columns
				valid = get_table_columns(self.doctype)
			else:
				valid = self.meta.get_valid_columns()

			frappe.local.valid_columns[self.doctype] = valid

		return frappe.local.valid_columns[self.doctype]

	def is_new(self):
		return self.get("__islocal")

	def as_dict(self, no_nulls=False, no_default_fields=False):
		doc = self.get_valid_dict()
		doc["doctype"] = self.doctype
		for df in self.meta.get_table_fields():
			children = self.get(df.fieldname) or []
			doc[df.fieldname] = [d.as_dict(no_nulls=no_nulls) for d in children]

		if no_nulls:
			for k in doc.keys():
				if doc[k] is None:
					del doc[k]

		if no_default_fields:
			for k in doc.keys():
				if k in default_fields:
					del doc[k]

		for key in ("_user_tags", "__islocal", "__onload", "_starred_by"):
			if self.get(key):
				doc[key] = self.get(key)

		return frappe._dict(doc)

	def as_json(self):
		return frappe.as_json(self.as_dict())

	def get_table_field_doctype(self, fieldname):
		return self.meta.get_field(fieldname).options

	def get_parentfield_of_doctype(self, doctype):
		fieldname = [df.fieldname for df in self.meta.get_table_fields() if df.options==doctype]
		return fieldname[0] if fieldname else None

	def db_insert(self):
		"""INSERT the document (with valid columns) in the database."""
		if not self.name:
			# name will be set by document class in most cases
			set_new_name(self)
		d = self.get_valid_dict()
		columns = d.keys()
		try:
			frappe.db.sql("""insert into `tab{doctype}`
				({columns}) values ({values})""".format(
					doctype = self.doctype,
					columns = ", ".join(["`"+c+"`" for c in columns]),
					values = ", ".join(["%s"] * len(columns))
				), d.values())
		except Exception, e:
			if e.args[0]==1062 and "PRIMARY" in cstr(e.args[1]):
				if self.meta.autoname=="hash":
					# hash collision? try again
					self.name = None
					self.db_insert()
					return
				type, value, traceback = sys.exc_info()
				frappe.msgprint(_("Duplicate name {0} {1}").format(self.doctype, self.name))
				raise frappe.NameError, (self.doctype, self.name, e), traceback
			else:
				raise

		self.set("__islocal", False)

	def db_update(self):
		if self.get("__islocal") or not self.name:
			self.db_insert()
			return

		d = self.get_valid_dict()
		columns = d.keys()
		try:
			frappe.db.sql("""update `tab{doctype}`
				set {values} where name=%s""".format(
					doctype = self.doctype,
					values = ", ".join(["`"+c+"`=%s" for c in columns])
				), d.values() + [d.get("name")])
		except Exception, e:
			if e.args[0]==1062:
				type, value, traceback = sys.exc_info()
				fieldname = str(e).split("'")[-2]
				frappe.msgprint(_("{0} must be unique".format(self.meta.get_label(fieldname))))
				raise frappe.ValidationError, (self.doctype, self.name, e), traceback
			else:
				raise

	def db_set(self, fieldname, value, update_modified=True):
		self.set(fieldname, value)
		self.set("modified", now())
		self.set("modified_by", frappe.session.user)
		frappe.db.set_value(self.doctype, self.name, fieldname, value,
			self.modified, self.modified_by, update_modified=update_modified)

	def _fix_numeric_types(self):
		for df in self.meta.get("fields"):
			if df.fieldtype == "Check":
				self.set(df.fieldname, cint(self.get(df.fieldname)))

			elif self.get(df.fieldname) is not None:
				if df.fieldtype == "Int":
					self.set(df.fieldname, cint(self.get(df.fieldname)))

				elif df.fieldtype in ("Float", "Currency", "Percent"):
					self.set(df.fieldname, flt(self.get(df.fieldname)))

		if self.docstatus is not None:
			self.docstatus = cint(self.docstatus)

	def _get_missing_mandatory_fields(self):
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
			if self.get(df.fieldname) in (None, []) or not strip_html(cstr(self.get(df.fieldname))).strip():
				missing.append((df.fieldname, get_msg(df)))

		return missing

	def get_invalid_links(self, is_submittable=False):
		def get_msg(df, docname):
			if self.parentfield:
				return "{} #{}: {}: {}".format(_("Row"), self.idx, _(df.label), docname)
			else:
				return "{}: {}".format(_(df.label), docname)

		invalid_links = []
		cancelled_links = []
		for df in self.meta.get_link_fields() + self.meta.get("fields",
			{"fieldtype":"Dynamic Link"}):


			docname = self.get(df.fieldname)
			if docname:
				if df.fieldtype=="Link":
					doctype = df.options
					if not doctype:
						frappe.throw(_("Options not set for link field {0}").format(df.fieldname))
				else:
					doctype = self.get(df.options)
					if not doctype:
						frappe.throw(_("{0} must be set first").format(self.meta.get_label(df.options)))

				# MySQL is case insensitive. Preserve case of the original docname in the Link Field.
				value = frappe.db.get_value(doctype, docname, "name", cache=True)
				setattr(self, df.fieldname, value)

				if not value:
					invalid_links.append((df.fieldname, docname, get_msg(df, docname)))

				elif (df.fieldname != "amended_from"
					and (is_submittable or self.meta.is_submittable) and frappe.get_meta(doctype).is_submittable
					and cint(frappe.db.get_value(doctype, docname, "docstatus"))==2):

					cancelled_links.append((df.fieldname, docname, get_msg(df, docname)))

		return invalid_links, cancelled_links

	def _validate_selects(self):
		if frappe.flags.in_import:
			return

		for df in self.meta.get_select_fields():
			if df.fieldname=="naming_series" or not (self.get(df.fieldname) and df.options):
				continue

			options = (df.options or "").split("\n")

			# if only empty options
			if not filter(None, options):
				continue

			# strip and set
			self.set(df.fieldname, cstr(self.get(df.fieldname)).strip())
			value = self.get(df.fieldname)

			if value not in options and not (frappe.flags.in_test and value.startswith("_T-")):
				# show an elaborate message
				prefix = _("Row #{0}:").format(self.idx) if self.get("parentfield") else ""
				label = _(self.meta.get_label(df.fieldname))
				comma_options = '", "'.join(_(each) for each in options)

				frappe.throw(_('{0} {1} cannot be "{2}". It should be one of "{3}"').format(prefix, label,
					value, comma_options))

	def _validate_constants(self):
		if frappe.flags.in_import or self.is_new():
			return

		constants = [d.fieldname for d in self.meta.get("fields", {"set_only_once": 1})]
		if constants:
			values = frappe.db.get_value(self.doctype, self.name, constants, as_dict=True)

		for fieldname in constants:
			if self.get(fieldname) != values.get(fieldname):
				frappe.throw(_("Value cannot be changed for {0}").format(self.meta.get_label(fieldname)),
					frappe.CannotChangeConstantError)

	def _validate_update_after_submit(self):
		db_values = frappe.db.get_value(self.doctype, self.name, "*", as_dict=True)
		for key, db_value in db_values.iteritems():
			df = self.meta.get_field(key)

			if df and not df.allow_on_submit and (self.get(key) or db_value):
				self_value = self.get_value(key)

				if self_value != db_value:
					frappe.throw(_("Not allowed to change {0} after submission").format(df.label),
						frappe.UpdateAfterSubmitError)

	def precision(self, fieldname, parentfield=None):
		"""Returns float precision for a particular field (or get global default).

		:param fieldname: Fieldname for which precision is required.
		:param parentfield: If fieldname is in child table."""
		from frappe.model.meta import get_field_precision

		if parentfield and not isinstance(parentfield, basestring):
			parentfield = parentfield.parentfield

		cache_key = parentfield or "main"

		if not hasattr(self, "_precision"):
			self._precision = frappe._dict()

		if cache_key not in self._precision:
			self._precision[cache_key] = frappe._dict()

		if fieldname not in self._precision[cache_key]:
			self._precision[cache_key][fieldname] = None

			doctype = self.meta.get_field(parentfield).options if parentfield else self.doctype
			df = frappe.get_meta(doctype).get_field(fieldname)

			if df.fieldtype in ("Currency", "Float", "Percent"):
				self._precision[cache_key][fieldname] = get_field_precision(df, self)

		return self._precision[cache_key][fieldname]


	def get_formatted(self, fieldname, doc=None, currency=None):
		from frappe.utils.formatters import format_value

		df = self.meta.get_field(fieldname)
		if not df and fieldname in default_fields:
			from frappe.model.meta import get_default_df
			df = get_default_df(fieldname)

		return format_value(self.get(fieldname), df=df, doc=doc or self, currency=currency)

	def is_print_hide(self, fieldname, df=None, for_print=True):
		"""Returns true if fieldname is to be hidden for print.

		Print Hide can be set via the Print Format Builder or in the controller as a list
		of hidden fields. Example

			class MyDoc(Document):
				def __setup__(self):
					self.print_hide = ["field1", "field2"]

		:param fieldname: Fieldname to be checked if hidden.
		"""
		meta_df = self.meta.get_field(fieldname)
		if meta_df and meta_df.get("__print_hide"):
			return True
		if df:
			return df.print_hide
		if meta_df:
			return meta_df.print_hide

	def in_format_data(self, fieldname):
		"""Returns True if shown via Print Format::`format_data` property.
			Called from within standard print format."""
		doc = getattr(self, "parent_doc", self)

		if hasattr(doc, "format_data_map"):
			return fieldname in doc.format_data_map
		else:
			return True

	def reset_values_if_no_permlevel_access(self, has_access_to, high_permlevel_fields):
		"""If the user does not have permissions at permlevel > 0, then reset the values to original / default"""
		to_reset = []

		for df in high_permlevel_fields:
			if df.permlevel not in has_access_to and df.fieldtype not in display_fieldtypes:
				to_reset.append(df)

		if to_reset:
			if self.is_new():
				# if new, set default value
				ref_doc = frappe.new_doc(self.doctype)
			else:
				# get values from old doc
				if self.parent:
					self.parent_doc.get_latest()
					ref_doc = [d for d in self.parent_doc.get(self.parentfield) if d.name == self.name][0]
				else:
					ref_doc = self.get_latest()

			for df in to_reset:
				self.set(df.fieldname, ref_doc.get(df.fieldname))

	def get_value(self, fieldname):
		df = self.meta.get_field(fieldname)
		val = self.get(fieldname)

		return self.cast(val, df)

	def cast(self, val, df):
		if df.fieldtype in ("Currency", "Float", "Percent"):
			val = flt(val)

		elif df.fieldtype in ("Int", "Check"):
			val = cint(val)

		elif df.fieldtype in ("Data", "Text", "Small Text", "Long Text",
			"Text Editor", "Select", "Link", "Dynamic Link"):
				val = cstr(val)

		elif df.fieldtype == "Date":
			val = getdate(val)

		elif df.fieldtype == "Datetime":
			val = get_datetime(val)

		elif df.fieldtype == "Time":
			val = to_timedelta(val)

		return val

	def _extract_images_from_text_editor(self):
		from frappe.utils.file_manager import extract_images_from_doc
		if self.doctype != "DocType":
			for df in self.meta.get("fields", {"fieldtype":"Text Editor"}):
				extract_images_from_doc(self, df.fieldname)

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
				fval = ("not None", fval)
			elif fval is False:
				fval = ("None", fval)
			elif not isinstance(fval, (tuple, list)):
				if isinstance(fval, basestring) and fval.startswith("^"):
					fval = ("^", fval[1:])
				else:
					fval = ("=", fval)

			if not frappe.compare(getattr(d, f, None), fval[0], fval[1]):
				add = False
				break

		if add:
			out.append(d)
			if limit and (len(out)-1)==limit:
				break

	return out
