# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import hashlib
import json
import time
import weakref
from collections.abc import Generator, Iterable
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional, TypeVar

from werkzeug.exceptions import NotFound

import frappe
from frappe import _, _dict, is_whitelisted, msgprint
from frappe.core.doctype.file.utils import relink_mismatched_files
from frappe.core.doctype.server_script.server_script_utils import run_server_script_for_doc_event
from frappe.desk.form.document_follow import follow_document
from frappe.integrations.doctype.webhook import run_webhooks
from frappe.model import (
	child_table_fields,
	datetime_fields,
	default_fields,
	display_fieldtypes,
	float_like_fields,
	get_permitted_fields,
	optional_fields,
	table_fields,
)
from frappe.model.docstatus import DocStatus
from frappe.model.naming import set_new_name, validate_name
from frappe.model.utils import is_virtual_doctype
from frappe.model.utils.link_count import notify_link_count
from frappe.model.workflow import set_workflow_state_on_action, validate_workflow
from frappe.modules import load_doctype_module
from frappe.types import DF
from frappe.utils import (
	cast_fieldtype,
	cint,
	compare,
	cstr,
	date_diff,
	file_lock,
	flt,
	is_a_property,
	now,
	sanitize_html,
	strip_html,
)
from frappe.utils.data import get_absolute_url, get_datetime, get_timedelta, getdate
from frappe.utils.defaults import get_not_null_defaults
from frappe.utils.global_search import update_global_search
from frappe.utils.html_utils import unescape_html

if TYPE_CHECKING:
	from frappe.core.doctype.docfield.docfield import DocField


D = TypeVar("D", bound="Document")

DOCUMENT_LOCK_EXPIRTY = 12 * 60 * 60  # All locks expire in 12 hours automatically
DOCUMENT_LOCK_SOFT_EXPIRY = 60 * 60  # Let users force-unlock after 60 minutes

max_positive_value = {"smallint": 2**15 - 1, "int": 2**31 - 1, "bigint": 2**63 - 1}


DOCTYPE_TABLE_FIELDS = [
	_dict(fieldname="fields", options="DocField"),
	_dict(fieldname="permissions", options="DocPerm"),
	_dict(fieldname="actions", options="DocType Action"),
	_dict(fieldname="links", options="DocType Link"),
	_dict(fieldname="states", options="DocType State"),
]

TABLE_DOCTYPES_FOR_DOCTYPE = {df["fieldname"]: df["options"] for df in DOCTYPE_TABLE_FIELDS}
DOCTYPES_FOR_DOCTYPE = {"DocType", *TABLE_DOCTYPES_FOR_DOCTYPE.values()}


def get_doc(*args, **kwargs):
	"""Return a `frappe.model.Document` object.

	:param arg1: Document dict or DocType name.
	:param arg2: [optional] document name.
	:param for_update: [optional] select document for update.

	There are multiple ways to call `get_doc`

	        # will fetch the latest user object (with child table) from the database
	        user = get_doc("User", "test@example.com")

	        # create a new object
	        user = get_doc({
	                "doctype":"User"
	                "email_id": "test@example.com",
	                "roles: [
	                        {"role": "System Manager"}
	                ]
	        })

	        # create new object with keyword arguments
	        user = get_doc(doctype='User', email_id='test@example.com')

	        # select a document for update
	        user = get_doc("User", "test@example.com", for_update=True)
	"""
	if args:
		if isinstance(args[0], Document):
			# already a document
			return args[0]
		elif isinstance(args[0], str):
			doctype = args[0]

		elif isinstance(args[0], dict):
			# passed a dict
			kwargs = args[0]

		else:
			raise ValueError("First non keyword argument must be a string or dict")

	if len(args) < 2 and kwargs:
		if "doctype" in kwargs:
			doctype = kwargs["doctype"]
		else:
			raise ValueError('"doctype" is a required key')

	controller = get_controller(doctype)
	if controller:
		return controller(*args, **kwargs)

	raise ImportError(doctype)


def get_controller(doctype):
	"""Return the locally cached **class** object of the given DocType.

	For `custom` type, return `frappe.model.document.Document`.

	:param doctype: DocType name as string.
	"""

	if frappe.local.dev_server or frappe.flags.in_migrate:
		return import_controller(doctype)

	site_controllers = frappe.controllers.setdefault(frappe.local.site, {})
	if doctype not in site_controllers:
		site_controllers[doctype] = import_controller(doctype)

	return site_controllers[doctype]


def import_controller(doctype):
	from frappe.model.document import Document
	from frappe.utils.nestedset import NestedSet

	module_name = "Core"
	if doctype not in DOCTYPES_FOR_DOCTYPE:
		doctype_info = frappe.db.get_value("DocType", doctype, fieldname="*")
		if doctype_info:
			if doctype_info.custom:
				return NestedSet if doctype_info.is_tree else Document
			module_name = doctype_info.module

	module_path = None
	class_overrides = frappe.get_hooks("override_doctype_class")
	if class_overrides and class_overrides.get(doctype):
		import_path = class_overrides[doctype][-1]
		module_path, classname = import_path.rsplit(".", 1)
		module = frappe.get_module(module_path)

	else:
		module = load_doctype_module(doctype, module_name)
		classname = doctype.replace(" ", "").replace("-", "")

	class_ = getattr(module, classname, None)
	if class_ is None:
		raise ImportError(
			doctype
			if module_path is None
			else f"{doctype}: {classname} does not exist in module {module_path}"
		)

	if not issubclass(class_, Document):
		raise ImportError(f"{doctype}: {classname} is not a subclass of Document")

	return class_


class BaseDocument:
	def __init__(self, d):
		if d.get("doctype"):
			self.doctype = d["doctype"]

		self._table_fieldnames = {df.fieldname for df in self._get_table_fields()}
		self.update(d)
		self.dont_update_if_missing = []

		if hasattr(self, "__setup__"):
			self.__setup__()


class Document(BaseDocument):
	"""All controllers inherit from `Document`."""

	doctype: DF.Data
	name: DF.Data | None
	flags: frappe._dict[str, Any]
	owner: DF.Link
	creation: DF.Datetime
	modified: DF.Datetime
	modified_by: DF.Link
	idx: DF.Int

	_reserved_keywords = frozenset(
		(
			"doctype",
			"meta",
			"flags",
			"parent_doc",
			"_table_fields",
			"_valid_columns",
			"_doc_before_save",
			"_table_fieldnames",
			"_reserved_keywords",
			"permitted_fieldnames",
			"dont_update_if_missing",
		)
	)

	def __init__(self, *args, **kwargs):
		"""Constructor.

		:param arg1: DocType name as string or document **dict**
		:param arg2: Document name, if `arg1` is DocType name.

		If DocType name and document name are passed, the object will load
		all values (including child documents) from the database.
		"""
		self.doctype = None
		self.name = None
		self.flags = frappe._dict()

		if args and args[0]:
			if isinstance(args[0], str):
				# first arugment is doctype
				self.doctype = args[0]

				# doctype for singles, string value or filters for other documents
				self.name = self.doctype if len(args) == 1 else args[1]

				# for_update is set in flags to avoid changing load_from_db signature
				# since it is used in virtual doctypes and inherited in child classes
				self.flags.for_update = kwargs.get("for_update")
				self.load_from_db()
				return

			if isinstance(args[0], dict):
				# first argument is a dict
				kwargs = args[0]

		if kwargs:
			# init base document
			super().__init__(kwargs)
			self.init_child_tables()
			self.init_valid_columns()

		else:
			# incorrect arguments. let's not proceed.
			raise ValueError("Illegal arguments")

	@cached_property
	def meta(self):
		return frappe.get_meta(self.doctype)

	@cached_property
	def permitted_fieldnames(self):
		return get_permitted_fields(doctype=self.doctype, parenttype=getattr(self, "parenttype", None))

	def __getstate__(self):
		"""Return a copy of `__dict__` excluding unpicklable values like `meta`.

		Called when pickling.
		More info: https://docs.python.org/3/library/pickle.html#handling-stateful-objects
		"""

		# Always use the dict.copy() method to avoid modifying the original state
		state = self.__dict__.copy()
		self.remove_unpicklable_values(state)

		return state

	def remove_unpicklable_values(self, state):
		"""Remove unpicklable values before pickling"""

		state.pop("meta", None)
		state.pop("permitted_fieldnames", None)
		state.pop("_parent_doc", None)

	def update(self, d):
		"""Update multiple fields of a doctype using a dictionary of key-value pairs.

		Example:
		        doc.update({
		                "user": "admin",
		                "balance": 42000
		        })
		"""

		# set name first, as it is used a reference in child document
		if "name" in d:
			self.name = d["name"]

		ignore_children = hasattr(self, "flags") and self.flags.ignore_children
		for key, value in d.items():
			self.set(key, value, as_value=ignore_children)

		return self

	def update_if_missing(self, d):
		"""Set default values for fields without existing values"""
		if isinstance(d, Document):
			d = d.get_valid_dict()

		for key, value in d.items():
			if (
				value is not None
				and self.get(key) is None
				# dont_update_if_missing is a list of fieldnames
				# for which you don't want to set default value
				and key not in self.dont_update_if_missing
			):
				self.set(key, value)

	def get_db_value(self, key):
		return frappe.db.get_value(self.doctype, self.name, key)

	def get(self, key, filters=None, limit=None, default=None):
		if isinstance(key, dict):
			return _filter(self.get_all_children(), key, limit=limit)

		if filters:
			if isinstance(filters, dict):
				return _filter(self.__dict__.get(key, []), filters, limit=limit)

			# perhaps you wanted to set a default instead
			default = filters

		value = self.__dict__.get(key, default)

		if limit and isinstance(value, list | tuple) and len(value) > limit:
			value = value[:limit]

		return value

	def getone(self, key, filters=None):
		return self.get(key, filters=filters, limit=1)[0]

	def set(self, key, value, as_value=False):
		if key in self._reserved_keywords:
			return

		if not as_value and key in self._table_fieldnames:
			self.__dict__[key] = []

			# if value is falsy, just init to an empty list
			if value:
				self.extend(key, value)

			return

		self.__dict__[key] = value

	def delete_key(self, key):
		if key in self.__dict__:
			del self.__dict__[key]

	def append(self, key: str, value: D | dict | None = None) -> D:
		"""Append an item to a child table.

		Example:
		        doc.append("childtable", {
		                "child_table_field": "value",
		                "child_table_int_field": 0,
		                ...
		        })
		"""
		if value is None:
			value = {}

		if (table := self.__dict__.get(key)) is None:
			self.__dict__[key] = table = []

		ret_value = self._init_child(value, key)
		table.append(ret_value)

		# reference parent document but with weak reference, parent_doc will be deleted if self is garbage collected.
		ret_value.parent_doc = weakref.ref(self)

		return ret_value

	@property
	def parent_doc(self):
		parent_doc_ref = getattr(self, "_parent_doc", None)

		if isinstance(parent_doc_ref, Document):
			return parent_doc_ref
		elif isinstance(parent_doc_ref, weakref.ReferenceType):
			return parent_doc_ref()

	@parent_doc.setter
	def parent_doc(self, value):
		self._parent_doc = value

	@parent_doc.deleter
	def parent_doc(self):
		self._parent_doc = None

	def extend(self, key, value):
		try:
			value = iter(value)
		except TypeError:
			raise ValueError

		for v in value:
			self.append(key, v)

	def remove(self, doc):
		# Usage: from the parent doc, pass the child table doc
		# to remove that child doc from the child table, thus removing it from the parent doc
		if doc.get("parentfield"):
			self.get(doc.parentfield).remove(doc)

	def _init_child(self, value, key):
		if not isinstance(value, Document):
			if not (doctype := self.get_table_field_doctype(key)):
				raise AttributeError(key)

			value["doctype"] = doctype
			value = get_controller(doctype)(value)

		value.parent = self.name
		value.parenttype = self.doctype
		value.parentfield = key

		if value.docstatus is None:
			value.docstatus = DocStatus.draft()

		if not getattr(value, "idx", None):
			if table := getattr(self, key, None):
				value.idx = len(table) + 1
			else:
				value.idx = 1

		if not getattr(value, "name", None):
			value.__dict__["__islocal"] = 1

		return value

	def _get_table_fields(self):
		"""
		To get table fields during Document init
		Meta.get_table_fields goes into recursion for special doctypes
		"""

		if self.doctype == "DocType":
			return DOCTYPE_TABLE_FIELDS

		# child tables don't have child tables
		if self.doctype in DOCTYPES_FOR_DOCTYPE:
			return ()

		return self.meta.get_table_fields()

	def get_valid_dict(
		self, sanitize=True, convert_dates_to_str=False, ignore_nulls=False, ignore_virtual=False
	) -> _dict:
		d = _dict()
		field_values = self.__dict__

		for fieldname in self.meta.get_valid_columns():
			value = field_values.get(fieldname)

			# if no need for sanitization and value is None, continue
			if not sanitize and value is None:
				d[fieldname] = None
				continue

			df = self.meta.get_field(fieldname)
			is_virtual_field = getattr(df, "is_virtual", False)

			if df:
				if is_virtual_field:
					if ignore_virtual or fieldname not in self.permitted_fieldnames:
						continue

					if (prop := getattr(type(self), fieldname, None)) and is_a_property(prop):
						value = getattr(self, fieldname)

					elif options := getattr(df, "options", None):
						from frappe.utils.safe_exec import get_safe_globals

						value = frappe.safe_eval(
							code=options,
							eval_globals=get_safe_globals(),
							eval_locals={"doc": self},
						)

				if isinstance(value, list) and df.fieldtype not in table_fields:
					frappe.throw(_("Value for {0} cannot be a list").format(_(df.label, context=df.parent)))

				if df.fieldtype == "Check":
					value = 1 if cint(value) else 0

				elif df.fieldtype == "Int" and not isinstance(value, int):
					value = cint(value)

				elif df.fieldtype == "JSON" and isinstance(value, dict):
					value = json.dumps(value, sort_keys=True, indent=4, separators=(",", ": "))

				elif df.fieldtype in float_like_fields and not isinstance(value, float):
					value = flt(value)

				elif (df.fieldtype in datetime_fields and value == "") or (
					getattr(df, "unique", False) and cstr(value).strip() == ""
				):
					value = None

			if convert_dates_to_str and isinstance(
				value, datetime.datetime | datetime.date | datetime.time | datetime.timedelta
			):
				value = str(value)

			if ignore_nulls and not is_virtual_field and value is None:
				continue

			# If the docfield is not nullable - set a default non-null value
			if value is None and getattr(df, "not_nullable", False):
				if df.default:
					value = df.default
				else:
					value = get_not_null_defaults(df.fieldtype)

			d[fieldname] = value

		return d

	def init_child_tables(self):
		"""
		This is needed so that one can loop over child table properties
		without worrying about whether or not they have values
		"""

		for fieldname in self._table_fieldnames:
			if self.__dict__.get(fieldname) is None:
				self.__dict__[fieldname] = []

	def init_valid_columns(self):
		for key in default_fields:
			if key not in self.__dict__:
				self.__dict__[key] = None

			if self.__dict__[key] is None:
				if key == "docstatus":
					self.docstatus = DocStatus.draft()
				elif key == "idx":
					self.__dict__[key] = 0

		for key in self.get_valid_columns():
			if key not in self.__dict__:
				self.__dict__[key] = None

	def get_valid_columns(self) -> list[str]:
		if self.doctype not in frappe.local.valid_columns:
			if self.doctype in DOCTYPES_FOR_DOCTYPE:
				from frappe.model.meta import get_table_columns

				valid = get_table_columns(self.doctype)
			else:
				valid = self.meta.get_valid_columns()

			frappe.local.valid_columns[self.doctype] = valid

		return frappe.local.valid_columns[self.doctype]

	def is_new(self) -> bool:
		return self.get("__islocal")

	@property
	def docstatus(self):
		return DocStatus(cint(self.get("docstatus")))

	@docstatus.setter
	def docstatus(self, value):
		self.__dict__["docstatus"] = DocStatus(cint(value))

	def as_dict(
		self,
		no_nulls=False,
		no_default_fields=False,
		convert_dates_to_str=False,
		no_child_table_fields=False,
	) -> dict:
		doc = self.get_valid_dict(convert_dates_to_str=convert_dates_to_str, ignore_nulls=no_nulls)
		doc["doctype"] = self.doctype

		for fieldname in self._table_fieldnames:
			children = self.get(fieldname) or []
			doc[fieldname] = [
				d.as_dict(
					convert_dates_to_str=convert_dates_to_str,
					no_nulls=no_nulls,
					no_default_fields=no_default_fields,
					no_child_table_fields=no_child_table_fields,
				)
				for d in children
			]

		if no_default_fields:
			for key in default_fields:
				if key in doc:
					del doc[key]

		if no_child_table_fields:
			for key in child_table_fields:
				if key in doc:
					del doc[key]

		for key in (
			"_user_tags",
			"__islocal",
			"__onload",
			"_liked_by",
			"__run_link_triggers",
			"__unsaved",
		):
			if value := getattr(self, key, None):
				doc[key] = value

		return doc

	def as_json(self):
		return frappe.as_json(self.as_dict())

	def get_table_field_doctype(self, fieldname):
		try:
			return self.meta.get_field(fieldname).options
		except AttributeError:
			if self.doctype == "DocType" and (table_doctype := TABLE_DOCTYPES_FOR_DOCTYPE.get(fieldname)):
				return table_doctype

			raise

	def get_parentfield_of_doctype(self, doctype):
		fieldname = [df.fieldname for df in self.meta.get_table_fields() if df.options == doctype]
		return fieldname[0] if fieldname else None

	def db_insert(self, ignore_if_duplicate=False):
		"""INSERT the document (with valid columns) in the database.

		args:
		        ignore_if_duplicate: ignore primary key collision
		                                        at database level (postgres)
		                                        in python (mariadb)
		"""
		if not self.name:
			# name will be set by document class in most cases
			set_new_name(self)

		conflict_handler = ""
		# On postgres we can't implcitly ignore PK collision
		# So instruct pg to ignore `name` field conflicts
		if ignore_if_duplicate and frappe.db.db_type == "postgres":
			conflict_handler = "on conflict (name) do nothing"

		if not self.creation:
			self.creation = self.modified = now()
			self.created_by = self.modified_by = frappe.session.user

		# if doctype is "DocType", don't insert null values as we don't know who is valid yet
		d = self.get_valid_dict(
			convert_dates_to_str=True,
			ignore_nulls=self.doctype in DOCTYPES_FOR_DOCTYPE,
			ignore_virtual=True,
		)

		columns = list(d)
		try:
			frappe.db.sql(
				"""INSERT INTO `tab{doctype}` ({columns})
					VALUES ({values}) {conflict_handler}""".format(
					doctype=self.doctype,
					columns=", ".join("`" + c + "`" for c in columns),
					values=", ".join(["%s"] * len(columns)),
					conflict_handler=conflict_handler,
				),
				list(d.values()),
			)
		except Exception as e:
			if frappe.db.is_primary_key_violation(e):
				if self.meta.autoname == "hash":
					# hash collision? try again
					frappe.flags.retry_count = (frappe.flags.retry_count or 0) + 1
					if frappe.flags.retry_count > 5 and not frappe.flags.in_test:
						raise
					self.name = None
					self.db_insert()
					return

				if not ignore_if_duplicate:
					frappe.msgprint(
						_("{0} {1} already exists").format(_(self.doctype), frappe.bold(self.name)),
						title=_("Duplicate Name"),
						indicator="red",
					)
					raise frappe.DuplicateEntryError(self.doctype, self.name, e)

			elif frappe.db.is_unique_key_violation(e):
				# unique constraint
				self.show_unique_validation_message(e)

			else:
				raise

		self.set("__islocal", False)

	def db_update(self):
		if self.get("__islocal") or not self.name:
			self.db_insert()
			return

		d = self.get_valid_dict(
			convert_dates_to_str=True,
			ignore_nulls=self.doctype in DOCTYPES_FOR_DOCTYPE,
			ignore_virtual=True,
		)

		# don't update name, as case might've been changed
		name = cstr(d["name"])
		del d["name"]

		columns = list(d)

		try:
			frappe.db.sql(
				"""UPDATE `tab{doctype}`
				SET {values} WHERE `name`=%s""".format(
					doctype=self.doctype, values=", ".join("`" + c + "`=%s" for c in columns)
				),
				[*list(d.values()), name],
			)
		except Exception as e:
			if frappe.db.is_unique_key_violation(e):
				self.show_unique_validation_message(e)
			else:
				raise

	def db_update_all(self):
		"""Raw update parent + children
		DOES NOT VALIDATE AND CALL TRIGGERS"""
		self.db_update()
		for fieldname in self._table_fieldnames:
			for doc in self.get(fieldname):
				doc.db_update()

	def show_unique_validation_message(self, e):
		if frappe.db.db_type != "postgres":
			fieldname = str(e).split("'")[-2]
			label = None

			# MariaDB gives key_name in error. Extracting fieldname from key name
			try:
				fieldname = self.get_field_name_by_key_name(fieldname)
			except IndexError:
				pass

			label = self.get_label_from_fieldname(fieldname)

			frappe.msgprint(_("{0} must be unique").format(label or fieldname))

		# this is used to preserve traceback
		raise frappe.UniqueValidationError(self.doctype, self.name, e)

	def get_field_name_by_key_name(self, key_name):
		"""MariaDB stores a mapping between `key_name` and `column_name`.
		Return the `column_name` associated with the `key_name` passed.

		Args:
		        key_name (str): The name of the database index.

		Raises:
		        IndexError: If the key is not found in the table.

		Return:
		        str: The column name associated with the key.
		"""
		return frappe.db.sql(
			f"""
			SHOW
				INDEX
			FROM
				`tab{self.doctype}`
			WHERE
				key_name=%s
			AND
				Non_unique=0
			""",
			key_name,
			as_dict=True,
		)[0].get("Column_name")

	def get_label_from_fieldname(self, fieldname):
		"""Return the associated label for fieldname.

		Args:
		        fieldname (str): The fieldname in the DocType to use to pull the label.

		Return:
		        str: The label associated with the fieldname, if found, otherwise `None`.
		"""
		df = self.meta.get_field(fieldname)
		if df:
			return df.label

	def update_modified(self):
		"""Update modified timestamp"""
		self.set("modified", now())
		if getattr(self.meta, "issingle", False):
			frappe.db.set_single_value(self.doctype, "modified", self.modified, update_modified=False)
		else:
			frappe.db.set_value(self.doctype, self.name, "modified", self.modified, update_modified=False)

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
			self.docstatus = DocStatus(cint(self.docstatus))

	def _get_missing_mandatory_fields(self):
		"""Get mandatory fields that do not have any values"""

		def get_msg(df):
			if df.fieldtype in table_fields:
				return "{}: {}: {}".format(
					_("Error"), _("Data missing in table"), _(df.label, context=df.parent)
				)

			# check if parentfield exists (only applicable for child table doctype)
			elif self.get("parentfield"):
				return "{}: {} {} #{}: {}: {}".format(
					_("Error"),
					frappe.bold(_(self.doctype)),
					_("Row"),
					self.idx,
					_("Value missing for"),
					_(df.label, context=df.parent),
				)

			return _("Error: Value missing for {0}: {1}").format(_(df.parent), _(df.label, context=df.parent))

		def has_content(df):
			value = cstr(self.get(df.fieldname))
			has_text_content = strip_html(value).strip()
			has_img_tag = "<img" in value
			has_text_or_img_tag = has_text_content or has_img_tag

			if df.fieldtype == "Text Editor" and has_text_or_img_tag:
				return True
			elif df.fieldtype == "Code" and df.options == "HTML" and has_text_or_img_tag:
				return True
			else:
				return has_text_content

		missing = []

		for df in self.meta.get("fields", {"reqd": ("=", 1)}):
			if self.get(df.fieldname) in (None, []) or not has_content(df):
				missing.append((df.fieldname, get_msg(df)))

		# check for missing parent and parenttype
		if self.meta.istable:
			for fieldname in ("parent", "parenttype"):
				if not self.get(fieldname):
					missing.append((fieldname, get_msg(_dict(label=fieldname))))

		return missing

	def get_invalid_links(self, is_submittable=False):
		"""Return list of invalid links and also update fetch values if not set."""

		def get_msg(df, docname):
			# check if parentfield exists (only applicable for child table doctype)
			if self.get("parentfield"):
				return "{} #{}: {}: {}".format(_("Row"), self.idx, _(df.label, context=df.parent), docname)

			return f"{_(df.label, context=df.parent)}: {docname}"

		invalid_links = []
		cancelled_links = []

		for df in self.meta.get_link_fields() + self.meta.get("fields", {"fieldtype": ("=", "Dynamic Link")}):
			docname = self.get(df.fieldname)

			if docname:
				if df.fieldtype == "Link":
					doctype = df.options
					if not doctype:
						frappe.throw(_("Options not set for link field {0}").format(df.fieldname))
				else:
					doctype = self.get(df.options)
					if not doctype:
						frappe.throw(_("{0} must be set first").format(self.meta.get_label(df.options)))

				# MySQL is case insensitive. Preserve case of the original docname in the Link Field.

				# get a map of values ot fetch along with this link query
				# that are mapped as link_fieldname.source_fieldname in Options of
				# Readonly or Data or Text type fields

				fields_to_fetch = [
					_df
					for _df in self.meta.get_fields_to_fetch(df.fieldname)
					if not _df.get("fetch_if_empty")
					or (_df.get("fetch_if_empty") and not self.get(_df.fieldname))
				]
				if not frappe.get_meta(doctype).get("is_virtual"):
					if not fields_to_fetch:
						# cache a single value type
						values = _dict(name=frappe.db.get_value(doctype, docname, "name", cache=True))
					else:
						values_to_fetch = ["name"] + [
							_df.fetch_from.split(".")[-1] for _df in fields_to_fetch
						]

						# fallback to dict with field_to_fetch=None if link field value is not found
						# (for compatibility, `values` must have same data type)
						empty_values = _dict({value: None for value in values_to_fetch})
						# don't cache if fetching other values too
						values = (
							frappe.db.get_value(doctype, docname, values_to_fetch, as_dict=True)
							or empty_values
						)

				if getattr(frappe.get_meta(doctype), "issingle", 0):
					values.name = doctype

				if frappe.get_meta(doctype).get("is_virtual"):
					values = frappe.get_doc(doctype, docname).as_dict()

				if values:
					setattr(self, df.fieldname, values.name)

					for _df in fields_to_fetch:
						if self.is_new() or not self.docstatus.is_submitted() or _df.allow_on_submit:
							self.set_fetch_from_value(doctype, _df, values)

					notify_link_count(doctype, docname)

					if not values.name:
						invalid_links.append((df.fieldname, docname, get_msg(df, docname)))

					elif (
						df.fieldname != "amended_from"
						and (is_submittable or self.meta.is_submittable)
						and frappe.get_meta(doctype).is_submittable
						and cint(frappe.db.get_value(doctype, docname, "docstatus")) == DocStatus.cancelled()
					):
						cancelled_links.append((df.fieldname, docname, get_msg(df, docname)))

		return invalid_links, cancelled_links

	def set_fetch_from_value(self, doctype, df, values):
		fetch_from_fieldname = df.fetch_from.split(".")[-1]
		value = values[fetch_from_fieldname]
		if df.fieldtype in ["Small Text", "Text", "Data"]:
			from frappe.model.meta import get_default_df

			fetch_from_df = get_default_df(fetch_from_fieldname) or frappe.get_meta(doctype).get_field(
				fetch_from_fieldname
			)

			if not fetch_from_df:
				frappe.throw(
					_('Please check the value of "Fetch From" set for field {0}').format(
						frappe.bold(df.label)
					),
					title=_("Wrong Fetch From value"),
				)

			fetch_from_ft = fetch_from_df.get("fieldtype")
			if fetch_from_ft == "Text Editor" and value:
				value = unescape_html(strip_html(value))
		setattr(self, df.fieldname, value)

	def _validate_selects(self):
		if frappe.flags.in_import:
			return

		for df in self.meta.get_select_fields():
			if df.fieldname == "naming_series" or not self.get(df.fieldname) or not df.options:
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

				frappe.throw(
					_('{0} {1} cannot be "{2}". It should be one of "{3}"').format(
						prefix, label, value, comma_options
					)
				)

	def _validate_data_fields(self):
		# data_field options defined in frappe.model.data_field_options
		for phone_field in self.meta.get_phone_fields():
			phone = self.get(phone_field.fieldname)
			frappe.utils.validate_phone_number_with_country_code(phone, phone_field.fieldname)

		for data_field in self.meta.get_data_fields():
			data = self.get(data_field.fieldname)
			data_field_options = data_field.get("options")
			old_fieldtype = data_field.get("oldfieldtype")

			if old_fieldtype and old_fieldtype != "Data":
				continue

			if data_field_options == "Email":
				if (self.owner in frappe.STANDARD_USERS) and (data in frappe.STANDARD_USERS):
					continue
				for email_address in frappe.utils.split_emails(data):
					frappe.utils.validate_email_address(email_address, throw=True)

			if data_field_options == "Name":
				frappe.utils.validate_name(data, throw=True)

			if data_field_options == "Phone":
				frappe.utils.validate_phone_number(data, throw=True)

			if data_field_options == "URL":
				if not data:
					continue

				frappe.utils.validate_url(data, throw=True)

	def _validate_constants(self):
		if frappe.flags.in_import or self.is_new() or self.flags.ignore_validate_constants:
			return

		constants = [d.fieldname for d in self.meta.get("fields", {"set_only_once": ("=", 1)})]
		if constants:
			values = frappe.db.get_value(self.doctype, self.name, constants, as_dict=True)

		for fieldname in constants:
			df = self.meta.get_field(fieldname)

			# This conversion to string only when fieldtype is Date
			if df.fieldtype == "Date" or df.fieldtype == "Datetime":
				value = str(values.get(fieldname))

			else:
				value = values.get(fieldname)

			if self.get(fieldname) != value:
				frappe.throw(
					_("Value cannot be changed for {0}").format(self.meta.get_label(fieldname)),
					frappe.CannotChangeConstantError,
				)

	def _validate_length(self):
		if frappe.flags.in_install:
			return

		if getattr(self.meta, "issingle", 0):
			# single doctype value type is mediumtext
			return

		type_map = frappe.db.type_map

		for fieldname, value in self.get_valid_dict(ignore_virtual=True).items():
			df = self.meta.get_field(fieldname)

			if not df or df.fieldtype == "Check":
				# skip standard fields and Check fields
				continue

			column_type = type_map[df.fieldtype][0] or None

			if column_type == "varchar":
				default_column_max_length = type_map[df.fieldtype][1] or None
				max_length = cint(df.get("length")) or cint(default_column_max_length)

				if len(cstr(value)) > max_length:
					self.throw_length_exceeded_error(df, max_length, value)

			elif column_type in ("int", "bigint", "smallint"):
				max_length = max_positive_value[column_type]

				if abs(cint(value)) > max_length:
					self.throw_length_exceeded_error(df, max_length, value)

	def _validate_code_fields(self):
		for field in self.meta.get_code_fields():
			code_string = self.get(field.fieldname)
			language = field.get("options")

			if language == "Python":
				frappe.utils.validate_python_code(code_string, fieldname=field.label, is_expression=False)

			elif language == "PythonExpression":
				frappe.utils.validate_python_code(code_string, fieldname=field.label)

	def _sync_autoname_field(self):
		"""Keep autoname field in sync with `name`"""
		autoname = self.meta.autoname or ""
		_empty, _field_specifier, fieldname = autoname.partition("field:")

		if fieldname and self.name and self.name != self.get(fieldname):
			self.set(fieldname, self.name)

	def throw_length_exceeded_error(self, df, max_length, value):
		# check if parentfield exists (only applicable for child table doctype)
		if self.get("parentfield"):
			reference = _("{0}, Row {1}").format(_(self.doctype), self.idx)
		else:
			reference = f"{_(self.doctype)} {self.name}"

		frappe.throw(
			_("{0}: '{1}' ({3}) will get truncated, as max characters allowed is {2}").format(
				reference, _(df.label, context=df.parent), max_length, value
			),
			frappe.CharacterLengthExceededError,
			title=_("Value too big"),
		)

	def _validate_update_after_submit(self):
		# get the full doc with children
		db_values = frappe.get_doc(self.doctype, self.name).as_dict()

		for key in self.as_dict():
			df = self.meta.get_field(key)
			db_value = db_values.get(key)

			if df and not df.allow_on_submit and (self.get(key) or db_value):
				if df.fieldtype in table_fields:
					# just check if the table size has changed
					# individual fields will be checked in the loop for children
					self_value = len(self.get(key))
					db_value = len(db_value)

				else:
					self_value = self.get_value(key)
				# Postgres stores values as `datetime.time`, MariaDB as `timedelta`
				if isinstance(self_value, datetime.timedelta) and isinstance(db_value, datetime.time):
					db_value = datetime.timedelta(
						hours=db_value.hour,
						minutes=db_value.minute,
						seconds=db_value.second,
						microseconds=db_value.microsecond,
					)
				if self_value != db_value:
					frappe.throw(
						_("{0} Not allowed to change {1} after submission from {2} to {3}").format(
							f"Row #{self.idx}:" if self.get("parent") else "",
							frappe.bold(_(df.label, context=df.parent)),
							frappe.bold(db_value),
							frappe.bold(self_value),
						),
						frappe.UpdateAfterSubmitError,
						title=_("Cannot Update After Submit"),
					)

	def _sanitize_content(self):
		"""Sanitize HTML and Email in field values. Used to prevent XSS.

		- Ignore if 'Ignore XSS Filter' is checked or fieldtype is 'Code'
		"""
		from bs4 import BeautifulSoup

		if frappe.flags.in_install:
			return

		for fieldname, value in self.get_valid_dict(ignore_virtual=True).items():
			if not value or not isinstance(value, str):
				continue

			value = frappe.as_unicode(value)

			if "<" not in value and ">" not in value:
				# doesn't look like html so no need
				continue

			elif "<!-- markdown -->" in value and not bool(BeautifulSoup(value, "html.parser").find()):
				# should be handled separately via the markdown converter function
				continue

			df = self.meta.get_field(fieldname)
			sanitized_value = value

			if df and (
				df.get("ignore_xss_filter")
				or (df.get("fieldtype") in ("Data", "Small Text", "Text") and df.get("options") == "Email")
				or df.get("fieldtype") in ("Attach", "Attach Image", "Barcode", "Code")
				# cancelled and submit but not update after submit should be ignored
				or self.docstatus.is_cancelled()
				or (self.docstatus.is_submitted() and not df.get("allow_on_submit"))
			):
				continue

			else:
				sanitized_value = sanitize_html(value, linkify=df and df.fieldtype == "Text Editor")

			self.set(fieldname, sanitized_value)

	def _save_passwords(self):
		"""Save password field values in __Auth table"""
		from frappe.utils.password import remove_encrypted_password, set_encrypted_password

		if self.flags.ignore_save_passwords is True:
			return

		for df in self.meta.get("fields", {"fieldtype": ("=", "Password")}):
			if self.flags.ignore_save_passwords and df.fieldname in self.flags.ignore_save_passwords:
				continue
			new_password = self.get(df.fieldname)

			if not new_password:
				remove_encrypted_password(self.doctype, self.name, df.fieldname)

			if new_password and not self.is_dummy_password(new_password):
				# is not a dummy password like '*****'
				set_encrypted_password(self.doctype, self.name, new_password, df.fieldname)

				# set dummy password like '*****'
				self.set(df.fieldname, "*" * len(new_password))

	def get_password(self, fieldname="password", raise_exception=True):
		from frappe.utils.password import get_decrypted_password

		if self.get(fieldname) and not self.is_dummy_password(self.get(fieldname)):
			return self.get(fieldname)

		return get_decrypted_password(self.doctype, self.name, fieldname, raise_exception=raise_exception)

	def is_dummy_password(self, pwd):
		return "".join(set(pwd)) == "*"

	def precision(self, fieldname, parentfield=None) -> int | None:
		"""Return float precision for a particular field (or get global default).

		:param fieldname: Fieldname for which precision is required.
		:param parentfield: If fieldname is in child table."""
		from frappe.model.meta import get_field_precision

		if parentfield and not isinstance(parentfield, str) and parentfield.get("parentfield"):
			parentfield = parentfield.parentfield

		cache_key = parentfield or "main"

		if not hasattr(self, "_precision"):
			self._precision = _dict()

		if cache_key not in self._precision:
			self._precision[cache_key] = _dict()

		if fieldname not in self._precision[cache_key]:
			self._precision[cache_key][fieldname] = None

			doctype = self.meta.get_field(parentfield).options if parentfield else self.doctype
			df = frappe.get_meta(doctype).get_field(fieldname)

			if df.fieldtype in ("Currency", "Float", "Percent"):
				self._precision[cache_key][fieldname] = get_field_precision(df, self)

		return self._precision[cache_key][fieldname]

	def get_formatted(
		self, fieldname, doc=None, currency=None, absolute_value=False, translated=False, format=None
	):
		from frappe.utils.formatters import format_value

		df = self.meta.get_field(fieldname)
		if not df:
			from frappe.model.meta import get_default_df

			df = get_default_df(fieldname)

		if (
			df
			and df.fieldtype == "Currency"
			and not currency
			and (currency_field := df.get("options"))
			and (currency_value := self.get(currency_field))
		):
			currency = frappe.db.get_value("Currency", currency_value, cache=True)

		val = self.get(fieldname)

		if translated:
			val = _(val)

		if not doc:
			doc = getattr(self, "parent_doc", None) or self

		if (absolute_value or doc.get("absolute_value")) and isinstance(val, int | float):
			val = abs(self.get(fieldname))

		return format_value(val, df=df, doc=doc, currency=currency, format=format)

	def is_print_hide(self, fieldname, df=None, for_print=True):
		"""Return True if fieldname is to be hidden for print.

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

		print_hide = 0

		if self.get(fieldname) == 0 and not self.meta.istable:
			print_hide = (df and df.print_hide_if_no_value) or (meta_df and meta_df.print_hide_if_no_value)

		if not print_hide:
			if df and df.print_hide is not None:
				print_hide = df.print_hide
			elif meta_df:
				print_hide = meta_df.print_hide

		return print_hide

	def in_format_data(self, fieldname):
		"""Return True if shown via Print Format::`format_data` property.

		Called from within standard print format."""
		doc = getattr(self, "parent_doc", self)

		if hasattr(doc, "format_data_map"):
			return fieldname in doc.format_data_map
		else:
			return True

	def reset_values_if_no_permlevel_access(self, has_access_to, high_permlevel_fields):
		"""If the user does not have permissions at permlevel > 0, then reset the values to original / default"""
		to_reset = [
			df
			for df in high_permlevel_fields
			if (
				df.permlevel not in has_access_to
				and df.fieldtype not in display_fieldtypes
				and df.fieldname not in self.flags.get("ignore_permlevel_for_fields", [])
			)
		]

		if to_reset:
			if self.is_new():
				# if new, set default value
				ref_doc = frappe.new_doc(self.doctype)
			else:
				# get values from old doc
				if self.parent_doc:
					parent_doc = self.parent_doc.get_latest()
					child_docs = [d for d in parent_doc.get(self.parentfield) if d.name == self.name]
					if not child_docs:
						return
					ref_doc = child_docs[0]
				else:
					ref_doc = self.get_latest()

			for df in to_reset:
				self.set(df.fieldname, ref_doc.get(df.fieldname))

	def get_value(self, fieldname):
		df = self.meta.get_field(fieldname)
		val = self.get(fieldname)

		return self.cast(val, df)

	def cast(self, value, df):
		return cast_fieldtype(df.fieldtype, value, show_warning=False)

	def _extract_images_from_text_editor(self):
		from frappe.core.doctype.file.utils import extract_images_from_doc

		if self.doctype != "DocType":
			for df in self.meta.get("fields", {"fieldtype": ("=", "Text Editor")}):
				extract_images_from_doc(self, df.fieldname)

	@property
	def is_locked(self):
		return file_lock.lock_exists(self.get_signature())

	def load_from_db(self):
		"""Load document and children from database and create properties
		from fields"""
		self.flags.ignore_children = True
		if not getattr(self, "_metaclass", False) and self.meta.issingle:
			single_doc = frappe.db.get_singles_dict(self.doctype, for_update=self.flags.for_update)
			if not single_doc:
				single_doc = frappe.new_doc(self.doctype, as_dict=True)
				single_doc["name"] = self.doctype
				del single_doc["__islocal"]

			super().__init__(single_doc)
			self.init_valid_columns()
			self._fix_numeric_types()

		else:
			get_value_kwargs = {"for_update": self.flags.for_update, "as_dict": True}
			if not isinstance(self.name, dict | list):
				get_value_kwargs["order_by"] = None

			d = frappe.db.get_value(
				doctype=self.doctype, filters=self.name, fieldname="*", **get_value_kwargs
			)

			if not d:
				frappe.throw(
					_("{0} {1} not found").format(_(self.doctype), self.name), frappe.DoesNotExistError
				)

			super().__init__(d)
		self.flags.pop("ignore_children", None)

		for df in self._get_table_fields():
			# Make sure not to query the DB for a child table, if it is a virtual one.
			# During frappe is installed, the property "is_virtual" is not available in tabDocType, so
			# we need to filter those cases for the access to frappe.db.get_value() as it would crash otherwise.
			if hasattr(self, "doctype") and not hasattr(self, "module") and is_virtual_doctype(df.options):
				self.set(df.fieldname, [])
				continue

			children = (
				frappe.db.get_values(
					df.options,
					{"parent": self.name, "parenttype": self.doctype, "parentfield": df.fieldname},
					"*",
					as_dict=True,
					order_by="idx asc",
					for_update=self.flags.for_update,
				)
				or []
			)

			self.set(df.fieldname, children)

		# sometimes __setup__ can depend on child values, hence calling again at the end
		if hasattr(self, "__setup__"):
			self.__setup__()

	def reload(self):
		"""Reload document from database"""
		self.load_from_db()

	def get_latest(self):
		if not getattr(self, "_doc_before_save", None):
			self.load_doc_before_save()

		return self._doc_before_save

	def check_permission(self, permtype="read", permlevel=None):
		"""Raise `frappe.PermissionError` if not permitted"""
		if not self.has_permission(permtype):
			self.raise_no_permission_to(permtype)

	def has_permission(self, permtype="read", *, debug=False, user=None) -> bool:
		"""
		Call `frappe.permissions.has_permission` if `ignore_permissions` flag isn't truthy

		:param permtype: `read`, `write`, `submit`, `cancel`, `delete`, etc.
		"""

		if self.flags.ignore_permissions:
			return True

		import frappe.permissions

		return frappe.permissions.has_permission(self.doctype, permtype, self, debug=debug, user=user)

	def raise_no_permission_to(self, perm_type):
		"""Raise `frappe.PermissionError`."""
		frappe.flags.error_message = (
			_("Insufficient Permission for {0}").format(self.doctype) + f" ({frappe.bold(_(perm_type))})"
		)
		raise frappe.PermissionError

	def insert(
		self,
		ignore_permissions=None,
		ignore_links=None,
		ignore_if_duplicate=False,
		ignore_mandatory=None,
		set_name=None,
		set_child_names=True,
	) -> "Document":
		"""Insert the document in the database (as a new document).
		This will check for user permissions and execute `before_insert`,
		`validate`, `on_update`, `after_insert` methods if they are written.

		:param ignore_permissions: Do not check permissions if True.
		:param ignore_links: Do not check validity of links if True.
		:param ignore_if_duplicate: Do not raise error if a duplicate entry exists.
		:param ignore_mandatory: Do not check missing mandatory fields if True.
		:param set_name: Name to set for the document, if valid.
		:param set_child_names: Whether to set names for the child documents.
		"""
		if self.flags.in_print:
			return self

		self.flags.notifications_executed = []

		if ignore_permissions is not None:
			self.flags.ignore_permissions = ignore_permissions

		if ignore_links is not None:
			self.flags.ignore_links = ignore_links

		if ignore_mandatory is not None:
			self.flags.ignore_mandatory = ignore_mandatory

		self.set("__islocal", True)

		self._set_defaults()
		self.set_user_and_timestamp()
		self.set_docstatus()
		self.check_if_latest()
		self._validate_links()
		self.check_permission("create")
		self.run_method("before_insert")
		self.set_new_name(set_name=set_name, set_child_names=set_child_names)
		self.set_parent_in_children()
		self.validate_higher_perm_levels()

		self.flags.in_insert = True
		self.run_before_save_methods()
		self._validate()
		self.set_docstatus()
		self.flags.in_insert = False

		# run validate, on update etc.

		# parent
		if getattr(self.meta, "issingle", 0):
			self.update_single(self.get_valid_dict())
		else:
			self.db_insert(ignore_if_duplicate=ignore_if_duplicate)

		# children
		for d in self.get_all_children():
			d.db_insert()

		self.run_method("after_insert")
		self.flags.in_insert = True

		if self.get("amended_from"):
			self.copy_attachments_from_amended_from()

		relink_mismatched_files(self)
		self.run_post_save_methods()
		self.flags.in_insert = False

		# delete __islocal
		if hasattr(self, "__islocal"):
			delattr(self, "__islocal")

		# clear unsaved flag
		if hasattr(self, "__unsaved"):
			delattr(self, "__unsaved")

		if not (frappe.flags.in_migrate or frappe.local.flags.in_install or frappe.flags.in_setup_wizard):
			if frappe.get_cached_value("User", frappe.session.user, "follow_created_documents"):
				follow_document(self.doctype, self.name, frappe.session.user)
		return self

	def check_if_locked(self):
		if self.creation and self.is_locked:
			raise frappe.DocumentLockedError

	def save(self, *args, **kwargs):
		"""Wrapper for _save"""
		return self._save(*args, **kwargs)

	def _save(self, ignore_permissions=None, ignore_version=None) -> "Document":
		"""Save the current document in the database in the **DocType**'s table or
		`tabSingles` (for single types).

		This will check for user permissions and execute
		`validate` before updating, `on_update` after updating triggers.

		:param ignore_permissions: Do not check permissions if True.
		:param ignore_version: Do not save version if True."""
		if self.flags.in_print:
			return self

		self.flags.notifications_executed = []

		if ignore_permissions is not None:
			self.flags.ignore_permissions = ignore_permissions

		self.flags.ignore_version = frappe.flags.in_test if ignore_version is None else ignore_version

		if self.get("__islocal") or not self.get("name"):
			return self.insert()

		self.check_if_locked()
		self._set_defaults()
		self.check_permission("write", "save")

		self.set_user_and_timestamp()
		self.set_docstatus()
		self.check_if_latest()
		self.set_parent_in_children()
		self.set_name_in_children()

		self.validate_higher_perm_levels()
		self._validate_links()
		self.run_before_save_methods()

		if self._action != "cancel":
			self._validate()

		if self._action == "update_after_submit":
			self.validate_update_after_submit()

		self.set_docstatus()

		# parent
		if self.meta.issingle:
			self.update_single(self.get_valid_dict())
		else:
			self.db_update()

		self.update_children()
		self.run_post_save_methods()

		# clear unsaved flag
		if hasattr(self, "__unsaved"):
			delattr(self, "__unsaved")

		return self

	def copy_attachments_from_amended_from(self):
		"""Copy attachments from `amended_from`"""
		from frappe.desk.form.load import get_attachments

		# loop through attachments
		for attach_item in get_attachments(self.doctype, self.amended_from):
			# save attachments to new doc
			_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_url": attach_item.file_url,
					"file_name": attach_item.file_name,
					"attached_to_name": self.name,
					"attached_to_doctype": self.doctype,
					"folder": "Home/Attachments",
					"is_private": attach_item.is_private,
				}
			)
			_file.save()

	def update_children(self):
		"""update child tables"""
		for df in self.meta.get_table_fields():
			self.update_child_table(df.fieldname, df)

	def update_child_table(self, fieldname: str, df: Optional["DocField"] = None):
		"""sync child table for given fieldname"""
		df: "DocField" = df or self.meta.get_field(fieldname)
		all_rows = self.get(df.fieldname)

		# delete rows that do not match the ones in the document
		# if the doctype isn't in ignore_children_type flag and isn't virtual
		if not (
			df.options in (self.flags.ignore_children_type or ())
			or frappe.get_meta(df.options).is_virtual == 1
		):
			existing_row_names = [row.name for row in all_rows if row.name and not row.is_new()]

			tbl = frappe.qb.DocType(df.options)
			qry = (
				frappe.qb.from_(tbl)
				.where(tbl.parent == self.name)
				.where(tbl.parenttype == self.doctype)
				.where(tbl.parentfield == fieldname)
				.delete()
			)

			if existing_row_names:
				qry = qry.where(tbl.name.notin(existing_row_names))

			qry.run()

		# update / insert
		for d in all_rows:
			d: Document
			d.db_update()

	def get_doc_before_save(self) -> "Document":
		return getattr(self, "_doc_before_save", None)

	def has_value_changed(self, fieldname):
		"""Return True if value has changed before and after saving."""
		from datetime import date, datetime, timedelta

		previous = self.get_doc_before_save()

		if not previous:
			return True

		previous_value = previous.get(fieldname)
		current_value = self.get(fieldname)

		if isinstance(previous_value, datetime):
			current_value = get_datetime(current_value)
		elif isinstance(previous_value, date):
			current_value = getdate(current_value)
		elif isinstance(previous_value, timedelta):
			current_value = get_timedelta(current_value)

		return previous_value != current_value

	def set_new_name(self, force=False, set_name=None, set_child_names=True):
		"""Calls `frappe.naming.set_new_name` for parent and child docs."""

		if self.flags.name_set and not force:
			return

		autoname = self.meta.autoname or ""

		# If autoname has set as Prompt (name)
		if self.get("__newname") and autoname.lower() == "prompt":
			self.name = validate_name(self.doctype, self.get("__newname"))
			self.flags.name_set = True
			return

		if set_name:
			self.name = validate_name(self.doctype, set_name)
		else:
			set_new_name(self)

		if set_child_names:
			# set name for children
			for d in self.get_all_children():
				set_new_name(d)

		self.flags.name_set = True

	def get_title(self):
		"""Get the document title based on title_field or `title` or `name`"""
		return self.get(self.meta.get_title_field()) or ""

	def set_title_field(self):
		"""Set title field based on template"""

		def get_values():
			values = self.as_dict()
			# format values
			for key, value in values.items():
				if value is None:
					values[key] = ""
			return values

		if self.meta.get("title_field") == "title":
			df = self.meta.get_field(self.meta.title_field)

			if df.options:
				self.set(df.fieldname, df.options.format(**get_values()))
			elif self.is_new() and not self.get(df.fieldname) and df.default:
				# set default title for new transactions (if default)
				self.set(df.fieldname, df.default.format(**get_values()))

	def update_single(self, d):
		"""Updates values for Single type Document in `tabSingles`."""
		frappe.db.delete("Singles", {"doctype": self.doctype})
		for field, value in d.items():
			if field != "doctype":
				frappe.db.sql(
					"""insert into `tabSingles` (doctype, field, value)
					values (%s, %s, %s)""",
					(self.doctype, field, value),
				)

		if self.doctype in frappe.db.value_cache:
			del frappe.db.value_cache[self.doctype]

	def set_user_and_timestamp(self):
		self._original_modified = self.modified
		self.modified = now()
		self.modified_by = frappe.session.user

		# We'd probably want the creation and owner to be set via API
		# or Data import at some point, that'd have to be handled here
		if self.is_new() and not (
			frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_migrate
		):
			self.creation = self.modified
			self.owner = self.modified_by

		for d in self.get_all_children():
			d.modified = self.modified
			d.modified_by = self.modified_by
			if not d.owner:
				d.owner = self.owner
			if not d.creation:
				d.creation = self.creation

		frappe.flags.currently_saving.append((self.doctype, self.name))

	def set_docstatus(self):
		if self.docstatus is None:
			self.docstatus = DocStatus.draft()

		for d in self.get_all_children():
			d.docstatus = self.docstatus

	def _validate(self):
		self._validate_mandatory()
		self._validate_data_fields()
		self._validate_selects()
		self._validate_non_negative()
		self._validate_length()
		self._fix_rating_value()
		self._validate_code_fields()
		self._sync_autoname_field()
		self._extract_images_from_text_editor()
		self._sanitize_content()
		self._save_passwords()
		self.validate_workflow()

		for d in self.get_all_children():
			d._validate_data_fields()
			d._validate_selects()
			d._validate_non_negative()
			d._validate_length()
			d._validate_code_fields()
			d._sync_autoname_field()
			d._extract_images_from_text_editor()
			d._sanitize_content()
			d._save_passwords()
		if self.is_new():
			# don't set fields like _assign, _comments for new doc
			for fieldname in optional_fields:
				self.set(fieldname, None)
		else:
			self.validate_set_only_once()

	def _validate_non_negative(self):
		def get_msg(df):
			if self.get("parentfield"):
				return "{} {} #{}: {} {}".format(
					frappe.bold(_(self.doctype)),
					_("Row"),
					self.idx,
					_("Value cannot be negative for"),
					frappe.bold(_(df.label, context=df.parent)),
				)
			else:
				return _("Value cannot be negative for {0}: {1}").format(
					_(df.parent), frappe.bold(_(df.label, context=df.parent))
				)

		for df in self.meta.get(
			"fields", {"non_negative": ("=", 1), "fieldtype": ("in", ["Int", "Float", "Currency"])}
		):
			if flt(self.get(df.fieldname)) < 0:
				msg = get_msg(df)
				frappe.throw(msg, frappe.NonNegativeError, title=_("Negative Value"))

	def _fix_rating_value(self):
		for field in self.meta.get("fields", {"fieldtype": "Rating"}):
			value = self.get(field.fieldname)
			if not isinstance(value, float):
				value = flt(value)

			# Make sure rating is between 0 and 1
			self.set(field.fieldname, max(0, min(value, 1)))

	def validate_workflow(self):
		"""Validate if the workflow transition is valid"""
		if frappe.flags.in_install == "frappe":
			return
		workflow = self.meta.get_workflow()
		if workflow:
			validate_workflow(self)
			if self._action != "save":
				set_workflow_state_on_action(self, workflow, self._action)

	def validate_set_only_once(self):
		"""Validate that fields are not changed if not in insert"""
		set_only_once_fields = self.meta.get_set_only_once_fields()

		if set_only_once_fields and self._doc_before_save:
			# document exists before saving
			for field in set_only_once_fields:
				fail = False
				value = self.get(field.fieldname)
				original_value = self._doc_before_save.get(field.fieldname)

				if field.fieldtype in table_fields:
					fail = not self.is_child_table_same(field.fieldname)
				elif field.fieldtype in ("Date", "Datetime", "Time"):
					fail = str(value) != str(original_value)
				else:
					fail = value != original_value

				if fail:
					frappe.throw(
						_("Value cannot be changed for {0}").format(
							frappe.bold(self.meta.get_label(field.fieldname))
						),
						exc=frappe.CannotChangeConstantError,
					)

		return False

	def is_child_table_same(self, fieldname):
		"""Validate child table is same as original table before saving"""
		value = self.get(fieldname)
		original_value = self._doc_before_save.get(fieldname)
		same = True

		if len(original_value) != len(value):
			same = False
		else:
			# check all child entries
			for i, d in enumerate(original_value):
				new_child = value[i].as_dict(convert_dates_to_str=True)
				original_child = d.as_dict(convert_dates_to_str=True)

				# all fields must be same other than modified and modified_by
				for key in ("modified", "modified_by", "creation"):
					del new_child[key]
					del original_child[key]

				if original_child != new_child:
					same = False
					break

		return same

	def apply_fieldlevel_read_permissions(self):
		"""Remove values the user is not allowed to read."""
		if frappe.session.user == "Administrator":
			return

		all_fields = self.meta.fields.copy()
		for table_field in self.meta.get_table_fields():
			all_fields += frappe.get_meta(table_field.options).fields or []

		if all(df.permlevel == 0 for df in all_fields):
			return

		has_access_to = self.get_permlevel_access("read")

		for df in self.meta.fields:
			if df.permlevel and hasattr(self, df.fieldname) and df.permlevel not in has_access_to:
				try:
					delattr(self, df.fieldname)
				except AttributeError:
					# hasattr might return True for class attribute which can't be delattr-ed.
					continue

		for table_field in self.meta.get_table_fields():
			for df in frappe.get_meta(table_field.options).fields or []:
				if df.permlevel and df.permlevel not in has_access_to:
					for child in self.get(table_field.fieldname) or []:
						if hasattr(child, df.fieldname):
							delattr(child, df.fieldname)

	def validate_higher_perm_levels(self):
		"""If the user does not have permissions at permlevel > 0, then reset the values to original / default"""
		if self.flags.ignore_permissions or frappe.flags.in_install:
			return

		if frappe.session.user == "Administrator":
			return

		has_access_to = self.get_permlevel_access()
		high_permlevel_fields = self.meta.get_high_permlevel_fields()

		if high_permlevel_fields:
			self.reset_values_if_no_permlevel_access(has_access_to, high_permlevel_fields)

		# If new record then don't reset the values for child table
		if self.is_new():
			return

		# check for child tables
		for df in self.meta.get_table_fields():
			high_permlevel_fields = frappe.get_meta(df.options).get_high_permlevel_fields()
			if high_permlevel_fields:
				for d in self.get(df.fieldname):
					d.reset_values_if_no_permlevel_access(has_access_to, high_permlevel_fields)

	def get_permlevel_access(self, permission_type="write"):
		allowed_permlevels = []
		roles = frappe.get_roles()

		for perm in self.get_permissions():
			if perm.role in roles and perm.get(permission_type) and perm.permlevel not in allowed_permlevels:
				allowed_permlevels.append(perm.permlevel)

		return allowed_permlevels

	def has_permlevel_access_to(self, fieldname, df=None, permission_type="read"):
		if not df:
			df = self.meta.get_field(fieldname)

		return df.permlevel in self.get_permlevel_access(permission_type)

	def get_permissions(self):
		if self.meta.istable:
			# use parent permissions
			permissions = frappe.get_meta(self.parenttype).permissions
		else:
			permissions = self.meta.permissions

		return permissions

	def _set_defaults(self):
		if frappe.flags.in_import:
			return

		if self.is_new():
			new_doc = frappe.new_doc(self.doctype, as_dict=True)
			self.update_if_missing(new_doc)

		# children
		for df in self.meta.get_table_fields():
			new_doc = frappe.new_doc(df.options, parent_doc=self, parentfield=df.fieldname, as_dict=True)
			value = self.get(df.fieldname)
			if isinstance(value, list):
				for d in value:
					if d.is_new():
						d.update_if_missing(new_doc)

	def check_if_latest(self):
		"""Checks if `modified` timestamp provided by document being updated is same as the
		`modified` timestamp in the database. If there is a different, the document has been
		updated in the database after the current copy was read. Will throw an error if
		timestamps don't match.

		Will also validate document transitions (Save > Submit > Cancel) calling
		`self.check_docstatus_transition`."""

		self.load_doc_before_save(raise_exception=True)

		self._action = "save"
		previous = self._doc_before_save

		# previous is None for new document insert
		if not previous:
			self.check_docstatus_transition(0)
			return

		if cstr(previous.modified) != cstr(self._original_modified):
			frappe.msgprint(
				_("Error: Document has been modified after you have opened it")
				+ (f" ({previous.modified}, {self.modified}). ")
				+ _("Please refresh to get the latest document."),
				raise_exception=frappe.TimestampMismatchError,
			)

		if not self.meta.issingle:
			self.check_docstatus_transition(previous.docstatus)

	def check_docstatus_transition(self, to_docstatus):
		"""Ensures valid `docstatus` transition.
		Valid transitions are (number in brackets is `docstatus`):

		- Save (0) > Save (0)
		- Save (0) > Submit (1)
		- Submit (1) > Submit (1)
		- Submit (1) > Cancel (2)

		"""
		if not self.docstatus:
			self.docstatus = DocStatus.draft()

		if to_docstatus == DocStatus.draft():
			if self.docstatus.is_draft():
				self._action = "save"
			elif self.docstatus.is_submitted():
				self._action = "submit"
				self.check_permission("submit")
			elif self.docstatus.is_cancelled():
				raise frappe.DocstatusTransitionError(
					_("Cannot change docstatus from 0 (Draft) to 2 (Cancelled)")
				)
			else:
				raise frappe.ValidationError(_("Invalid docstatus"), self.docstatus)

		elif to_docstatus == DocStatus.submitted():
			if self.docstatus.is_submitted():
				self._action = "update_after_submit"
				self.check_permission("submit")
			elif self.docstatus.is_cancelled():
				self._action = "cancel"
				self.check_permission("cancel")
			elif self.docstatus.is_draft():
				raise frappe.DocstatusTransitionError(
					_("Cannot change docstatus from 1 (Submitted) to 0 (Draft)")
				)
			else:
				raise frappe.ValidationError(_("Invalid docstatus"), self.docstatus)

		elif to_docstatus == DocStatus.cancelled():
			raise frappe.ValidationError(_("Cannot edit cancelled document"))

	def set_parent_in_children(self):
		"""Updates `parent` and `parenttype` property in all children."""
		for d in self.get_all_children():
			d.parent = self.name
			d.parenttype = self.doctype

	def set_name_in_children(self):
		# Set name for any new children
		for d in self.get_all_children():
			if not d.name:
				set_new_name(d)

	def validate_update_after_submit(self):
		if self.flags.ignore_validate_update_after_submit:
			return

		self._validate_update_after_submit()
		for d in self.get_all_children():
			if d.is_new() and self.meta.get_field(d.parentfield).allow_on_submit:
				# in case of a new row, don't validate allow on submit, if table is allow on submit
				continue

			d._validate_update_after_submit()

		# TODO check only allowed values are updated

	def _validate_mandatory(self):
		if self.flags.ignore_mandatory:
			return

		missing = self._get_missing_mandatory_fields()
		for d in self.get_all_children():
			missing.extend(d._get_missing_mandatory_fields())

		if not missing:
			return

		for idx, msg in missing:  # noqa: B007
			msgprint(msg)

		if frappe.flags.print_messages:
			print(self.as_json().encode("utf-8"))

		raise frappe.MandatoryError(
			"[{doctype}, {name}]: {fields}".format(
				fields=", ".join(each[0] for each in missing), doctype=self.doctype, name=self.name
			)
		)

	def _validate_links(self):
		if self.flags.ignore_links or self._action == "cancel":
			return

		invalid_links, cancelled_links = self.get_invalid_links()

		for d in self.get_all_children():
			result = d.get_invalid_links(is_submittable=self.meta.is_submittable)
			invalid_links.extend(result[0])
			cancelled_links.extend(result[1])

		if invalid_links:
			msg = ", ".join(each[2] for each in invalid_links)
			frappe.throw(_("Could not find {0}").format(msg), frappe.LinkValidationError)

		if cancelled_links:
			msg = ", ".join(each[2] for each in cancelled_links)
			frappe.throw(_("Cannot link cancelled document: {0}").format(msg), frappe.CancelledLinkError)

	def get_all_children(self, parenttype=None) -> list["Document"]:
		"""Return all children documents from **Table** type fields in a list."""

		children = []

		for df in self.meta.get_table_fields():
			if parenttype and df.options != parenttype:
				continue

			if value := self.get(df.fieldname):
				children.extend(value)

		return children

	def run_method(self, method, *args, **kwargs):
		"""run standard triggers, plus those in hooks"""

		def fn(self, *args, **kwargs):
			method_object = getattr(self, method, None)

			# Cannot have a field with same name as method
			# If method found in __dict__, expect it to be callable
			if method in self.__dict__ or callable(method_object):
				return method_object(*args, **kwargs)

		fn.__name__ = str(method)
		out = Document.hook(fn)(self, *args, **kwargs)

		self.run_notifications(method)
		run_webhooks(self, method)
		run_server_script_for_doc_event(self, method)

		return out

	def run_trigger(self, method, *args, **kwargs):
		return self.run_method(method, *args, **kwargs)

	def run_notifications(self, method):
		"""Run notifications for this method"""
		if (
			(frappe.flags.in_import and frappe.flags.mute_emails)
			or frappe.flags.in_patch
			or frappe.flags.in_install
		):
			return

		if self.flags.notifications_executed is None:
			self.flags.notifications_executed = []

		from frappe.email.doctype.notification.notification import evaluate_alert

		if self.flags.notifications is None:

			def _get_notifications():
				"""Return enabled notifications for the current doctype."""

				return frappe.get_all(
					"Notification",
					fields=["name", "event", "method"],
					filters={"enabled": 1, "document_type": self.doctype},
				)

			self.flags.notifications = frappe.cache.hget("notifications", self.doctype, _get_notifications)

		if not self.flags.notifications:
			return

		def _evaluate_alert(alert):
			if alert.name in self.flags.notifications_executed:
				return

			evaluate_alert(self, alert.name, alert.event)
			self.flags.notifications_executed.append(alert.name)

		event_map = {
			"on_update": "Save",
			"after_insert": "New",
			"on_submit": "Submit",
			"on_cancel": "Cancel",
		}

		if not self.flags.in_insert:
			# value change is not applicable in insert
			event_map["on_change"] = "Value Change"

		for alert in self.flags.notifications:
			event = event_map.get(method, None)
			if event and alert.event == event:
				_evaluate_alert(alert)
			elif alert.event == "Method" and method == alert.method:
				_evaluate_alert(alert)

	def _submit(self):
		"""Submit the document. Sets `docstatus` = 1, then saves."""
		self.docstatus = DocStatus.submitted()
		return self.save()

	def _cancel(self):
		"""Cancel the document. Sets `docstatus` = 2, then saves."""
		self.docstatus = DocStatus.cancelled()
		return self.save()

	def _rename(self, name: str, merge: bool = False, force: bool = False, validate_rename: bool = True):
		"""Rename the document. Triggers frappe.rename_doc, then reloads."""
		from frappe.model.rename_doc import rename_doc

		self.name = rename_doc(doc=self, new=name, merge=merge, force=force, validate=validate_rename)
		self.reload()

	@frappe.whitelist()
	def submit(self):
		"""Submit the document. Sets `docstatus` = 1, then saves."""
		return self._submit()

	@frappe.whitelist()
	def cancel(self):
		"""Cancel the document. Sets `docstatus` = 2, then saves."""
		return self._cancel()

	@frappe.whitelist()
	def rename(self, name: str, merge=False, force=False, validate_rename=True):
		"""Rename the document to `name`. This transforms the current object."""
		return self._rename(name=name, merge=merge, force=force, validate_rename=validate_rename)

	def delete(self, ignore_permissions=False, force=False, *, delete_permanently=False):
		"""Delete document."""
		return frappe.delete_doc(
			self.doctype,
			self.name,
			ignore_permissions=ignore_permissions,
			flags=self.flags,
			force=force,
			delete_permanently=delete_permanently,
		)

	def run_before_save_methods(self):
		"""Run standard methods before	`INSERT` or `UPDATE`. Standard Methods are:

		- `validate`, `before_save` for **Save**.
		- `validate`, `before_submit` for **Submit**.
		- `before_cancel` for **Cancel**
		- `before_update_after_submit` for **Update after Submit**

		Will also update title_field if set"""

		self.reset_seen()

		# before_validate method should be executed before ignoring validations
		if self._action in ("save", "submit"):
			self.run_method("before_validate")

		if self.flags.ignore_validate:
			return

		if self._action == "save":
			self.run_method("validate")
			self.run_method("before_save")
		elif self._action == "submit":
			self.run_method("validate")
			self.run_method("before_submit")
		elif self._action == "cancel":
			self.run_method("before_cancel")
		elif self._action == "update_after_submit":
			self.run_method("before_update_after_submit")

		self.set_title_field()

	def load_doc_before_save(self, *, raise_exception: bool = False):
		"""load existing document from db before saving"""

		self._doc_before_save = None

		if self.is_new():
			return

		try:
			self._doc_before_save = frappe.get_doc(self.doctype, self.name, for_update=True)
		except frappe.DoesNotExistError:
			if raise_exception:
				raise

			frappe.clear_last_message()

	def run_post_save_methods(self):
		"""Run standard methods after `INSERT` or `UPDATE`. Standard Methods are:

		- `on_update` for **Save**.
		- `on_update`, `on_submit` for **Submit**.
		- `on_cancel` for **Cancel**
		- `update_after_submit` for **Update after Submit**"""

		if self._action == "save":
			self.run_method("on_update")
		elif self._action == "submit":
			self.run_method("on_update")
			self.run_method("on_submit")
		elif self._action == "cancel":
			self.run_method("on_cancel")
			self.check_no_back_links_exist()
		elif self._action == "update_after_submit":
			self.run_method("on_update_after_submit")

		self.clear_cache()

		if self.flags.get("notify_update", True):
			self.notify_update()

		update_global_search(self)

		self.save_version()

		self.run_method("on_change")

		if (self.doctype, self.name) in frappe.flags.currently_saving:
			frappe.flags.currently_saving.remove((self.doctype, self.name))

	def clear_cache(self):
		frappe.clear_document_cache(self.doctype, self.name)

	def reset_seen(self):
		"""Clear _seen property and set current user as seen"""
		if (
			getattr(self.meta, "track_seen", False)
			and not getattr(self.meta, "issingle", False)
			and not self.is_new()
		):
			frappe.db.set_value(
				self.doctype, self.name, "_seen", json.dumps([frappe.session.user]), update_modified=False
			)

	def notify_update(self):
		"""Publish realtime that the current document is modified"""
		if frappe.flags.in_patch:
			return

		frappe.publish_realtime(
			"doc_update",
			{"modified": self.modified, "doctype": self.doctype, "name": self.name},
			doctype=self.doctype,
			docname=self.name,
			after_commit=True,
		)

		if not self.meta.get("read_only") and not self.meta.get("issingle") and not self.meta.get("istable"):
			data = {"doctype": self.doctype, "name": self.name, "user": frappe.session.user}
			frappe.publish_realtime("list_update", data, after_commit=True)

	def db_set(self, fieldname, value=None, update_modified=True, notify=False, commit=False):
		"""Set a value in the document object, update the timestamp and update the database.

		WARNING: This method does not trigger controller validations and should
		be used very carefully.

		:param fieldname: fieldname of the property to be updated, or a {"field":"value"} dictionary
		:param value: value of the property to be updated
		:param update_modified: default True. updates the `modified` and `modified_by` properties
		:param notify: default False. run doc.notify_update() to send updates via socketio
		:param commit: default False. run frappe.db.commit()
		"""
		if isinstance(fieldname, dict):
			self.update(fieldname)
		else:
			self.set(fieldname, value)

		if update_modified and (self.doctype, self.name) not in frappe.flags.currently_saving:
			# don't update modified timestamp if called from post save methods
			# like on_update or on_submit
			self.set("modified", now())
			self.set("modified_by", frappe.session.user)

		# load but do not reload doc_before_save because before_change or on_change might expect it
		if not self.get_doc_before_save():
			self.load_doc_before_save()

		# to trigger notification on value change
		self.run_method("before_change")

		if self.name is None:
			return

		if self.meta.issingle:
			frappe.db.set_single_value(
				self.doctype,
				fieldname,
				value,
				modified=self.modified,
				modified_by=self.modified_by,
				update_modified=update_modified,
			)
		else:
			frappe.db.set_value(
				self.doctype,
				self.name,
				fieldname,
				value,
				self.modified,
				self.modified_by,
				update_modified=update_modified,
			)

		self.run_method("on_change")

		if notify:
			self.notify_update()

		if commit:
			frappe.db.commit()

	def db_get(self, fieldname):
		"""get database value for this fieldname"""
		return frappe.db.get_value(self.doctype, self.name, fieldname)

	def check_no_back_links_exist(self):
		"""Check if document links to any active document before Cancel."""
		from frappe.model.delete_doc import check_if_doc_is_dynamically_linked, check_if_doc_is_linked

		if not self.flags.ignore_links:
			check_if_doc_is_linked(self, method="Cancel")
			check_if_doc_is_dynamically_linked(self, method="Cancel")

	def save_version(self):
		"""Save version info"""

		# don't track version under following conditions
		if (
			not getattr(self.meta, "track_changes", False)
			or self.doctype == "Version"
			or self.flags.ignore_version
			or frappe.flags.in_install
			or (not self._doc_before_save and frappe.flags.in_patch)
		):
			return

		doc_to_compare = self._doc_before_save
		if not doc_to_compare and (amended_from := self.get("amended_from")):
			doc_to_compare = frappe.get_doc(self.doctype, amended_from)

		version = frappe.new_doc("Version")
		if version.update_version_info(doc_to_compare, self):
			version.insert(ignore_permissions=True)

			if not frappe.flags.in_migrate:
				# follow since you made a change?
				if frappe.get_cached_value("User", frappe.session.user, "follow_created_documents"):
					follow_document(self.doctype, self.name, frappe.session.user)

	@staticmethod
	def hook(f):
		"""Decorator: Make method `hookable` (i.e. extensible by another app).

		Note: If each hooked method returns a value (dict), then all returns are
		collated in one dict and returned. Ideally, don't return values in hookable
		methods, set properties in the document."""

		def add_to_return_value(self, new_return_value):
			if new_return_value is None:
				self._return_value = self.get("_return_value")
				return

			if isinstance(new_return_value, dict):
				if not self.get("_return_value"):
					self._return_value = {}
				self._return_value.update(new_return_value)
			else:
				self._return_value = new_return_value

		def compose(fn, *hooks):
			def runner(self, method, *args, **kwargs):
				add_to_return_value(self, fn(self, *args, **kwargs))
				for f in hooks:
					add_to_return_value(self, f(self, method, *args, **kwargs))

				return self.__dict__.pop("_return_value", None)

			return runner

		def composer(self, *args, **kwargs):
			hooks = []
			method = f.__name__
			doc_events = frappe.get_doc_hooks()
			for handler in doc_events.get(self.doctype, {}).get(method, []) + doc_events.get("*", {}).get(
				method, []
			):
				hooks.append(frappe.get_attr(handler))

			composed = compose(f, *hooks)
			return composed(self, method, *args, **kwargs)

		return composer

	def is_whitelisted(self, method_name):
		method = getattr(self, method_name, None)
		if not method:
			raise NotFound(f"Method {method_name} not found")

		is_whitelisted(getattr(method, "__func__", method))

	def validate_value(self, fieldname, condition, val2, doc=None, raise_exception=None):
		"""Check that value of fieldname should be 'condition' val2
		else throw Exception."""
		error_condition_map = {
			"in": _("one of"),
			"not in": _("none of"),
			"^": _("beginning with"),
		}

		if not doc:
			doc = self

		val1 = doc.get_value(fieldname)

		df = doc.meta.get_field(fieldname)
		val2 = doc.cast(val2, df)

		if not compare(val1, condition, val2):
			label = doc.meta.get_label(fieldname)
			condition_str = error_condition_map.get(condition, condition)
			if doc.get("parentfield"):
				msg = _("Incorrect value in row {0}: {1} must be {2} {3}").format(
					doc.idx, label, condition_str, val2
				)
			else:
				msg = _("Incorrect value: {0} must be {1} {2}").format(label, condition_str, val2)

			# raise passed exception or True
			msgprint(msg, raise_exception=raise_exception or True)

	def validate_table_has_rows(self, parentfield, raise_exception=None):
		"""Raise exception if Table field is empty."""
		if not (isinstance(self.get(parentfield), list) and len(self.get(parentfield)) > 0):
			label = self.meta.get_label(parentfield)
			frappe.throw(
				_("Table {0} cannot be empty").format(label), raise_exception or frappe.EmptyTableError
			)

	def round_floats_in(self, doc, fieldnames=None):
		"""Round floats for all `Currency`, `Float`, `Percent` fields for the given doc.

		:param doc: Document whose numeric properties are to be rounded.
		:param fieldnames: [Optional] List of fields to be rounded."""
		if not fieldnames:
			fieldnames = (
				df.fieldname
				for df in doc.meta.get("fields", {"fieldtype": ["in", ["Currency", "Float", "Percent"]]})
			)

		for fieldname in fieldnames:
			doc.set(fieldname, flt(doc.get(fieldname), self.precision(fieldname, doc.get("parentfield"))))

	def get_url(self):
		"""Return Desk URL for this document."""
		return get_absolute_url(self.doctype, self.name)

	def add_comment(
		self,
		comment_type="Comment",
		text=None,
		comment_email=None,
		comment_by=None,
	):
		"""Add a comment to this document.

		:param comment_type: e.g. `Comment`. See Communication for more info."""

		return frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": comment_type,
				"comment_email": comment_email or frappe.session.user,
				"comment_by": comment_by,
				"reference_doctype": self.doctype,
				"reference_name": self.name,
				"content": text or comment_type,
			}
		).insert(ignore_permissions=True)

	def add_seen(self, user=None):
		"""add the given/current user to list of users who have seen this document (_seen)"""
		if not user:
			user = frappe.session.user

		if self.meta.track_seen and not frappe.flags.read_only and not self.meta.issingle:
			_seen = self.get("_seen") or []
			_seen = frappe.parse_json(_seen)

			if user not in _seen:
				_seen.append(user)
				frappe.db.set_value(
					self.doctype, self.name, "_seen", json.dumps(_seen), update_modified=False
				)
				frappe.local.flags.commit = True

	def add_viewed(self, user=None, force=False, unique_views=False):
		"""add log to communication when a user views a document"""
		if not user:
			user = frappe.session.user

		if unique_views and frappe.db.exists(
			"View Log", {"reference_doctype": self.doctype, "reference_name": self.name, "viewed_by": user}
		):
			return

		if (hasattr(self.meta, "track_views") and self.meta.track_views) or force:
			view_log = frappe.get_doc(
				{
					"doctype": "View Log",
					"viewed_by": user,
					"reference_doctype": self.doctype,
					"reference_name": self.name,
				}
			)
			if frappe.flags.read_only:
				view_log.deferred_insert()
			else:
				view_log.insert(ignore_permissions=True)
				frappe.local.flags.commit = True

			return view_log

	def log_error(self, title=None, message=None):
		"""Helper function to create an Error Log"""
		return frappe.log_error(
			message=message, title=title, reference_doctype=self.doctype, reference_name=self.name
		)

	def get_signature(self):
		"""Return signature (hash) for private URL."""
		return hashlib.sha224(f"{self.doctype}:{self.name}".encode(), usedforsecurity=False).hexdigest()

	def get_document_share_key(self, expires_on=None, no_expiry=False):
		if no_expiry:
			expires_on = None

		existing_key = frappe.db.exists(
			"Document Share Key",
			{
				"reference_doctype": self.doctype,
				"reference_docname": self.name,
				"expires_on": expires_on,
			},
		)
		if existing_key:
			doc = frappe.get_doc("Document Share Key", existing_key)
		else:
			doc = frappe.new_doc("Document Share Key")
			doc.reference_doctype = self.doctype
			doc.reference_docname = self.name
			doc.expires_on = expires_on
			doc.flags.no_expiry = no_expiry
			doc.insert(ignore_permissions=True)

		return doc.key

	def get_liked_by(self):
		liked_by = getattr(self, "_liked_by", None)
		if liked_by:
			return json.loads(liked_by)
		else:
			return []

	def set_onload(self, key, value):
		if not self.get("__onload"):
			self.set("__onload", frappe._dict())
		self.get("__onload")[key] = value

	def get_onload(self, key=None):
		if not key:
			return self.get("__onload", frappe._dict())

		return self.get("__onload")[key]

	def queue_action(self, action, **kwargs):
		"""Run an action in background. If the action has an inner function,
		like _submit for submit, it will call that instead"""
		# call _submit instead of submit, so you can override submit to call
		# run_delayed based on some action
		# See: Stock Reconciliation
		from frappe.utils.background_jobs import enqueue

		if hasattr(self, f"_{action}"):
			action = f"_{action}"

		try:
			self.lock()
		except frappe.DocumentLockedError:
			# Allow unlocking if created more than 60 minutes ago
			primary_action = None
			if file_lock.lock_age(self.get_signature()) > DOCUMENT_LOCK_SOFT_EXPIRY:
				primary_action = {
					"label": "Force Unlock",
					"server_action": "frappe.model.document.unlock_document",
					"hide_on_success": True,
					"args": {
						"doctype": self.doctype,
						"name": self.name,
					},
				}

			frappe.throw(
				_(
					"This document is currently locked and queued for execution. Please try again after some time."
				),
				title=_("Document Queued"),
				primary_action=primary_action,
			)

		return enqueue(
			"frappe.model.document.execute_action",
			__doctype=self.doctype,
			__name=self.name,
			__action=action,
			**kwargs,
		)

	def lock(self, timeout=None):
		"""Creates a lock file for the given document. If timeout is set,
		it will retry every 1 second for acquiring the lock again

		:param timeout: Timeout in seconds, default 0"""
		signature = self.get_signature()
		if file_lock.lock_exists(signature):
			lock_exists = True
			if file_lock.lock_age(signature) > DOCUMENT_LOCK_EXPIRTY:
				file_lock.delete_lock(signature)
				lock_exists = False
			if timeout:
				for _ in range(timeout):
					time.sleep(1)
					if not file_lock.lock_exists(signature):
						lock_exists = False
						break
			if lock_exists:
				raise frappe.DocumentLockedError
		file_lock.create_lock(signature)
		frappe.local.locked_documents.append(self)

	def unlock(self):
		"""Delete the lock file for this document"""
		file_lock.delete_lock(self.get_signature())
		if self in frappe.local.locked_documents:
			frappe.local.locked_documents.remove(self)

	def validate_from_to_dates(self, from_date_field: str, to_date_field: str) -> None:
		"""Validate that the value of `from_date_field` is not later than the value of `to_date_field`."""
		from_date = self.get(from_date_field)
		to_date = self.get(to_date_field)
		if not (from_date and to_date):
			return

		if date_diff(to_date, from_date) < 0:
			frappe.throw(
				_("{0} must be after {1}").format(
					frappe.bold(_(self.meta.get_label(to_date_field))),
					frappe.bold(_(self.meta.get_label(from_date_field))),
				),
				frappe.exceptions.InvalidDates,
			)

	def get_assigned_users(self):
		assigned_users = frappe.get_all(
			"ToDo",
			fields=["allocated_to"],
			filters={
				"reference_type": self.doctype,
				"reference_name": self.name,
				"status": ("!=", "Cancelled"),
			},
			pluck="allocated_to",
		)

		return set(assigned_users)

	def add_tag(self, tag):
		"""Add a Tag to this document"""
		from frappe.desk.doctype.tag.tag import DocTags

		DocTags(self.doctype).add(self.name, tag)

	def remove_tag(self, tag):
		"""Remove a Tag to this document"""
		from frappe.desk.doctype.tag.tag import DocTags

		DocTags(self.doctype).remove(self.name, tag)

	def get_tags(self):
		"""Return a list of Tags attached to this document"""
		from frappe.desk.doctype.tag.tag import DocTags

		return DocTags(self.doctype).get_tags(self.name).split(",")[1:]

	def deferred_insert(self) -> None:
		"""Push the document to redis temporarily and insert later.

		WARN: This doesn't guarantee insertion as redis can be restarted
		before data is flushed to database.
		"""

		from frappe.deferred_insert import deferred_insert

		self.set_user_and_timestamp()

		doc = self.get_valid_dict(convert_dates_to_str=True, ignore_virtual=True)
		deferred_insert(doctype=self.doctype, records=doc)

	def __repr__(self):
		name = self.name or "unsaved"
		doctype = self.__class__.__name__

		docstatus = f" docstatus={self.docstatus}" if self.docstatus else ""
		parent = f" parent={self.parent}" if getattr(self, "parent", None) else ""

		return f"<{doctype}: {name}{docstatus}{parent}>"

	def __str__(self):
		name = self.name or "unsaved"
		doctype = self.__class__.__name__

		return f"{doctype}({name})"


def execute_action(__doctype, __name, __action, **kwargs):
	"""Execute an action on a document (called by background worker)"""
	doc = frappe.get_doc(__doctype, __name)
	doc.unlock()
	try:
		getattr(doc, __action)(**kwargs)
	except Exception:
		frappe.db.rollback()

		# add a comment (?)
		if frappe.message_log:
			msg = frappe.message_log[-1].get("message")
		else:
			msg = "<pre><code>" + frappe.get_traceback() + "</pre></code>"

		doc.add_comment("Comment", _("Action Failed") + "<br><br>" + msg)
	doc.notify_update()


def bulk_insert(
	doctype: str,
	documents: Iterable["Document"],
	ignore_duplicates: bool = False,
	chunk_size=10_000,
):
	"""Insert simple Documents objects to database in bulk.

	Warning/Info:
	        - All documents are inserted without triggering ANY hooks.
	        - This function assumes you've done the due dilligence and inserts in similar fashion as db_insert
	        - Documents can be any iterable / generator containing Document objects
	"""

	doctype_meta = frappe.get_meta(doctype)
	documents = list(documents)

	valid_column_map = {
		doctype: doctype_meta.get_valid_columns(),
	}
	values_map = {
		doctype: _document_values_generator(documents, valid_column_map[doctype]),
	}

	for child_table in doctype_meta.get_table_fields():
		valid_column_map[child_table.options] = frappe.get_meta(child_table.options).get_valid_columns()
		values_map[child_table.options] = _document_values_generator(
			(
				ch_doc
				for ch_doc in (
					child_docs for doc in documents for child_docs in doc.get(child_table.fieldname)
				)
			),
			valid_column_map[child_table.options],
		)

	for dt, docs in values_map.items():
		frappe.db.bulk_insert(
			dt, valid_column_map[dt], docs, ignore_duplicates=ignore_duplicates, chunk_size=chunk_size
		)


def _document_values_generator(
	documents: Iterable["Document"],
	columns: list[str],
) -> Generator[tuple[Any], None, None]:
	for doc in documents:
		doc.creation = doc.modified = now()
		doc.created_by = doc.modified_by = frappe.session.user
		doc_values = doc.get_valid_dict(
			convert_dates_to_str=True,
			ignore_nulls=True,
			ignore_virtual=True,
		)
		yield tuple(doc_values.get(col) for col in columns)


@frappe.whitelist()
def unlock_document(doctype: str, name: str):
	frappe.get_doc(doctype, name).unlock()
	frappe.msgprint(frappe._("Document Unlocked"), alert=True)


def _filter(data, filters, limit=None):
	"""pass filters as:
	{"key": "val", "key": ["!=", "val"],
	"key": ["in", "val"], "key": ["not in", "val"], "key": "^val",
	"key" : True (exists), "key": False (does not exist) }"""

	out, _filters = [], {}

	if not data:
		return out

	# setup filters as tuples
	if filters:
		for f in filters:
			fval = filters[f]

			if not isinstance(fval, tuple | list):
				if fval is True:
					fval = ("not None", fval)
				elif fval is False:
					fval = ("None", fval)
				elif isinstance(fval, str) and fval.startswith("^"):
					fval = ("^", fval[1:])
				else:
					fval = ("=", fval)

			_filters[f] = fval

	for d in data:
		for f, fval in _filters.items():
			if not compare(getattr(d, f, None), fval[0], fval[1]):
				break
		else:
			out.append(d)
			if limit and len(out) >= limit:
				break

	return out
