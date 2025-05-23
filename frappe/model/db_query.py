# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""build query for doclistview and return results"""

import copy
import datetime
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import cached_property

import frappe
import frappe.defaults
import frappe.permissions
import frappe.share
from frappe import _
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.database.utils import DefaultOrderBy, FallBackDateTimeStr, NestedSetHierarchy
from frappe.model import OPTIONAL_FIELDS, get_permitted_fields
from frappe.model.meta import get_table_columns
from frappe.model.utils import is_virtual_doctype
from frappe.model.utils.user_settings import get_user_settings, update_user_settings
from frappe.query_builder.utils import Column
from frappe.types import Filters, FilterSignature, FilterTuple
from frappe.utils import (
	cint,
	cstr,
	flt,
	get_filter,
	get_time,
	get_timespan_date_range,
)
from frappe.utils.data import DateTimeLikeObject, get_datetime, getdate, sbool

LOCATE_PATTERN = re.compile(r"locate\([^,]+,\s*[`\"]?name[`\"]?\s*\)", flags=re.IGNORECASE)
LOCATE_CAST_PATTERN = re.compile(r"locate\(([^,]+),\s*([`\"]?name[`\"]?)\s*\)", flags=re.IGNORECASE)
FUNC_IFNULL_PATTERN = re.compile(r"(strpos|ifnull|coalesce)\(\s*[`\"]?name[`\"]?\s*,", flags=re.IGNORECASE)
CAST_VARCHAR_PATTERN = re.compile(r"([`\"]?tab[\w`\" -]+\.[`\"]?name[`\"]?)(?!\w)", flags=re.IGNORECASE)
ORDER_BY_PATTERN = re.compile(r"\ order\ by\ |\ asc|\ ASC|\ desc|\ DESC", flags=re.IGNORECASE)
SUB_QUERY_PATTERN = re.compile("^.*[,();@].*", flags=re.DOTALL)
IS_QUERY_PATTERN = re.compile(r"^(select|delete|update|drop|create)\s")
IS_QUERY_PREDICATE_PATTERN = re.compile(r"\s*[0-9a-zA-z]*\s*( from | group by | order by | where | join )")
FIELD_QUOTE_PATTERN = re.compile(r"[0-9a-zA-Z]+\s*'")
FIELD_COMMA_PATTERN = re.compile(r"[0-9a-zA-Z_]+\s*,")
STRICT_FIELD_PATTERN = re.compile(r".*/\*.*")
STRICT_UNION_PATTERN = re.compile(r".*\s(union).*\s")
ORDER_GROUP_PATTERN = re.compile(r".*[^a-z0-9-_ ,`'\"\.\(\)].*")
SPECIAL_FIELD_CHARS = frozenset(("(", "`", ".", "'", '"', "*"))
# XXX: These are just matching brackets to not confuse code formatters: ))


class DatabaseQuery:
	def __init__(self, doctype, user=None):
		self.doctype = doctype
		self.tables = []
		self.link_tables = []
		self.linked_table_aliases = {}
		self.linked_table_counter = Counter()
		self.conditions = []
		self.or_conditions = []
		self.fields = None
		self.user = user or frappe.session.user
		self.ignore_ifnull = False
		self.flags = frappe._dict()
		self.reference_doctype = None
		self.permission_map = {}
		self.shared = []
		self._fetch_shared_documents = False
		self._metas = {}

	@cached_property
	def doctype_meta(self):
		return self.get_meta(self.doctype)

	def get_meta(self, doctype: str):
		if doctype not in self._metas:
			self._metas[doctype] = frappe.get_meta(doctype)
		return self._metas[doctype]

	@property
	def query_tables(self):
		return self.tables + [d.table_alias for d in self.link_tables]

	def execute(
		self,
		fields=None,
		filters: FilterSignature | str | None = None,
		or_filters: FilterSignature | None = None,
		docstatus=None,
		group_by=None,
		order_by=DefaultOrderBy,
		limit_start=False,
		limit_page_length=None,
		as_list=False,
		with_childnames=False,
		debug=False,
		ignore_permissions=False,
		user=None,
		with_comment_count=False,
		join="left join",
		distinct=False,
		start=None,
		page_length=None,
		limit=None,
		ignore_ifnull=False,
		save_user_settings=False,
		save_user_settings_fields=False,
		update=None,
		user_settings=None,
		reference_doctype=None,
		run=True,
		strict=True,
		pluck=None,
		ignore_ddl=False,
		*,
		parent_doctype=None,
	) -> list:
		if not ignore_permissions:
			self.check_read_permission(self.doctype, parent_doctype=parent_doctype)

		# filters and fields swappable
		# its hard to remember what comes first
		if isinstance(fields, dict) or (fields and isinstance(fields, list) and isinstance(fields[0], list)):
			# if fields is given as dict/list of list, its probably filters
			filters, fields = fields, filters

		elif fields and isinstance(filters, list) and len(filters) > 1 and isinstance(filters[0], str):
			# if `filters` is a list of strings, its probably fields
			filters, fields = fields, filters

		if fields:
			self.fields = fields
		else:
			self.fields = [f"`tab{self.doctype}`.`{pluck or 'name'}`"]

		if start:
			limit_start = start
		if page_length:
			limit_page_length = page_length
		if limit:
			limit_page_length = limit
		if as_list and not isinstance(self.fields, (Sequence | str)) and len(self.fields) > 1:
			frappe.throw(_("Fields must be a list or tuple when as_list is enabled"))

		self.filters: Filters
		self.or_filters: Filters
		for k, _filters in {
			"filters": filters or Filters(),
			"or_filters": or_filters or Filters(),
		}.items():
			if isinstance(_filters, str):
				_filters = json.loads(_filters)
			if not isinstance(_filters, Filters):
				_filters = Filters(_filters, doctype=self.doctype)
			setattr(self, k, _filters)

		self.docstatus = docstatus or []
		self.group_by = group_by
		self.order_by = order_by
		self.limit_start = cint(limit_start)
		self.limit_page_length = cint(limit_page_length) if limit_page_length else None
		self.with_childnames = with_childnames
		self.debug = debug
		self.join = join
		self.distinct = distinct
		self.as_list = as_list
		self.ignore_ifnull = ignore_ifnull
		self.flags.ignore_permissions = ignore_permissions
		self.user = user or frappe.session.user
		self.update = update
		self.user_settings_fields = copy.deepcopy(self.fields)
		self.run = run
		self.strict = strict
		self.ignore_ddl = ignore_ddl
		self.parent_doctype = parent_doctype

		# for contextual user permission check
		# to determine which user permission is applicable on link field of specific doctype
		self.reference_doctype = reference_doctype or self.doctype

		if user_settings:
			self.user_settings = json.loads(user_settings)

		if is_virtual_doctype(self.doctype):
			from frappe.model.base_document import get_controller

			controller = get_controller(self.doctype)
			if not hasattr(controller, "get_list"):
				return []

			self.parse_args()
			kwargs = {
				"as_list": as_list,
				"with_comment_count": with_comment_count,
				"save_user_settings": save_user_settings,
				"save_user_settings_fields": save_user_settings_fields,
				"pluck": pluck,
				"parent_doctype": parent_doctype,
			} | self.__dict__
			return frappe.call(controller.get_list, args=kwargs, **kwargs)

		self.columns = self.get_table_columns()

		# no table & ignore_ddl, return
		if not self.columns:
			return []

		result = self.build_and_run()

		if sbool(with_comment_count) and not as_list and self.doctype:
			self.add_comment_count(result)

		if save_user_settings:
			self.save_user_settings_fields = save_user_settings_fields
			self.update_user_settings()

		if pluck:
			return [d[pluck] for d in result]

		return result

	def build_and_run(self):
		args = self.prepare_args()
		args.limit = self.add_limit()

		if not args.fields:
			# apply_fieldlevel_read_permissions has likely removed ALL the fields that user asked for
			return []

		if args.conditions:
			args.conditions = "where " + args.conditions

		if self.distinct:
			args.fields = "distinct " + args.fields
			args.order_by = ""  # TODO: recheck for alternative

		# Postgres requires any field that appears in the select clause to also
		# appear in the order by and group by clause
		if frappe.db.db_type == "postgres" and args.order_by and args.group_by:
			args = self.prepare_select_args(args)

		query = """select {fields}
from {tables}
{conditions}
{group_by}
{order_by}
{limit}""".format(**args)

		return frappe.db.sql(
			query,
			as_dict=not self.as_list,
			debug=self.debug,
			update=self.update,
			ignore_ddl=self.ignore_ddl,
			run=self.run,
		)

	def prepare_args(self):
		self.parse_args()
		self.sanitize_fields()
		self.extract_tables()
		self.set_optional_columns()
		self.build_conditions()
		self.apply_fieldlevel_read_permissions()

		args = frappe._dict()

		if self.with_childnames:
			for t in self.tables:
				if t != f"`tab{self.doctype}`":
					self.fields.append(f"{t}.name as '{t[4:-1]}:name'")

		# query dict
		args.tables = self.tables[0]

		# left join parent, child tables
		for child in self.tables[1:]:
			parent_name = cast_name(f"{self.tables[0]}.name")
			args.tables += f" {self.join} {child} on ({child}.parenttype = {frappe.db.escape(self.doctype)} and {child}.parent = {parent_name})"

		# left join link tables
		for link in self.link_tables:
			args.tables += f" {self.join} {link.table_name} {link.table_alias} on ({link.table_alias}.`name` = {self.tables[0]}.`{link.fieldname}`)"

		if self.grouped_or_conditions:
			self.conditions.append(f"({' or '.join(self.grouped_or_conditions)})")

		args.conditions = " and ".join(self.conditions)

		if self.or_conditions:
			args.conditions += (" or " if args.conditions else "") + " or ".join(self.or_conditions)

		self.set_field_tables()
		self.cast_name_fields()

		fields = []

		# Wrapping fields with grave quotes to allow support for sql keywords
		# TODO: Add support for wrapping fields with sql functions and distinct keyword
		for field in self.fields:
			if field is None:
				fields.append("NULL")
				continue

			stripped_field = field.strip().lower()

			if (
				stripped_field[0] in {"`", "*", '"', "'"}
				or "(" in stripped_field
				or "distinct" in stripped_field
			):
				fields.append(field)
			elif "as" in stripped_field.split(" "):
				col, _, new = field.split()
				fields.append(f"`{col}` as {new}")
			else:
				fields.append(f"`{field}`")

		args.fields = ", ".join(fields)

		self.set_order_by(args)

		self.validate_order_by_and_group_by(args.order_by)
		args.order_by = (args.order_by and (" order by " + args.order_by)) or ""

		self.validate_order_by_and_group_by(self.group_by)
		args.group_by = (self.group_by and (" group by " + self.group_by)) or ""

		return args

	def prepare_select_args(self, args):
		order_field = ORDER_BY_PATTERN.sub("", args.order_by)

		if order_field not in args.fields:
			extracted_column = order_column = order_field.replace("`", "")
			if "." in extracted_column:
				extracted_column = extracted_column.split(".")[1]

			args.fields += f", MAX({extracted_column}) as `{order_column}`"
			args.order_by = args.order_by.replace(order_field, f"`{order_column}`")

		return args

	def parse_args(self):
		"""Convert fields and filters from strings to list, dicts."""
		if isinstance(self.fields, str):
			if self.fields == "*":
				self.fields = ["*"]
			else:
				try:
					self.fields = json.loads(self.fields)
				except ValueError:
					self.fields = [f.strip() for f in self.fields.split(",")]

		# remove empty strings / nulls in fields
		self.fields = [f for f in self.fields if f]

		# convert child_table.fieldname to `tabChild DocType`.`fieldname`
		for field in self.fields:
			if "." in field:
				original_field = field
				alias = None
				if " as " in field:
					field, alias = field.split(" as ", 1)
				linked_fieldname, fieldname = field.split(".", 1)
				linked_field = self.get_meta(self.doctype).get_field(linked_fieldname)
				# this is not a link field
				if not linked_field:
					continue
				linked_doctype = linked_field.options
				if linked_field.fieldtype == "Link":
					linked_table = self.append_link_table(linked_doctype, linked_fieldname)
					field = f"{linked_table.table_alias}.`{fieldname}`"
				else:
					field = f"`tab{linked_doctype}`.`{fieldname}`"
				if alias:
					field = f"{field} as {alias}"
				self.fields[self.fields.index(original_field)] = field

	def sanitize_fields(self):
		"""
		regex : ^.*[,();].*
		purpose : The regex will look for malicious patterns like `,`, '(', ')', '@', ;' in each
		                field which may leads to sql injection.
		example :
		        field = "`DocType`.`issingle`, version()"
		As field contains `,` and mysql function `version()`, with the help of regex
		the system will filter out this field.
		"""
		blacklisted_keywords = ["select", "create", "insert", "delete", "drop", "update", "case", "show"]
		blacklisted_functions = [
			"concat",
			"concat_ws",
			"if",
			"ifnull",
			"nullif",
			"coalesce",
			"connection_id",
			"current_user",
			"database",
			"last_insert_id",
			"session_user",
			"system_user",
			"user",
			"version",
			"global",
		]

		def _raise_exception():
			frappe.throw(_("Use of sub-query or function is restricted"), frappe.DataError)

		def _is_query(field):
			if IS_QUERY_PATTERN.match(field):
				_raise_exception()

			elif IS_QUERY_PREDICATE_PATTERN.match(field):
				_raise_exception()

		for field in self.fields:
			lower_field = field.lower().strip()

			if SUB_QUERY_PATTERN.match(field):
				# Check for subquery anywhere in the field, not just at the beginning
				if "(" in lower_field:
					location = lower_field.index("(")
					subquery_token = lower_field[location + 1 :].lstrip().split(" ", 1)[0]
					if any(keyword in subquery_token for keyword in blacklisted_keywords):
						_raise_exception()

				function = lower_field.split("(", 1)[0].rstrip()
				if function in blacklisted_functions:
					frappe.throw(
						_("Use of function {0} in field is restricted").format(function), exc=frappe.DataError
					)

				if "@" in lower_field:
					# prevent access to global variables
					_raise_exception()

			if FIELD_QUOTE_PATTERN.match(field):
				_raise_exception()

			if FIELD_COMMA_PATTERN.match(field):
				_raise_exception()

			_is_query(field)

			if self.strict:
				if STRICT_FIELD_PATTERN.match(field):
					frappe.throw(_("Illegal SQL Query"))

				if STRICT_UNION_PATTERN.match(lower_field):
					frappe.throw(_("Illegal SQL Query"))

	def extract_tables(self):
		"""extract tables from fields"""
		self.tables = [f"`tab{self.doctype}`"]
		sql_functions = [
			"dayofyear(",
			"extract(",
			"locate(",
			"strpos(",
			"count(",
			"sum(",
			"avg(",
		]
		# add tables from fields
		if self.fields:
			for field in self.fields:
				if "tab" not in field or "." not in field or any(x for x in sql_functions if x in field):
					continue

				table_name = field.split(".", 1)[0]

				# Check if table_name is a linked_table alias
				for linked_table in self.link_tables:
					if linked_table.table_alias == table_name:
						table_name = linked_table.table_name
						break

				if table_name.lower().startswith("group_concat("):
					table_name = table_name[13:]
				if table_name.lower().startswith("distinct"):
					table_name = table_name[8:].strip()
				if table_name[0] != "`":
					table_name = f"`{table_name}`"
				if (
					table_name not in self.query_tables
					and table_name not in self.linked_table_aliases.values()
				):
					self.append_table(table_name)

	def append_table(self, table_name):
		self.tables.append(table_name)
		doctype = table_name[4:-1]
		self.check_read_permission(doctype)

	def append_link_table(self, doctype, fieldname):
		for linked_table in self.link_tables:
			if linked_table.doctype == doctype and linked_table.fieldname == fieldname:
				return linked_table

		self.check_read_permission(doctype)
		self.linked_table_counter.update((doctype,))
		linked_table = frappe._dict(
			doctype=doctype,
			fieldname=fieldname,
			table_name=f"`tab{doctype}`",
			table_alias=f"`tab{doctype}_{self.linked_table_counter[doctype]}`",
		)
		self.linked_table_aliases[linked_table.table_alias.replace("`", "")] = linked_table.table_name
		self.link_tables.append(linked_table)
		return linked_table

	def check_read_permission(self, doctype: str, parent_doctype: str | None = None):
		if self.flags.ignore_permissions:
			return

		if doctype not in self.permission_map:
			self._set_permission_map(doctype, parent_doctype)

		return self.permission_map[doctype]

	def _set_permission_map(self, doctype: str, parent_doctype: str | None = None):
		ptype = "select" if frappe.only_has_select_perm(doctype) else "read"
		frappe.has_permission(
			doctype,
			ptype=ptype,
			parent_doctype=parent_doctype or self.doctype,
			throw=True,
			user=self.user,
		)
		self.permission_map[doctype] = ptype

	def set_field_tables(self):
		"""If there are more than one table, the fieldname must not be ambiguous.
		If the fieldname is not explicitly mentioned, set the default table"""

		def _in_standard_sql_methods(field):
			methods = ("count(", "avg(", "sum(", "extract(", "dayofyear(")
			return field.lower().startswith(methods)

		if len(self.tables) > 1 or len(self.link_tables) > 0:
			for idx, field in enumerate(self.fields):
				if field is not None and "." not in field and not _in_standard_sql_methods(field):
					self.fields[idx] = f"{self.tables[0]}.{field}"

	def cast_name_fields(self):
		for i, field in enumerate(self.fields):
			if field is not None:
				self.fields[i] = cast_name(field)

	def get_table_columns(self):
		try:
			return get_table_columns(self.doctype)
		except frappe.db.TableMissingError:
			if self.ignore_ddl:
				return None
			else:
				raise

	def set_optional_columns(self):
		"""Removes optional columns like `_user_tags`, `_comments` etc. if not in table"""

		self.fields[:] = [f for f in self.fields if f not in OPTIONAL_FIELDS or f in self.columns]
		self.filters[:] = [
			f for f in self.filters if f.fieldname not in OPTIONAL_FIELDS or f.fieldname in self.columns
		]

	def build_conditions(self):
		self.conditions = []
		self.grouped_or_conditions = []
		self.build_filter_conditions(self.filters, self.conditions)
		self.build_filter_conditions(self.or_filters, self.grouped_or_conditions)

		# match conditions
		if not self.flags.ignore_permissions:
			match_conditions = self.build_match_conditions()
			if match_conditions:
				self.conditions.append(f"({match_conditions})")

	def build_filter_conditions(self, filters: Filters, conditions: list, ignore_permissions=None):
		"""build conditions from user filters"""
		if ignore_permissions is not None:
			self.flags.ignore_permissions = ignore_permissions

		for f in filters:
			conditions.append(self.prepare_filter_condition(f))

	def remove_field(self, idx: int):
		if self.as_list:
			self.fields[idx] = None
		else:
			self.fields.pop(idx)

	def apply_fieldlevel_read_permissions(self):
		"""Apply fieldlevel read permissions to the query

		Note: Does not apply to `frappe.model.core_doctype_list`

		Remove fields that user is not allowed to read. If `fields=["*"]` is passed, only permitted fields will
		be returned.

		Example:
		        - User has read permission only on `title` for DocType `Note`
		        - Query: fields=["*"]
		        - Result: fields=["title", ...] // will also include Frappe's meta field like `name`, `owner`, etc.
		"""
		from frappe.desk.reportview import extract_fieldnames

		if self.flags.ignore_permissions:
			return

		asterisk_fields = []
		permitted_fields = set(
			get_permitted_fields(
				doctype=self.doctype,
				parenttype=self.parent_doctype,
				permission_type=self.permission_map.get(self.doctype),
				ignore_virtual=True,
			)
		)
		permitted_child_table_fields = {}

		for i, field in enumerate(self.fields):
			# field: 'count(distinct `tabPhoto`.name) as total_count'
			# column: 'tabPhoto.name'
			# field: 'count(`tabPhoto`.name) as total_count'
			# column: 'tabPhoto.name'
			columns = extract_fieldnames(field)
			if not columns:
				continue

			column = columns[0]
			if column == "*" and "*" in field:
				if not in_function("*", field):
					asterisk_fields.append(i)
				continue

			# handle pseudo columns
			if not column or column.isnumeric():
				continue

			# labels / pseudo columns or frappe internals
			if column[0] in {"'", '"'}:
				continue

			doctype = None

			if "." in column:
				table, column = column.split(".", 1)
				doctype = self.linked_table_aliases[table] if table in self.linked_table_aliases else table
				doctype = doctype.replace("`", "").removeprefix("tab")

			# handle child / joined table fields
			if doctype and doctype != self.doctype:
				if wrap_grave_quotes(table) not in self.query_tables:
					raise frappe.PermissionError(doctype)

				if doctype not in permitted_child_table_fields:
					permitted_child_table_fields[doctype] = set(
						get_permitted_fields(
							doctype=doctype,
							parenttype=self.doctype,
							ignore_virtual=True,
						)
					)

				if column in permitted_child_table_fields[doctype] or column in OPTIONAL_FIELDS:
					continue

				self.remove_field(i)
				continue

			if column in OPTIONAL_FIELDS or column in permitted_fields:
				continue

			# field inside function calls / * handles things like count(*)
			elif "(" in field:
				if "*" in field:
					continue
				else:
					for column in columns:
						if column not in permitted_fields:
							self.remove_field(i)
							break
					continue
			# remove if access not allowed
			else:
				self.remove_field(i)

		# handle * fields
		j = 0
		for i in asterisk_fields:
			self.fields[i + j : i + j + 1] = permitted_fields
			j = j + len(permitted_fields) - 1

	def prepare_filter_condition(self, ft: FilterTuple) -> str:
		"""Return a filter condition in the format:

		ifnull(`tabDocType`.`fieldname`, fallback) operator "value"
		"""

		# TODO: refactor

		from frappe.boot import get_additional_filters_from_hooks

		additional_filters_config = get_additional_filters_from_hooks()
		f: FilterTuple = get_filter(self.doctype, ft, additional_filters_config)

		tname = "`tab" + f.doctype + "`"
		if tname not in self.tables:
			self.append_table(tname)

		column_name = cast_name(f.fieldname if "ifnull(" in f.fieldname else f"{tname}.`{f.fieldname}`")

		if f.operator.lower() in additional_filters_config:
			f.update(get_additional_filter_field(additional_filters_config, f, f.value))

		meta = self.get_meta(f.doctype)
		df = meta.get("fields", {"fieldname": f.fieldname})
		df = df[0] if df else None

		# primary key is never nullable, modified is usually indexed by default and always present
		can_be_null = f.fieldname not in ("name", "modified", "creation")

		value = None

		# prepare in condition
		if f.operator.lower() in NestedSetHierarchy:
			# TODO: handle list and tuple
			# if not isinstance(values, (list, tuple)):
			# 	values = values.split(",")
			field = meta.get_field(f.fieldname)
			ref_doctype = field.options if field else f.doctype
			lft, rgt = "", ""
			if f.value:
				lft, rgt = frappe.db.get_value(ref_doctype, f.value, ["lft", "rgt"]) or (0, 0)

			# Get descendants elements of a DocType with a tree structure
			if f.operator.lower() in (
				"descendants of",
				"not descendants of",
				"descendants of (inclusive)",
			):
				nodes = frappe.get_all(
					ref_doctype,
					filters={"lft": [">", lft], "rgt": ["<", rgt]},
					order_by="`lft` ASC",
					pluck="name",
				)
				if f.operator.lower() == "descendants of (inclusive)":
					nodes += [f.value]
			else:
				# Get ancestor elements of a DocType with a tree structure
				nodes = frappe.get_all(
					ref_doctype,
					filters={"lft": ["<", lft], "rgt": [">", rgt]},
					order_by="`lft` DESC",
					pluck="name",
				)

			fallback = "''"
			value = [frappe.db.escape((cstr(v)).strip(), percent=False) for v in nodes]
			if len(value):
				value = f"({', '.join(value)})"
			else:
				value = "('')"

			# changing operator to IN as the above code fetches all the parent / child values and convert into tuple
			# which can be directly used with IN operator to query.
			f.operator = (
				"not in" if f.operator.lower() in ("not ancestors of", "not descendants of") else "in"
			)

		if f.operator.lower() in ("in", "not in"):
			# if values contain '' or falsy values then only coalesce column
			# for `in` query this is only required if values contain '' or values are empty.
			# for `not in` queries we can't be sure as column values might contain null.
			can_be_null &= not getattr(df, "not_nullable", False)
			if f.operator.lower() == "in":
				can_be_null &= not f.value or any(v is None or v == "" for v in f.value)

			if value is None:
				values = f.value or ""
				if isinstance(values, str):
					values = values.split(",")

				fallback = "''"
				value = [frappe.db.escape((cstr(v) or "").strip(), percent=False) for v in values]
				if len(value):
					value = f"({', '.join(value)})"
				else:
					value = "('')"

		else:
			escape = True

			if df and (
				df.fieldtype in ("Check", "Float", "Int", "Currency", "Percent")
				or getattr(df, "not_nullable", False)
			):
				can_be_null = False

			if f.operator.lower() in ("previous", "next", "timespan"):
				date_range = get_date_range(f.operator.lower(), f.value)
				f.operator = "between"
				f.value = date_range
				fallback = f"'{FallBackDateTimeStr}'"

			if f.operator.lower() in (">", ">=") and (
				f.fieldname in ("creation", "modified")
				or (df and (df.fieldtype == "Date" or df.fieldtype == "Datetime"))
			):
				# Null values can never be greater than any non-null value
				can_be_null = False

			if f.operator in (">", "<", ">=", "<=") and (f.fieldname in ("creation", "modified")):
				value = cstr(f.value)
				can_be_null = False
				fallback = f"'{FallBackDateTimeStr}'"

			elif f.operator.lower() in ("between") and (
				f.fieldname in ("creation", "modified")
				or (df and (df.fieldtype == "Date" or df.fieldtype == "Datetime"))
			):
				escape = False
				# Between operator never needs to check for null
				# Explanation: Consider SQL -> `COLUMN between X and Y`
				# Actual computation:
				#     for row in rows:
				#     if Y > row.COLUMN > X:
				#         yield row

				# Since Y and X can't be null, null value in column will never match filter, so
				# coalesce is extra cost that prevents index usage
				can_be_null = False

				value = get_between_date_filter(f.value, df)
				fallback = f"'{FallBackDateTimeStr}'"

			elif f.operator.lower() == "is":
				fallback = "''"
				if f.value == "set":
					f.operator = "!="
					can_be_null = False
				elif f.value == "not set":
					f.operator = "="
					can_be_null = not getattr(df, "not_nullable", False)
				f.value = value = ""

			elif df and df.fieldtype == "Date":
				value = frappe.db.format_date(f.value)
				fallback = "'0001-01-01'"

			elif (df and df.fieldtype == "Datetime") or isinstance(f.value, datetime.datetime):
				value = frappe.db.format_datetime(f.value)
				fallback = f"'{FallBackDateTimeStr}'"

			elif df and df.fieldtype == "Time":
				value = get_time(f.value).strftime("%H:%M:%S.%f")
				fallback = "'00:00:00'"

			elif f.operator.lower() in ("like", "not like") or (
				isinstance(f.value, str)
				and (not df or df.fieldtype not in ["Float", "Int", "Currency", "Percent", "Check"])
			):
				value = "" if f.value is None else f.value
				fallback = "''"

				if f.operator.lower() in ("like", "not like") and isinstance(value, str):
					# because "like" uses backslash (\) for escaping
					value = value.replace("\\", "\\\\").replace("%", "%%")

			elif f.operator == "=" and df and df.fieldtype in ("Link", "Data", "Dynamic Link"):
				value = cstr(f.value)
				fallback = "''"

			elif f.fieldname == "name":
				value = f.value if f.value is not None else ""
				fallback = "''"

			elif (
				df
				and (db_type := cstr(frappe.db.type_map.get(df.fieldtype, " ")[0]))
				and db_type in ("varchar", "text", "longtext", "smalltext", "json")
			):
				value = cstr(f.value)
				fallback = "''"

			else:
				value = flt(f.value)
				fallback = 0

			if isinstance(f.value, Column):
				can_be_null = False  # added to avoid the ifnull/coalesce addition
				quote = '"' if frappe.conf.db_type == "postgres" else "`"
				value = f"{tname}.{quote}{f.value.name}{quote}"

			# escape value
			elif escape and isinstance(value, str):
				value = f"{frappe.db.escape(value, percent=False)}"

		if (
			self.ignore_ifnull
			or not can_be_null
			or (f.value and f.operator.lower() in ("=", "like"))
			or "ifnull(" in column_name.lower()
		):
			if f.operator.lower() == "like" and frappe.conf.get("db_type") == "postgres":
				f.operator = "ilike"
			condition = f"{column_name} {f.operator} {value}"
		else:
			# PERF: try to transform ifnull into two conditions, this way query plan can use index
			# intersection instead of full table scans.
			if fallback == value and f.operator == "=":
				condition = f"( {column_name} is NULL OR {column_name} {f.operator} {value} )"
			elif fallback == value and f.operator == "!=":
				# NULL != anything is always NULL, so won't match
				condition = f"{column_name} {f.operator} {value}"
			else:
				condition = f"ifnull({column_name}, {fallback}) {f.operator} {value}"

		return condition

	def build_match_conditions(self, as_condition=True) -> str | list:
		"""add match conditions if applicable"""
		self.match_filters = []
		self.match_conditions = []
		only_if_shared = False
		if not self.user:
			self.user = frappe.session.user

		if not self.tables:
			self.extract_tables()

		role_permissions = frappe.permissions.get_role_permissions(self.doctype_meta, user=self.user)
		if (
			not self.doctype_meta.istable
			and not role_permissions.get("select")
			and not role_permissions.get("read")
			and not self.flags.ignore_permissions
			and not has_any_user_permission_for_doctype(self.doctype, self.user, self.reference_doctype)
		):
			only_if_shared = True
			self.shared = frappe.share.get_shared(self.doctype, self.user)
			if not self.shared:
				frappe.throw(_("No permission to read {0}").format(_(self.doctype)), frappe.PermissionError)
			else:
				self.conditions.append(self.get_share_condition())

		else:
			# skip user perm check if owner constraint is required
			if requires_owner_constraint(role_permissions):
				self._fetch_shared_documents = True
				self.match_conditions.append(
					f"`tab{self.doctype}`.`owner` = {frappe.db.escape(self.user, percent=False)}"
				)

			# add user permission only if role has read perm
			elif role_permissions.get("read") or role_permissions.get("select"):
				# get user permissions
				user_permissions = frappe.permissions.get_user_permissions(self.user)
				self.add_user_permissions(user_permissions)

			# Only when full read access is not present fetch shared docuemnts.
			# This is done to avoid extra query.
			# Only following cases can require explicit addition of shared documents.
			#    1. DocType has if_owner constraint and hence can't see shared documents
			#    2. DocType has user permissions and hence can't see shared documents
			if self._fetch_shared_documents:
				self.shared = frappe.share.get_shared(self.doctype, self.user)

		if as_condition:
			conditions = ""
			if self.match_conditions:
				# will turn out like ((blog_post in (..) and blogger in (...)) or (blog_category in (...)))
				conditions = "((" + ") or (".join(self.match_conditions) + "))"

			doctype_conditions = self.get_permission_query_conditions()
			if doctype_conditions:
				conditions += (" and " + doctype_conditions) if conditions else doctype_conditions

			# share is an OR condition, if there is a role permission
			if not only_if_shared and self.shared and conditions:
				conditions = f"(({conditions}) or ({self.get_share_condition()}))"

			return conditions

		else:
			return self.match_filters

	def get_share_condition(self):
		return (
			cast_name(f"`tab{self.doctype}`.name")
			+ f" in ({', '.join(frappe.db.escape(s, percent=False) for s in self.shared)})"
		)

	def add_user_permissions(self, user_permissions):
		doctype_link_fields = self.doctype_meta.get_link_fields()

		# append current doctype with fieldname as 'name' as first link field
		doctype_link_fields.append(
			dict(
				options=self.doctype,
				fieldname="name",
			)
		)

		match_filters = {}
		match_conditions = []
		for df in doctype_link_fields:
			if df.get("ignore_user_permissions"):
				continue

			user_permission_values = user_permissions.get(df.get("options"), {})

			if user_permission_values:
				docs = []
				if frappe.get_system_settings("apply_strict_user_permissions"):
					condition = ""
				else:
					empty_value_condition = cast_name(
						f"ifnull(`tab{self.doctype}`.`{df.get('fieldname')}`, '')=''"
					)
					condition = empty_value_condition + " or "

				for permission in user_permission_values:
					if not permission.get("applicable_for"):
						docs.append(permission.get("doc"))

					# append docs based on user permission applicable on reference doctype
					# this is useful when getting list of docs from a link field
					# in this case parent doctype of the link
					# will be the reference doctype

					elif df.get("fieldname") == "name" and self.reference_doctype:
						if permission.get("applicable_for") == self.reference_doctype:
							docs.append(permission.get("doc"))

					elif permission.get("applicable_for") == self.doctype:
						docs.append(permission.get("doc"))

				if docs:
					values = ", ".join(frappe.db.escape(doc, percent=False) for doc in docs)
					condition += cast_name(f"`tab{self.doctype}`.`{df.get('fieldname')}`") + f" in ({values})"
					match_conditions.append(f"({condition})")
					match_filters[df.get("options")] = docs

		if match_conditions:
			self._fetch_shared_documents = True
			self.match_conditions.append(" and ".join(match_conditions))

		if match_filters:
			self._fetch_shared_documents = True
			self.match_filters.append(match_filters)

	def get_permission_query_conditions(self) -> str:
		conditions = []
		hooks = frappe.get_hooks("permission_query_conditions", {})
		condition_methods = hooks.get(self.doctype, []) + hooks.get("*", [])
		for method in condition_methods:
			if c := frappe.call(frappe.get_attr(method), self.user, doctype=self.doctype):
				conditions.append(c)

		if permission_script_name := get_server_script_map().get("permission_query", {}).get(self.doctype):
			script = frappe.get_doc("Server Script", permission_script_name)
			if condition := script.get_permission_query_conditions(self.user):
				conditions.append(condition)

		return " and ".join(conditions) if conditions else ""

	def set_order_by(self, args):
		if self.order_by and self.order_by != "KEEP_DEFAULT_ORDERING":
			args.order_by = self.order_by
		else:
			args.order_by = ""

			# don't add order by from meta if a mysql group function is used without group by clause
			group_function_without_group_by = (
				len(self.fields) == 1
				and (
					self.fields[0].lower().startswith("count(")
					or self.fields[0].lower().startswith("min(")
					or self.fields[0].lower().startswith("max(")
					or self.fields[0].lower().startswith("sum(")
					or self.fields[0].lower().startswith("avg(")
				)
				and not self.group_by
			)

			if not group_function_without_group_by:
				sort_field = sort_order = None
				if self.doctype_meta.sort_field and "," in self.doctype_meta.sort_field:
					# multiple sort given in doctype definition
					# Example:
					# `idx desc, creation desc`
					# will covert to
					# `tabItem`.`idx` desc, `tabItem`.`creation` desc
					args.order_by = ", ".join(
						f"`tab{self.doctype}`.`{f_split[0].strip()}` {f_split[1].strip()}"
						for f in self.doctype_meta.sort_field.split(",")
						if (f_split := f.split(maxsplit=2))
					)
				else:
					sort_field = self.doctype_meta.sort_field or "creation"
					sort_order = (self.doctype_meta.sort_field and self.doctype_meta.sort_order) or "desc"
					if self.order_by:
						args.order_by = (
							f"`tab{self.doctype}`.`{sort_field or 'creation'}` {sort_order or 'desc'}"
						)

	def validate_order_by_and_group_by(self, parameters: str):
		"""Check order by, group by so that atleast one column is selected and does not have subquery"""
		if not parameters:
			return

		blacklisted_sql_functions = {
			"sleep",
		}
		_lower = parameters.lower()

		if "select" in _lower and "from" in _lower:
			frappe.throw(_("Cannot use sub-query in order by"))

		if ORDER_GROUP_PATTERN.match(_lower):
			frappe.throw(_("Illegal SQL Query"))

		for field in parameters.split(","):
			field = field.strip()
			function = field.split("(", 1)[0].rstrip().lower()
			full_field_name = "." in field and field.startswith("`tab")

			if full_field_name:
				tbl = field.split(".", 1)[0]
				if tbl not in self.tables:
					if tbl.startswith("`"):
						tbl = tbl[4:-1]
					frappe.throw(_("Please select atleast 1 column from {0} to sort/group").format(tbl))

			# Check if the function is used anywhere in the field
			if any(func in function for func in blacklisted_sql_functions):
				frappe.throw(_("Cannot use {0} in order/group by").format(function))

	def add_limit(self):
		if self.limit_page_length:
			return f"limit {self.limit_page_length} offset {self.limit_start}"
		else:
			return ""

	def add_comment_count(self, result):
		for r in result:
			if not r.name:
				continue

			r._comment_count = 0
			if "_comments" in r and r._comments:
				# perf: Avoid parsing _comments, they can be huge and this is just a "UX feature"
				r._comment_count = r._comments.count('"comment"')

	def update_user_settings(self):
		# update user settings if new search
		if not self.save_user_settings_fields and not getattr(self, "user_settings", None):
			# Nothing has changed or needs to be changed
			return

		user_settings = json.loads(get_user_settings(self.doctype))

		if hasattr(self, "user_settings"):
			user_settings.update(self.user_settings)

		if self.save_user_settings_fields:
			user_settings["fields"] = self.user_settings_fields

		update_user_settings(self.doctype, user_settings)


def cast_name(column: str) -> str:
	"""Casts name field to varchar for postgres

	Handles majorly 4 cases:
	1. locate
	2. strpos
	3. ifnull
	4. coalesce

	Uses regex substitution.

	Example:
	input - "ifnull(`tabBlog Post`.`name`, '')=''"
	output - "ifnull(cast(`tabBlog Post`.`name` as varchar), '')=''" """
	if frappe.db.db_type != "postgres":
		return column

	kwargs = {"string": column}
	if "cast(" not in column.lower() and "::" not in column:
		if LOCATE_PATTERN.search(**kwargs):
			return LOCATE_CAST_PATTERN.sub(r"locate(\1, cast(\2 as varchar))", **kwargs)

		elif match := FUNC_IFNULL_PATTERN.search(**kwargs):
			func = match.groups()[0]
			return re.sub(rf"{func}\(\s*([`\"]?name[`\"]?)\s*,", rf"{func}(cast(\1 as varchar),", **kwargs)

		return CAST_VARCHAR_PATTERN.sub(r"cast(\1 as varchar)", **kwargs)

	return column


def check_parent_permission(parent, child_doctype):
	if parent:
		# User may pass fake parent and get the information from the child table
		if child_doctype and not (
			frappe.db.exists("DocField", {"parent": parent, "options": child_doctype})
			or frappe.db.exists("Custom Field", {"dt": parent, "options": child_doctype})
		):
			raise frappe.PermissionError

		if frappe.permissions.has_permission(parent):
			return

	# Either parent not passed or the user doesn't have permission on parent doctype of child table!
	raise frappe.PermissionError


def get_order_by(doctype, meta):
	order_by = ""

	sort_field = sort_order = None
	if meta.sort_field and "," in meta.sort_field:
		# multiple sort given in doctype definition
		# Example:
		# `idx desc, creation desc`
		# will covert to
		# `tabItem`.`idx` desc, `tabItem`.`creation` desc
		order_by = ", ".join(
			f"`tab{doctype}`.`{f_split[0].strip()}` {f_split[1].strip()}"
			for f in meta.sort_field.split(",")
			if (f_split := f.split(maxsplit=2))
		)

	else:
		sort_field = meta.sort_field or "creation"
		sort_order = (meta.sort_field and meta.sort_order) or "desc"
		order_by = f"`tab{doctype}`.`{sort_field}` {sort_order}"

	return order_by


def has_any_user_permission_for_doctype(doctype, user, applicable_for):
	user_permissions = frappe.permissions.get_user_permissions(user=user)
	doctype_user_permissions = user_permissions.get(doctype, [])

	for permission in doctype_user_permissions:
		if not permission.applicable_for or permission.applicable_for == applicable_for:
			return True

	return False


def get_between_date_filter(value, df=None):
	"""Handle datetime filter bounds for between filter values.

	If date is passed but fieldtype is datetime then
	        from part is converted to start of day and to part is converted to end of day.
	If any of filter part (to or from) are missing then:
	        start or end of current day is assumed as fallback.
	If fieldtypes match with filter values then:
	        no change is applied.
	"""

	fieldtype = (df and df.fieldtype) or "Datetime"

	from_date = frappe.utils.nowdate()
	to_date = frappe.utils.nowdate()

	if value and isinstance(value, list | tuple):
		if len(value) >= 1:
			from_date = value[0]
		if len(value) >= 2:
			to_date = value[1]

	# if filter value is date but fieldtype is datetime:
	if fieldtype == "Datetime":
		from_date = _convert_type_for_between_filters(from_date, set_time=datetime.time())
		to_date = _convert_type_for_between_filters(to_date, set_time=datetime.time(23, 59, 59, 999999))

	# If filter value is already datetime, do nothing.
	if fieldtype == "Datetime":
		cond = f"'{frappe.db.format_datetime(from_date)}' AND '{frappe.db.format_datetime(to_date)}'"
	else:
		cond = f"'{frappe.db.format_date(from_date)}' AND '{frappe.db.format_date(to_date)}'"

	return cond


def _convert_type_for_between_filters(
	value: DateTimeLikeObject, set_time: datetime.time
) -> datetime.datetime:
	if isinstance(value, str):
		if " " in value.strip():
			value = get_datetime(value)
		else:
			value = getdate(value)

	if isinstance(value, datetime.datetime):
		return value
	elif isinstance(value, datetime.date):
		return datetime.datetime.combine(value, set_time)

	return value


def get_additional_filter_field(additional_filters_config, f, value):
	additional_filter = additional_filters_config[f.operator.lower()]
	f = frappe._dict(frappe.get_attr(additional_filter["get_field"])())
	if f.query_value:
		for option in f.options:
			option = frappe._dict(option)
			if option.value == value:
				f.value = option.query_value
	return f


def get_date_range(operator: str, value: str):
	timespan_map = {
		"1 week": "week",
		"1 month": "month",
		"3 months": "quarter",
		"6 months": "6 months",
		"1 year": "year",
	}
	period_map = {
		"previous": "last",
		"next": "next",
	}

	if operator != "timespan":
		timespan = f"{period_map[operator]} {timespan_map[value]}"
	else:
		timespan = value

	return get_timespan_date_range(timespan)


def requires_owner_constraint(role_permissions):
	"""Return True if "select" or "read" isn't available without being creator."""

	if not role_permissions.get("has_if_owner_enabled"):
		return

	if_owner_perms = role_permissions.get("if_owner")
	if not if_owner_perms:
		return

	# has select or read without if owner, no need for constraint
	for perm_type in ("select", "read"):
		if role_permissions.get(perm_type) and perm_type not in if_owner_perms:
			return

	# not checking if either select or read if present in if_owner_perms
	# because either of those is required to perform a query
	return True


def wrap_grave_quotes(table: str) -> str:
	if table[0] != "`":
		table = f"`{table}`"
	return table


def is_plain_field(field: str) -> bool:
	for char in field:
		if char in SPECIAL_FIELD_CHARS:
			return False
	return True


def in_function(substr: str, field: str) -> bool:
	try:
		return substr in field and field.index("(") < field.index(substr) < field.index(")")
	except ValueError:
		return False


def strip_alias(field: str) -> str:
	# Note: Currently only supports aliases that use the " AS " syntax
	if " as " in field.lower():
		return field.split(" as ", 1)[0]
	return field
