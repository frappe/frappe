# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# metadata

"""
Load metadata (DocType) class

Example:

	meta = frappe.get_meta('User')
	if meta.has_field('first_name'):
		print("DocType" table has field "first_name")


"""
import json
import os
from datetime import datetime

import click

import frappe
from frappe import _
from frappe.model import (
	child_table_fields,
	data_fieldtypes,
	default_fields,
	no_value_fields,
	optional_fields,
	table_fields,
)
from frappe.model.base_document import (
	DOCTYPE_TABLE_FIELDS,
	TABLE_DOCTYPES_FOR_DOCTYPE,
	BaseDocument,
)
from frappe.model.document import Document
from frappe.model.workflow import get_workflow_name
from frappe.modules import load_doctype_module
from frappe.utils import cast, cint, cstr

DEFAULT_FIELD_LABELS = {
	"name": lambda: _("ID"),
	"creation": lambda: _("Created On"),
	"docstatus": lambda: _("Document Status"),
	"idx": lambda: _("Index"),
	"modified": lambda: _("Last Updated On"),
	"modified_by": lambda: _("Last Updated By"),
	"owner": lambda: _("Created By"),
	"_user_tags": lambda: _("Tags"),
	"_liked_by": lambda: _("Liked By"),
	"_comments": lambda: _("Comments"),
	"_assign": lambda: _("Assigned To"),
}


def get_meta(doctype, cached=True) -> "Meta":
	if not cached:
		return Meta(doctype)

	if meta := frappe.cache().hget("doctype_meta", doctype):
		return meta

	meta = Meta(doctype)
	frappe.cache().hset("doctype_meta", doctype, meta)
	return meta


def load_meta(doctype):
	return Meta(doctype)


def get_table_columns(doctype):
	return frappe.db.get_table_columns(doctype)


def load_doctype_from_file(doctype):
	fname = frappe.scrub(doctype)
	with open(frappe.get_app_path("frappe", "core", "doctype", fname, fname + ".json")) as f:
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
	special_doctypes = {
		"DocField",
		"DocPerm",
		"DocType",
		"Module Def",
		"DocType Action",
		"DocType Link",
		"DocType State",
	}
	standard_set_once_fields = [
		frappe._dict(fieldname="creation", fieldtype="Datetime"),
		frappe._dict(fieldname="owner", fieldtype="Data"),
	]

	def __init__(self, doctype):
		if isinstance(doctype, Document):
			super().__init__(doctype.as_dict())
		else:
			super().__init__("DocType", doctype)

		self.process()

	def load_from_db(self):
		try:
			super().load_from_db()
		except frappe.DoesNotExistError:
			if self.doctype == "DocType" and self.name in self.special_doctypes:
				self.__dict__.update(load_doctype_from_file(self.name))
			else:
				raise

	def process(self):
		# don't process for special doctypes
		# prevents circular dependency
		if self.name in self.special_doctypes:
			self.init_field_caches()
			return

		self.add_custom_fields()
		self.apply_property_setters()
		self.init_field_caches()
		self.sort_fields()
		self.get_valid_columns()
		self.set_custom_permissions()
		self.add_custom_links_and_actions()

	def as_dict(self, no_nulls=False):
		def serialize(doc):
			out = {}
			for key, value in doc.__dict__.items():
				if isinstance(value, (list, tuple)):
					if not value or not isinstance(value[0], BaseDocument):
						# non standard list object, skip
						continue

					value = [serialize(d) for d in value]

				if (not no_nulls and value is None) or isinstance(
					value, (str, int, float, datetime, list, tuple)
				):
					out[key] = value

			# set empty lists for unset table fields
			for fieldname in TABLE_DOCTYPES_FOR_DOCTYPE.keys():
				if out.get(fieldname) is None:
					out[fieldname] = []

			return out

		return serialize(self)

	def get_link_fields(self):
		return self.get("fields", {"fieldtype": "Link", "options": ["!=", "[Select]"]})

	def get_data_fields(self):
		return self.get("fields", {"fieldtype": "Data"})

	def get_phone_fields(self):
		return self.get("fields", {"fieldtype": "Phone"})

	def get_dynamic_link_fields(self):
		if not hasattr(self, "_dynamic_link_fields"):
			self._dynamic_link_fields = self.get("fields", {"fieldtype": "Dynamic Link"})
		return self._dynamic_link_fields

	def get_select_fields(self):
		return self.get(
			"fields", {"fieldtype": "Select", "options": ["not in", ["[Select]", "Loading..."]]}
		)

	def get_image_fields(self):
		return self.get("fields", {"fieldtype": "Attach Image"})

	def get_code_fields(self):
		return self.get("fields", {"fieldtype": "Code"})

	def get_set_only_once_fields(self):
		"""Return fields with `set_only_once` set"""
		if not hasattr(self, "_set_only_once_fields"):
			self._set_only_once_fields = self.get("fields", {"set_only_once": 1})
			fieldnames = [d.fieldname for d in self._set_only_once_fields]

			for df in self.standard_set_once_fields:
				if df.fieldname not in fieldnames:
					self._set_only_once_fields.append(df)

		return self._set_only_once_fields

	def get_table_fields(self):
		return self._table_fields

	def get_global_search_fields(self):
		"""Returns list of fields with `in_global_search` set and `name` if set"""
		fields = self.get("fields", {"in_global_search": 1, "fieldtype": ["not in", no_value_fields]})
		if getattr(self, "show_name_in_global_search", None):
			fields.append(frappe._dict(fieldtype="Data", fieldname="name", label="Name"))

		return fields

	def get_valid_columns(self):
		if not hasattr(self, "_valid_columns"):
			table_exists = frappe.db.table_exists(self.name)
			if self.name in self.special_doctypes and table_exists:
				self._valid_columns = get_table_columns(self.name)
			else:
				self._valid_columns = self.default_fields + [
					df.fieldname for df in self.get("fields") if df.fieldtype in data_fieldtypes
				]
				if self.istable:
					self._valid_columns += list(child_table_fields)

		return self._valid_columns

	def get_table_field_doctype(self, fieldname):
		return TABLE_DOCTYPES_FOR_DOCTYPE.get(fieldname)

	def get_field(self, fieldname):
		"""Return docfield from meta"""

		return self._fields.get(fieldname)

	def has_field(self, fieldname):
		"""Returns True if fieldname exists"""

		return fieldname in self._fields

	def get_label(self, fieldname):
		"""Get label of the given fieldname"""

		if df := self.get_field(fieldname):
			return df.get("label")

		if fieldname in DEFAULT_FIELD_LABELS:
			return DEFAULT_FIELD_LABELS[fieldname]()

		return _("No Label")

	def get_options(self, fieldname):
		return self.get_field(fieldname).options

	def get_link_doctype(self, fieldname):
		df = self.get_field(fieldname)

		if df.fieldtype == "Link":
			return df.options

		if df.fieldtype == "Dynamic Link":
			return self.get_options(df.options)

	def get_search_fields(self):
		search_fields = self.search_fields or "name"
		search_fields = [d.strip() for d in search_fields.split(",")]
		if "name" not in search_fields:
			search_fields.append("name")

		return search_fields

	def get_fields_to_fetch(self, link_fieldname=None):
		"""Returns a list of docfield objects for fields whose values
		are to be fetched and updated for a particular link field

		These fields are of type Data, Link, Text, Readonly and their
		fetch_from property is set as `link_fieldname`.`source_fieldname`"""

		out = []

		if not link_fieldname:
			link_fields = [df.fieldname for df in self.get_link_fields()]

		for df in self.fields:
			if df.fieldtype not in no_value_fields and getattr(df, "fetch_from", None):
				if link_fieldname:
					if df.fetch_from.startswith(link_fieldname + "."):
						out.append(df)
				else:
					if "." in df.fetch_from:
						fieldname = df.fetch_from.split(".", 1)[0]
						if fieldname in link_fields:
							out.append(df)

		return out

	def get_list_fields(self):
		list_fields = ["name"] + [
			d.fieldname for d in self.fields if (d.in_list_view and d.fieldtype in data_fieldtypes)
		]
		if self.title_field and self.title_field not in list_fields:
			list_fields.append(self.title_field)
		return list_fields

	def get_custom_fields(self):
		return [d for d in self.fields if getattr(d, "is_custom_field", False)]

	def get_title_field(self):
		"""Return the title field of this doctype,
		explict via `title_field`, or `title` or `name`"""
		title_field = getattr(self, "title_field", None)
		if not title_field and self.has_field("title"):
			title_field = "title"
		if not title_field:
			title_field = "name"

		return title_field

	def get_translatable_fields(self):
		"""Return all fields that are translation enabled"""
		return [d.fieldname for d in self.fields if d.translatable]

	def is_translatable(self, fieldname):
		"""Return true of false given a field"""

		if field := self.get_field(fieldname):
			return field.translatable

	def get_workflow(self):
		return get_workflow_name(self.name)

	def get_naming_series_options(self) -> list[str]:
		"""Get list naming series options."""

		if field := self.get_field("naming_series"):
			options = field.options or ""
			return options.split("\n")

		return []

	def add_custom_fields(self):
		if not frappe.db.table_exists("Custom Field"):
			return

		custom_fields = frappe.db.get_values(
			"Custom Field",
			filters={"dt": self.name},
			fieldname="*",
			as_dict=True,
			order_by="idx",
			update={"is_custom_field": 1},
		)

		if not custom_fields:
			return

		self.extend("fields", custom_fields)

	def apply_property_setters(self):
		"""
		Property Setters are set via Customize Form. They override standard properties
		of the doctype or its child properties like fields, links etc. This method
		applies the customized properties over the standard meta object
		"""
		if not frappe.db.table_exists("Property Setter"):
			return

		property_setters = frappe.db.get_values(
			"Property Setter",
			filters={"doc_type": self.name},
			fieldname="*",
			as_dict=True,
		)

		if not property_setters:
			return

		for ps in property_setters:
			if ps.doctype_or_field == "DocType":
				self.set(ps.property, cast(ps.property_type, ps.value))

			elif ps.doctype_or_field == "DocField":
				for d in self.fields:
					if d.fieldname == ps.field_name:
						d.set(ps.property, cast(ps.property_type, ps.value))
						break

			elif ps.doctype_or_field == "DocType Link":
				for d in self.links:
					if d.name == ps.row_name:
						d.set(ps.property, cast(ps.property_type, ps.value))
						break

			elif ps.doctype_or_field == "DocType Action":
				for d in self.actions:
					if d.name == ps.row_name:
						d.set(ps.property, cast(ps.property_type, ps.value))
						break

			elif ps.doctype_or_field == "DocType State":
				for d in self.states:
					if d.name == ps.row_name:
						d.set(ps.property, cast(ps.property_type, ps.value))
						break

	def add_custom_links_and_actions(self):
		for doctype, fieldname in (
			("DocType Link", "links"),
			("DocType Action", "actions"),
			("DocType State", "states"),
		):
			# ignore_ddl because the `custom` column was added later via a patch
			for d in frappe.get_all(
				doctype, fields="*", filters=dict(parent=self.name, custom=1), ignore_ddl=True
			):
				self.append(fieldname, d)

			# set the fields in order if specified
			# order is saved as `links_order`
			order = json.loads(self.get(f"{fieldname}_order") or "[]")
			if order:
				name_map = {d.name: d for d in self.get(fieldname)}
				new_list = []
				for name in order:
					if name in name_map:
						new_list.append(name_map[name])

				# add the missing items that have not be added
				# maybe these items were added to the standard product
				# after the customization was done
				for d in self.get(fieldname):
					if d not in new_list:
						new_list.append(d)

				self.set(fieldname, new_list)

	def init_field_caches(self):
		# field map
		self._fields = {field.fieldname: field for field in self.fields}

		# table fields
		if self.name == "DocType":
			self._table_fields = DOCTYPE_TABLE_FIELDS
		else:
			self._table_fields = self.get("fields", {"fieldtype": ["in", table_fields]})

	def sort_fields(self):
		"""
		Sort fields on the basis of following rules (priority descending):
		- `field_order` property setter
		- `insert_after` computed based on default order for standard fields
		- `insert_after` property for custom fields
		"""

		if field_order := getattr(self, "field_order", []):
			field_order = [fieldname for fieldname in json.loads(field_order) if fieldname in self._fields]

			# all fields match, best case scenario
			if len(field_order) == len(self.fields):
				self._update_fields_based_on_order(field_order)
				return

			# if the first few standard fields are not in the field order, prepare to prepend them
			if self.fields[0].fieldname not in field_order:
				fields_to_prepend = []
				standard_field_found = False

				for fieldname, field in self._fields.items():
					if getattr(field, "is_custom_field", False):
						# all custom fields from here on
						break

					if fieldname in field_order:
						standard_field_found = True
						break

					fields_to_prepend.append(fieldname)

				if standard_field_found:
					field_order = fields_to_prepend + field_order
				else:
					# worst case scenario, invalidate field_order
					field_order = fields_to_prepend

		existing_fields = set(field_order) if field_order else False
		insert_after_map = {}

		for index, field in enumerate(self.fields):
			if existing_fields and field.fieldname in existing_fields:
				continue

			if not getattr(field, "is_custom_field", False):
				if existing_fields:
					# compute insert_after from previous field
					insert_after_map.setdefault(self.fields[index - 1].fieldname, []).append(field.fieldname)
				else:
					field_order.append(field.fieldname)

			elif insert_after := getattr(field, "insert_after", None):
				insert_after_map.setdefault(insert_after, []).append(field.fieldname)

			else:
				# if custom field is at the top, insert after is None
				field_order.insert(0, field.fieldname)

		if insert_after_map:
			_update_field_order_based_on_insert_after(field_order, insert_after_map)

		self._update_fields_based_on_order(field_order)

	def _update_fields_based_on_order(self, field_order):
		sorted_fields = []

		for idx, fieldname in enumerate(field_order, 1):
			field = self._fields[fieldname]
			field.idx = idx
			sorted_fields.append(field)

		self.fields = sorted_fields

	def set_custom_permissions(self):
		"""Reset `permissions` with Custom DocPerm if exists"""
		if frappe.flags.in_patch or frappe.flags.in_install:
			return

		if not self.istable and self.name not in ("DocType", "DocField", "DocPerm", "Custom DocPerm"):
			custom_perms = frappe.get_all(
				"Custom DocPerm",
				fields="*",
				filters=dict(parent=self.name),
				update=dict(doctype="Custom DocPerm"),
			)
			if custom_perms:
				self.permissions = [Document(d) for d in custom_perms]

	def get_fieldnames_with_value(self, with_field_meta=False, with_virtual_fields=False):
		def is_value_field(docfield):
			return not (
				not with_virtual_fields and docfield.get("is_virtual") or docfield.fieldtype in no_value_fields
			)

		if with_field_meta:
			return [df for df in self.fields if is_value_field(df)]

		return [df.fieldname for df in self.fields if is_value_field(df)]

	def get_fields_to_check_permissions(self, user_permission_doctypes):
		fields = self.get(
			"fields",
			{
				"fieldtype": "Link",
				"parent": self.name,
				"ignore_user_permissions": ("!=", 1),
				"options": ("in", user_permission_doctypes),
			},
		)

		if self.name in user_permission_doctypes:
			fields.append(frappe._dict({"label": "Name", "fieldname": "name", "options": self.name}))

		return fields

	def get_high_permlevel_fields(self):
		"""Build list of fields with high perm level and all the higher perm levels defined."""
		if not hasattr(self, "high_permlevel_fields"):
			self.high_permlevel_fields = []
			for df in self.fields:
				if df.permlevel > 0:
					self.high_permlevel_fields.append(df)

		return self.high_permlevel_fields

	def get_permitted_fieldnames(self, parenttype=None, *, user=None, permission_type="read"):
		"""Build list of `fieldname` with read perm level and all the higher perm levels defined.

		Note: If permissions are not defined for DocType, return all the fields with value.
		"""
		permitted_fieldnames = []

		if self.istable and not parenttype:
			return permitted_fieldnames

		if not permission_type:
			permission_type = "select" if frappe.only_has_select_perm(self.name, user=user) else "read"

		if permission_type == "select":
			return self.get_search_fields()

		if not self.get_permissions(parenttype=parenttype):
			return self.get_fieldnames_with_value()

		permlevel_access = set(
			self.get_permlevel_access(permission_type=permission_type, parenttype=parenttype, user=user)
		)

		for df in self.get_fieldnames_with_value(with_field_meta=True, with_virtual_fields=True):
			if df.permlevel in permlevel_access:
				permitted_fieldnames.append(df.fieldname)

		return permitted_fieldnames

	def get_permlevel_access(self, permission_type="read", parenttype=None, *, user=None):
		has_access_to = []
		roles = frappe.get_roles(user)
		for perm in self.get_permissions(parenttype):
			if perm.role in roles and perm.get(permission_type):
				if perm.permlevel not in has_access_to:
					has_access_to.append(perm.permlevel)

		return has_access_to

	def get_permissions(self, parenttype=None):
		if self.istable and parenttype:
			# use parent permissions
			permissions = frappe.get_meta(parenttype).permissions
		else:
			permissions = self.get("permissions", [])

		return permissions

	def get_dashboard_data(self):
		"""Returns dashboard setup related to this doctype.

		This method will return the `data` property in the `[doctype]_dashboard.py`
		file in the doctype's folder, along with any overrides or extensions
		implemented in other Frappe applications via hooks.
		"""
		data = frappe._dict()
		if not self.custom:
			try:
				module = load_doctype_module(self.name, suffix="_dashboard")
				if hasattr(module, "get_data"):
					data = frappe._dict(module.get_data())
			except ImportError:
				pass

		self.add_doctype_links(data)

		if not self.custom:
			for hook in frappe.get_hooks("override_doctype_dashboards", {}).get(self.name, []):
				data = frappe._dict(frappe.get_attr(hook)(data=data))

		return data

	def add_doctype_links(self, data):
		"""add `links` child table in standard link dashboard format"""
		dashboard_links = []

		if getattr(self, "links", None):
			dashboard_links.extend(self.links)

		if not data.transactions:
			# init groups
			data.transactions = []

		if not data.non_standard_fieldnames:
			data.non_standard_fieldnames = {}

		if not data.internal_links:
			data.internal_links = {}

		for link in dashboard_links:
			link.added = False
			if link.hidden:
				continue

			for group in data.transactions:
				group = frappe._dict(group)

				# For internal links parent doctype will be the key
				doctype = link.parent_doctype or link.link_doctype
				# group found
				if link.group and _(group.label) == _(link.group):
					if doctype not in group.get("items"):
						group.get("items").append(doctype)
					link.added = True

			if not link.added:
				# group not found, make a new group
				data.transactions.append(
					dict(label=link.group, items=[link.parent_doctype or link.link_doctype])
				)

			if not link.is_child_table:
				if link.link_fieldname != data.fieldname:
					if data.fieldname:
						data.non_standard_fieldnames[link.link_doctype] = link.link_fieldname
					else:
						data.fieldname = link.link_fieldname
			elif link.is_child_table:
				if not data.fieldname:
					data.fieldname = link.link_fieldname
				data.internal_links[link.parent_doctype] = [link.table_fieldname, link.link_fieldname]

	def get_row_template(self):
		return self.get_web_template(suffix="_row")

	def get_list_template(self):
		return self.get_web_template(suffix="_list")

	def get_web_template(self, suffix=""):
		"""Returns the relative path of the row template for this doctype"""
		module_name = frappe.scrub(self.module)
		doctype = frappe.scrub(self.name)
		template_path = frappe.get_module_path(
			module_name, "doctype", doctype, "templates", doctype + suffix + ".html"
		)
		if os.path.exists(template_path):
			return "{module_name}/doctype/{doctype_name}/templates/{doctype_name}{suffix}.html".format(
				module_name=module_name, doctype_name=doctype, suffix=suffix
			)
		return None

	def is_nested_set(self):
		return self.has_field("lft") and self.has_field("rgt")


#######


def is_single(doctype):
	try:
		return frappe.db.get_value("DocType", doctype, "issingle")
	except IndexError:
		raise Exception("Cannot determine whether %s is single" % doctype)


def get_parent_dt(dt):
	if not frappe.is_table(dt):
		return ""

	return (
		frappe.db.get_value(
			"DocField",
			{"fieldtype": ("in", frappe.model.table_fields), "options": dt},
			"parent",
		)
		or ""
	)


def set_fieldname(field_id, fieldname):
	frappe.db.set_value("DocField", field_id, "fieldname", fieldname)


def get_field_currency(df, doc=None):
	"""get currency based on DocField options and fieldvalue in doc"""
	currency = None

	if not df.get("options"):
		return None

	if not doc:
		return None

	if not getattr(frappe.local, "field_currency", None):
		frappe.local.field_currency = frappe._dict()

	if not (
		frappe.local.field_currency.get((doc.doctype, doc.name), {}).get(df.fieldname)
		or (
			doc.get("parent")
			and frappe.local.field_currency.get((doc.doctype, doc.parent), {}).get(df.fieldname)
		)
	):

		ref_docname = doc.get("parent") or doc.name

		if ":" in cstr(df.get("options")):
			split_opts = df.get("options").split(":")
			if len(split_opts) == 3 and doc.get(split_opts[1]):
				currency = frappe.get_cached_value(split_opts[0], doc.get(split_opts[1]), split_opts[2])
		else:
			currency = doc.get(df.get("options"))
			if doc.get("parenttype"):
				if currency:
					ref_docname = doc.name
				else:
					if frappe.get_meta(doc.parenttype).has_field(df.get("options")):
						# only get_value if parent has currency field
						currency = frappe.db.get_value(doc.parenttype, doc.parent, df.get("options"))

		if currency:
			frappe.local.field_currency.setdefault((doc.doctype, ref_docname), frappe._dict()).setdefault(
				df.fieldname, currency
			)

	return frappe.local.field_currency.get((doc.doctype, doc.name), {}).get(df.fieldname) or (
		doc.get("parent")
		and frappe.local.field_currency.get((doc.doctype, doc.parent), {}).get(df.fieldname)
	)


def get_field_precision(df, doc=None, currency=None):
	"""get precision based on DocField options and fieldvalue in doc"""
	from frappe.utils import get_number_format_info

	if df.precision:
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
	if fieldname in (default_fields + child_table_fields):
		if fieldname in ("creation", "modified"):
			return frappe._dict(fieldname=fieldname, fieldtype="Datetime")

		elif fieldname in ("idx", "docstatus"):
			return frappe._dict(fieldname=fieldname, fieldtype="Int")

		return frappe._dict(fieldname=fieldname, fieldtype="Data")


def trim_tables(doctype=None, dry_run=False, quiet=False):
	"""
	Removes database fields that don't exist in the doctype (json or custom field). This may be needed
	as maintenance since removing a field in a DocType doesn't automatically
	delete the db field.
	"""
	UPDATED_TABLES = {}
	filters = {"issingle": 0, "is_virtual": 0}
	if doctype:
		filters["name"] = doctype

	for doctype in frappe.get_all("DocType", filters=filters, pluck="name"):
		try:
			dropped_columns = trim_table(doctype, dry_run=dry_run)
			if dropped_columns:
				UPDATED_TABLES[doctype] = dropped_columns
		except frappe.db.TableMissingError:
			if quiet:
				continue
			click.secho(f"Ignoring missing table for DocType: {doctype}", fg="yellow", err=True)
			click.secho(
				f"Consider removing record in the DocType table for {doctype}", fg="yellow", err=True
			)
		except Exception as e:
			if quiet:
				continue
			click.echo(e, err=True)

	return UPDATED_TABLES


def trim_table(doctype, dry_run=True):
	frappe.cache().hdel("table_columns", f"tab{doctype}")
	ignore_fields = default_fields + optional_fields + child_table_fields
	columns = frappe.db.get_table_columns(doctype)
	fields = frappe.get_meta(doctype, cached=False).get_fieldnames_with_value()

	def is_internal(field):
		return field not in ignore_fields and not field.startswith("_")

	columns_to_remove = [f for f in list(set(columns) - set(fields)) if is_internal(f)]
	DROPPED_COLUMNS = columns_to_remove[:]

	if columns_to_remove and not dry_run:
		columns_to_remove = ", ".join(f"DROP `{c}`" for c in columns_to_remove)
		frappe.db.sql_ddl(f"ALTER TABLE `tab{doctype}` {columns_to_remove}")

	return DROPPED_COLUMNS


def _update_field_order_based_on_insert_after(field_order, insert_after_map):
	"""Update the field order based on insert_after_map"""

	retry_field_insertion = True

	while retry_field_insertion:
		retry_field_insertion = False

		for fieldname in list(insert_after_map):
			if fieldname not in field_order:
				continue

			custom_field_index = field_order.index(fieldname)
			for custom_field_name in insert_after_map.pop(fieldname):
				custom_field_index += 1
				field_order.insert(custom_field_index, custom_field_name)

			retry_field_insertion = True

	if insert_after_map:
		# insert_after is an invalid fieldname, add these fields to the end
		for fields in insert_after_map.values():
			field_order.extend(fields)
