# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# metadata

'''
Load metadata (DocType) class

Example:

	meta = frappe.get_meta('User')
	if meta.has_field('first_name'):
		print("DocType" table has field "first_name")


'''

from __future__ import unicode_literals, print_function
from datetime import datetime
from six.moves import range
import frappe, json, os
from frappe.utils import cstr, cint
from frappe.model import default_fields, no_value_fields, optional_fields, data_fieldtypes, table_fields
from frappe.model.document import Document
from frappe.model.base_document import BaseDocument
from frappe.modules import load_doctype_module
from frappe.model.workflow import get_workflow_name
from frappe import _

def get_meta(doctype, cached=True):
	if cached:
		if not frappe.local.meta_cache.get(doctype):
			meta = frappe.cache().hget("meta", doctype)
			if meta:
				meta = Meta(meta)
			else:
				meta = Meta(doctype)
				frappe.cache().hset('meta', doctype, meta.as_dict())
			frappe.local.meta_cache[doctype] = meta

		return frappe.local.meta_cache[doctype]
	else:
		return load_meta(doctype)

def load_meta(doctype):
	return Meta(doctype)

def get_table_columns(doctype):
	return frappe.cache().hget("table_columns", doctype,
		lambda: frappe.db.get_table_columns(doctype))

def load_doctype_from_file(doctype):
	fname = frappe.scrub(doctype)
	with open(frappe.get_app_path("frappe", "core", "doctype", fname, fname + ".json"), "r") as f:
		txt = json.loads(f.read())

	for d in txt.get("fields", []):
		d["doctype"] = "DocField"

	for d in txt.get("permissions", []):
		d["doctype"] = "DocPerm"

	txt["fields"] = [BaseDocument(d) for d in txt["fields"]]
	if "permissions" in txt:
		txt["permissions"] = [BaseDocument(d) for d in txt["permissions"]]

	return txt

class Meta(Document):
	_metaclass = True
	default_fields = list(default_fields)[1:]
	special_doctypes = ("DocField", "DocPerm", "Role", "DocType", "Module Def")

	def __init__(self, doctype):
		self._fields = {}
		if isinstance(doctype, dict):
			super(Meta, self).__init__(doctype)

		elif isinstance(doctype, Document):
			super(Meta, self).__init__(doctype.as_dict())
			self.process()

		else:
			super(Meta, self).__init__("DocType", doctype)
			self.process()

	def load_from_db(self):
		try:
			super(Meta, self).load_from_db()
		except frappe.DoesNotExistError:
			if self.doctype=="DocType" and self.name in self.special_doctypes:
				self.__dict__.update(load_doctype_from_file(self.name))
			else:
				raise

	def process(self):
		# don't process for special doctypes
		# prevent's circular dependency
		if self.name in self.special_doctypes:
			return

		self.add_custom_fields()
		self.apply_property_setters()
		self.sort_fields()
		self.get_valid_columns()
		self.set_custom_permissions()

	def as_dict(self, no_nulls = False):
		def serialize(doc):
			out = {}
			for key in doc.__dict__:
				value = doc.__dict__.get(key)

				if isinstance(value, (list, tuple)):
					if len(value) > 0 and hasattr(value[0], '__dict__'):
						value = [serialize(d) for d in value]
					else:
						# non standard list object, skip
						continue

				if (isinstance(value, (frappe.text_type, int, float, datetime, list, tuple))
					or (not no_nulls and value is None)):
					out[key] = value

			return out

		return serialize(self)

	def get_link_fields(self):
		return self.get("fields", {"fieldtype": "Link", "options":["!=", "[Select]"]})

	def get_dynamic_link_fields(self):
		if not hasattr(self, '_dynamic_link_fields'):
			self._dynamic_link_fields = self.get("fields", {"fieldtype": "Dynamic Link"})
		return self._dynamic_link_fields

	def get_select_fields(self):
		return self.get("fields", {"fieldtype": "Select", "options":["not in",
			["[Select]", "Loading..."]]})

	def get_image_fields(self):
		return self.get("fields", {"fieldtype": "Attach Image"})

	def get_set_only_once_fields(self):
		'''Return fields with `set_only_once` set'''
		if not hasattr(self, "_set_only_once_fields"):
			self._set_only_once_fields = self.get("fields", {"set_only_once": 1})
		return self._set_only_once_fields

	def get_table_fields(self):
		if not hasattr(self, "_table_fields"):
			if self.name!="DocType":
				self._table_fields = self.get('fields', {"fieldtype": ['in', table_fields]})
			else:
				self._table_fields = doctype_table_fields

		return self._table_fields

	def get_global_search_fields(self):
		'''Returns list of fields with `in_global_search` set and `name` if set'''
		fields = self.get("fields", {"in_global_search": 1, "fieldtype": ["not in", no_value_fields]})
		if getattr(self, 'show_name_in_global_search', None):
			fields.append(frappe._dict(fieldtype='Data', fieldname='name', label='Name'))

		return fields

	def get_valid_columns(self):
		if not hasattr(self, "_valid_columns"):
			if self.name in ("DocType", "DocField", "DocPerm", "Property Setter"):
				self._valid_columns = get_table_columns(self.name)
			else:
				self._valid_columns = self.default_fields + \
					[df.fieldname for df in self.get("fields") if df.fieldtype in data_fieldtypes]

		return self._valid_columns

	def get_table_field_doctype(self, fieldname):
		return { "fields": "DocField", "permissions": "DocPerm"}.get(fieldname)

	def get_field(self, fieldname):
		'''Return docfield from meta'''
		if not self._fields:
			for f in self.get("fields"):
				self._fields[f.fieldname] = f

		return self._fields.get(fieldname)

	def has_field(self, fieldname):
		'''Returns True if fieldname exists'''
		return True if self.get_field(fieldname) else False

	def get_label(self, fieldname):
		'''Get label of the given fieldname'''
		df = self.get_field(fieldname)
		if df:
			label = df.label
		else:
			label = {
				'name': _('ID'),
				'owner': _('Created By'),
				'modified_by': _('Modified By'),
				'creation': _('Created On'),
				'modified': _('Last Modified On')
			}.get(fieldname) or _('No Label')
		return label

	def get_options(self, fieldname):
		return self.get_field(fieldname).options

	def get_link_doctype(self, fieldname):
		df = self.get_field(fieldname)

		if df.fieldtype == "Link":
			return df.options

		elif df.fieldtype == "Dynamic Link":
			return self.get_options(df.options)

		else:
			return None

	def get_search_fields(self):
		search_fields = self.search_fields or "name"
		search_fields = [d.strip() for d in search_fields.split(",")]
		if "name" not in search_fields:
			search_fields.append("name")

		return search_fields

	def get_fields_to_fetch(self, link_fieldname=None):
		'''Returns a list of docfield objects for fields whose values
		are to be fetched and updated for a particular link field

		These fields are of type Data, Link, Text, Readonly and their
		options property is set as `link_fieldname`.`source_fieldname`'''

		out = []

		if not link_fieldname:
			link_fields = [df.fieldname for df in self.get_link_fields()]

		for df in self.fields:
			if df.fieldtype not in no_value_fields and getattr(df, 'fetch_from', None):
				if link_fieldname:
					if df.fetch_from.startswith(link_fieldname + '.'):
						out.append(df)
				else:
					if '.' in df.fetch_from:
						fieldname = df.fetch_from.split('.', 1)[0]
						if fieldname in link_fields:
							out.append(df)

		return out

	def get_list_fields(self):
		list_fields = ["name"] + [d.fieldname \
			for d in self.fields if (d.in_list_view and d.fieldtype in data_fieldtypes)]
		if self.title_field and self.title_field not in list_fields:
			list_fields.append(self.title_field)
		return list_fields

	def get_custom_fields(self):
		return [d for d in self.fields if d.get('is_custom_field')]

	def get_title_field(self):
		'''Return the title field of this doctype,
		explict via `title_field`, or `title` or `name`'''
		title_field = getattr(self, 'title_field', None)
		if not title_field and self.has_field('title'):
			title_field = 'title'
		if not title_field:
			title_field = 'name'

		return title_field

	def get_translatable_fields(self):
		'''Return all fields that are translation enabled'''
		return [d.fieldname for d in self.fields if d.translatable]

	def is_translatable(self, fieldname):
		'''Return true of false given a field'''
		field = self.get_field(fieldname)
		return field and field.translatable

	def get_workflow(self):
		return get_workflow_name(self.name)

	def add_custom_fields(self):
		try:
			self.extend("fields", frappe.db.sql("""SELECT * FROM `tabCustom Field`
				WHERE dt = %s AND docstatus < 2""", (self.name,), as_dict=1,
				update={"is_custom_field": 1}))
		except Exception as e:
			if frappe.db.is_table_missing(e):
				return
			else:
				raise

	def apply_property_setters(self):
		property_setters = frappe.db.sql("""select * from `tabProperty Setter` where
			doc_type=%s""", (self.name,), as_dict=1)

		if not property_setters: return

		integer_docfield_properties = [d.fieldname for d in frappe.get_meta('DocField').fields
			if d.fieldtype in ('Int', 'Check')]

		for ps in property_setters:
			if ps.doctype_or_field=='DocType':
				if ps.property_type in ('Int', 'Check'):
					ps.value = cint(ps.value)

				self.set(ps.property, ps.value)
			else:
				docfield = self.get("fields", {"fieldname":ps.field_name}, limit=1)
				if docfield:
					docfield = docfield[0]
				else:
					continue

				if ps.property in integer_docfield_properties:
					ps.value = cint(ps.value)

				docfield.set(ps.property, ps.value)

	def sort_fields(self):
		"""sort on basis of insert_after"""
		custom_fields = sorted(self.get_custom_fields(), key=lambda df: df.idx)

		if custom_fields:
			newlist = []

			# if custom field is at top
			# insert_after is false
			for c in list(custom_fields):
				if not c.insert_after:
					newlist.append(c)
					custom_fields.pop(custom_fields.index(c))

			# standard fields
			newlist += [df for df in self.get('fields') if not df.get('is_custom_field')]

			newlist_fieldnames = [df.fieldname for df in newlist]
			for i in range(2):
				for df in list(custom_fields):
					if df.insert_after in newlist_fieldnames:
						cf = custom_fields.pop(custom_fields.index(df))
						idx = newlist_fieldnames.index(df.insert_after)
						newlist.insert(idx + 1, cf)
						newlist_fieldnames.insert(idx + 1, cf.fieldname)

				if not custom_fields:
					break

			# worst case, add remaining custom fields to last
			if custom_fields:
				newlist += custom_fields

			# renum idx
			for i, f in enumerate(newlist):
				f.idx = i + 1

			self.fields = newlist

	def set_custom_permissions(self):
		'''Reset `permissions` with Custom DocPerm if exists'''
		if frappe.flags.in_patch or frappe.flags.in_install:
			return

		if not self.istable and self.name not in ('DocType', 'DocField', 'DocPerm',
			'Custom DocPerm'):
			custom_perms = frappe.get_all('Custom DocPerm', fields='*',
				filters=dict(parent=self.name), update=dict(doctype='Custom DocPerm'))
			if custom_perms:
				self.permissions = [Document(d) for d in custom_perms]

	def get_fieldnames_with_value(self):
		return [df.fieldname for df in self.fields if df.fieldtype not in no_value_fields]


	def get_fields_to_check_permissions(self, user_permission_doctypes):
		fields = self.get("fields", {
			"fieldtype":"Link",
			"parent": self.name,
			"ignore_user_permissions":("!=", 1),
			"options":("in", user_permission_doctypes)
		})

		if self.name in user_permission_doctypes:
			fields.append(frappe._dict({
				"label":"Name",
				"fieldname":"name",
				"options": self.name
			}))

		return fields

	def get_high_permlevel_fields(self):
		"""Build list of fields with high perm level and all the higher perm levels defined."""
		if not hasattr(self, "high_permlevel_fields"):
			self.high_permlevel_fields = []
			for df in self.fields:
				if df.permlevel > 0:
					self.high_permlevel_fields.append(df)

		return self.high_permlevel_fields

	def get_dashboard_data(self):
		'''Returns dashboard setup related to this doctype.

		This method will return the `data` property in the
		`[doctype]_dashboard.py` file in the doctype folder'''
		data = frappe._dict()
		try:
			module = load_doctype_module(self.name, suffix='_dashboard')
			if hasattr(module, 'get_data'):
				data = frappe._dict(module.get_data())
		except ImportError:
			pass

		return data

	def get_row_template(self):
		return self.get_web_template(suffix='_row')

	def get_web_template(self, suffix=''):
		'''Returns the relative path of the row template for this doctype'''
		module_name = frappe.scrub(self.module)
		doctype = frappe.scrub(self.name)
		template_path = frappe.get_module_path(module_name, 'doctype',
			doctype, 'templates', doctype + suffix + '.html')
		if os.path.exists(template_path):
			return '{module_name}/doctype/{doctype_name}/templates/{doctype_name}{suffix}.html'.format(
				module_name = module_name, doctype_name = doctype, suffix=suffix)
		return None

	def is_nested_set(self):
		return self.has_field('lft') and self.has_field('rgt')

doctype_table_fields = [
	frappe._dict({"fieldname": "fields", "options": "DocField"}),
	frappe._dict({"fieldname": "permissions", "options": "DocPerm"})
]

#######

def is_single(doctype):
	try:
		return frappe.db.get_value("DocType", doctype, "issingle")
	except IndexError:
		raise Exception('Cannot determine whether %s is single' % doctype)

def get_parent_dt(dt):
	parent_dt = frappe.db.get_all('DocField', 'parent', dict(fieldtype=['in', frappe.model.table_fields], options=dt), limit=1)
	return parent_dt and parent_dt[0].parent or ''

def set_fieldname(field_id, fieldname):
	frappe.db.set_value('DocField', field_id, 'fieldname', fieldname)

def get_field_currency(df, doc=None):
	"""get currency based on DocField options and fieldvalue in doc"""
	currency = None

	if not df.get("options"):
		return None

	if not doc:
		return None

	if not getattr(frappe.local, "field_currency", None):
		frappe.local.field_currency = frappe._dict()

	if not (frappe.local.field_currency.get((doc.doctype, doc.name), {}).get(df.fieldname) or
		(doc.parent and frappe.local.field_currency.get((doc.doctype, doc.parent), {}).get(df.fieldname))):

		ref_docname = doc.parent or doc.name

		if ":" in cstr(df.get("options")):
			split_opts = df.get("options").split(":")
			if len(split_opts)==3:
				currency = frappe.get_cached_value(split_opts[0], doc.get(split_opts[1]), split_opts[2])
		else:
			currency = doc.get(df.get("options"))
			if doc.parent:
				if currency:
					ref_docname = doc.name
				else:
					currency = frappe.db.get_value(doc.parenttype, doc.parent, df.get("options"))

		if currency:
			frappe.local.field_currency.setdefault((doc.doctype, ref_docname), frappe._dict())\
				.setdefault(df.fieldname, currency)

	return frappe.local.field_currency.get((doc.doctype, doc.name), {}).get(df.fieldname) or \
		(doc.parent and frappe.local.field_currency.get((doc.doctype, doc.parent), {}).get(df.fieldname))

def get_field_precision(df, doc=None, currency=None):
	"""get precision based on DocField options and fieldvalue in doc"""
	from frappe.utils import get_number_format_info

	if cint(df.precision):
		precision = cint(df.precision)

	elif df.fieldtype == "Currency":
		precision = cint(frappe.db.get_default("currency_precision"))
		if not precision:
			number_format = frappe.db.get_default("number_format") or "#,###.##"
			decimal_str, comma_str, precision = get_number_format_info(number_format)
	else:
		precision = cint(frappe.db.get_default("float_precision")) or 3

	return precision


def get_default_df(fieldname):
	if fieldname in default_fields:
		if fieldname in ("creation", "modified"):
			return frappe._dict(
				fieldname = fieldname,
				fieldtype = "Datetime"
			)

		else:
			return frappe._dict(
				fieldname = fieldname,
				fieldtype = "Data"
			)

def trim_tables(doctype=None):
	"""
	Removes database fields that don't exist in the doctype (json or custom field). This may be needed
	as maintenance since removing a field in a DocType doesn't automatically
	delete the db field.
	"""
	ignore_fields = default_fields + optional_fields

	filters={ "issingle": 0 }
	if doctype:
		filters["name"] = doctype

	for doctype in frappe.db.get_all("DocType", filters=filters):
		doctype = doctype.name
		columns = frappe.db.get_table_columns(doctype)
		fields = frappe.get_meta(doctype).get_fieldnames_with_value()
		columns_to_remove = [f for f in list(set(columns) - set(fields)) if f not in ignore_fields
			and not f.startswith("_")]
		if columns_to_remove:
			print(doctype, "columns removed:", columns_to_remove)
			columns_to_remove = ", ".join(["drop `{0}`".format(c) for c in columns_to_remove])
			query = """alter table `tab{doctype}` {columns}""".format(
				doctype=doctype, columns=columns_to_remove)
			frappe.db.sql_ddl(query)
