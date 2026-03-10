import re
from ast import literal_eval
from functools import lru_cache
from types import BuiltinFunctionType
from typing import TYPE_CHECKING

import sqlparse
from pypika.queries import QueryBuilder, Table

import frappe
from frappe import _
from frappe.database.operator_map import OPERATOR_MAP
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.database.utils import DefaultOrderBy, get_doctype_name
from frappe.query_builder import Criterion, Field, Order, functions
<<<<<<< HEAD
from frappe.query_builder.functions import Function, SqlFunctions
from frappe.query_builder.utils import PseudoColumnMapper
from frappe.utils.data import MARIADB_SPECIFIC_COMMENT
=======
from frappe.query_builder.custom import Month, MonthName, Quarter

CORE_DOCTYPES = DOCTYPES_FOR_DOCTYPE | frozenset(
	(
		"Custom Field",
		"Property Setter",
		"Module Def",
		"__Auth",
		"__global_search",
		"Singles",
		"Sessions",
		"Series",
	)
)


def _apply_date_field_filter_conversion(value, operator: str, doctype: str, field):
	"""Apply datetime to date conversion for Date fieldtype filters.

	This matches db_query behavior where datetime values are truncated to dates
	when filtering on Date fields, for all operators (not just 'between').

	Args:
		value: The filter value (can be datetime, tuple of datetimes, or other)
		operator: The operator being used (between, >, <, etc.)
		doctype: The doctype to get field metadata from
		field: The field name or pypika Field object

	Returns:
		The converted value with datetimes converted to dates if field is Date type
	"""
	try:
		# Extract field name
		if "." in str(field):
			field = field.split(".")[-1]

		# Skip querying meta for core doctypes to avoid recursion
		if doctype in CORE_DOCTYPES:
			meta = None
		else:
			meta = frappe.get_meta(doctype)

		if meta is None:
			return value

		df = meta.get_field(field)
		if df is None or df.fieldtype != "Date":
			return value

		# Convert datetime to date if the fieldtype is date
		if operator.lower() == "between" and isinstance(value, list | tuple) and len(value) == 2:
			from_val, to_val = value
			if isinstance(from_val, datetime.datetime):
				from_val = from_val.date()
			if isinstance(to_val, datetime.datetime):
				to_val = to_val.date()
			return (from_val, to_val)
		elif isinstance(value, datetime.datetime):
			return value.date()

	except AttributeError, TypeError, KeyError:
		pass

	return value


def _apply_datetime_field_filter_conversion(between_values: tuple | list, doctype: str, field) -> tuple:
	"""Apply date to datetime conversion for Datetime fields with 'between' operator.

	Args:
		between_values: Tuple/list of two values [from, to] for between filter
		doctype: DocType name
		field: Field name or pypika Field object

	Returns:
		Tuple with dates expanded to datetime ranges for Datetime fields
	"""
	from frappe.model.db_query import _convert_type_for_between_filters

	# Extract field name
	field_name = field
	if "." in str(field):
		field_name = field.split(".")[-1]

	# Skip querying meta for core doctypes to avoid recursion
	if doctype in CORE_DOCTYPES:
		df = None
	else:
		meta = frappe.get_meta(doctype)
		df = meta.get_field(field_name) if meta else None

	# Standard datetime fields or Datetime fieldtype
	if not (field_name in ("creation", "modified") or (df and df.fieldtype == "Datetime")):
		return between_values

	from_val, to_val = between_values

	# Convert to datetime using db_query helper (handles strings, dates, datetimes)
	from_val = _convert_type_for_between_filters(from_val, set_time=datetime.time())
	to_val = _convert_type_for_between_filters(to_val, set_time=datetime.time(23, 59, 59, 999999))

	return (from_val, to_val)

>>>>>>> a084bad5d5 (fix(apply_field_permissions): improve checks)

if TYPE_CHECKING:
	from frappe.query_builder import DocType

TAB_PATTERN = re.compile("^tab")
WORDS_PATTERN = re.compile(r"\w+")
BRACKETS_PATTERN = re.compile(r"\(.*?\)|$")
SQL_FUNCTIONS = [sql_function.value for sql_function in SqlFunctions]
COMMA_PATTERN = re.compile(r",\s*(?![^()]*\))")


class Engine:
	def get_query(
		self,
		table: str | Table,
		fields: list | tuple | None = None,
		filters: dict[str, str | int] | str | int | list[list | str | int] | None = None,
		order_by: str | None = None,
		group_by: str | None = None,
		limit: int | None = None,
		offset: int | None = None,
		distinct: bool = False,
		for_update: bool = False,
		update: bool = False,
		into: bool = False,
		delete: bool = False,
		*,
		validate_filters: bool = False,
		skip_locked: bool = False,
		wait: bool = True,
	) -> QueryBuilder:
		self.is_mariadb = frappe.db.db_type == "mariadb"
		self.is_postgres = frappe.db.db_type == "postgres"
		self.validate_filters = validate_filters

		if isinstance(table, Table):
			self.table = table
			self.doctype = get_doctype_name(table.get_sql())
		else:
			self.doctype = table
			self.table = frappe.qb.DocType(table)

		if update:
			self.query = frappe.qb.update(self.table)
		elif into:
			self.query = frappe.qb.into(self.table)
		elif delete:
			self.query = frappe.qb.from_(self.table).delete()
		else:
			self.query = frappe.qb.from_(self.table)
			self.apply_fields(fields)

		self.apply_filters(filters)
		self.apply_order_by(order_by)

		if limit:
			self.query = self.query.limit(limit)

		if offset:
			self.query = self.query.offset(offset)

		if distinct:
			self.query = self.query.distinct()

		if for_update:
			self.query = self.query.for_update(skip_locked=skip_locked, nowait=not wait)

		if group_by:
			self.query = self.query.groupby(group_by)

		return self.query

	def apply_fields(self, fields):
		# add fields
		self.fields = self.parse_fields(fields)
		if not self.fields:
			self.fields = [self.table.name]

		self.query._child_queries = []
		has_select_field = False
		for field in self.fields:
			if isinstance(field, DynamicTableField):
<<<<<<< HEAD
				self.query = field.apply_select(self.query)
=======
				self.query = field.apply_select(self.query, engine=self)
				has_select_field = True
>>>>>>> 72007f636d (fix(query): ensure atleast name is always selected)
			elif isinstance(field, ChildQuery):
				self.query._child_queries.append(field)
			else:
				self.query = self.query.select(field)
				has_select_field = True

		if not has_select_field:
			self.query = self.query.select(self.table.name)

	def apply_filters(
		self,
		filters: dict[str, str | int] | str | int | list[list | str | int] | None = None,
	):
		if filters is None:
			return

		if isinstance(filters, str | int):
			filters = {"name": str(filters)}

		if isinstance(filters, Criterion):
			self.query = self.query.where(filters)

		elif isinstance(filters, dict):
			self.apply_dict_filters(filters)

		elif isinstance(filters, list | tuple):
			if all(isinstance(d, str | int) for d in filters) and len(filters) > 0:
				self.apply_dict_filters({"name": ("in", filters)})
			else:
				for filter in filters:
					if isinstance(filter, str | int | Criterion | dict):
						self.apply_filters(filter)
					elif isinstance(filter, list | tuple):
						self.apply_list_filters(filter)

	def apply_list_filters(self, filter: list):
		if len(filter) == 2:
			field, value = filter
			self._apply_filter(field, value)
		elif len(filter) == 3:
			field, operator, value = filter
			self._apply_filter(field, value, operator)
		elif len(filter) == 4:
			doctype, field, operator, value = filter
			self._apply_filter(field, value, operator, doctype)

	def apply_dict_filters(self, filters: dict[str, str | int | list]):
		for field, value in filters.items():
			operator = "="
			if isinstance(value, list | tuple):
				operator, value = value

			self._apply_filter(field, value, operator)

	def _apply_filter(
		self, field: str, value: str | int | list | None, operator: str = "=", doctype: str | None = None
	):
		_field = field
		_value = value
		_operator = operator

		if not isinstance(_field, str):
			pass
		elif not self.validate_filters and (dynamic_field := DynamicTableField.parse(field, self.doctype)):
			# apply implicit join if link field's field is referenced
			self.query = dynamic_field.apply_join(self.query)
			_field = dynamic_field.field
		elif self.validate_filters and SPECIAL_CHAR_PATTERN.search(_field):
			frappe.throw(_("Invalid filter: {0}").format(_field))
		elif not doctype or doctype == self.doctype:
			_field = self.table[field]
		elif doctype:
			_field = frappe.qb.DocType(doctype)[field]

		# apply implicit join if child table is referenced
		if doctype and doctype != self.doctype:
			meta = frappe.get_meta(doctype)
			table = frappe.qb.DocType(doctype)
			if meta.istable and not self.query.is_joined(table):
				self.query = self.query.left_join(table).on(
					(table.parent == self.table.name) & (table.parenttype == self.doctype)
				)

		if isinstance(_value, bool):
			_value = int(_value)

		elif not _value and isinstance(_value, list | tuple):
			_value = ("",)

		# Nested set
		if _operator in OPERATOR_MAP["nested_set"]:
			hierarchy = _operator
			docname = _value

			_df = frappe.get_meta(self.doctype).get_field(field)
			ref_doctype = _df.options if _df else self.doctype

			nodes = get_nested_set_hierarchy_result(ref_doctype, docname, hierarchy)
			operator_fn = (
				OPERATOR_MAP["not in"]
				if hierarchy in ("not ancestors of", "not descendants of")
				else OPERATOR_MAP["in"]
			)
			if nodes:
				self.query = self.query.where(operator_fn(_field, nodes))
			else:
				self.query = self.query.where(operator_fn(_field, ("",)))
			return

		operator_fn = OPERATOR_MAP[_operator.casefold()]
		if _value is None and isinstance(_field, Field):
<<<<<<< HEAD
			self.query = self.query.where(_field.isnull())
=======
			if operator_fn == builtin_operator.ne:
				filter_field_name = (
					field
					if isinstance(field, str)
					else (_field.name if hasattr(_field, "name") else str(_field))
				)
				if "." in filter_field_name:
					filter_field_name = filter_field_name.split(".")[-1]

				target_doctype = doctype or self.doctype
				fallback_sql = self._get_ifnull_fallback(target_doctype, filter_field_name)

				if fallback_sql == "''":
					fallback_value = ""
				elif fallback_sql.startswith("'") and fallback_sql.endswith("'"):
					fallback_value = fallback_sql[1:-1]
				else:
					try:
						fallback_value = int(fallback_sql)
					except ValueError, TypeError:
						fallback_value = fallback_sql

				return operator_fn(_field, ValueWrapper(fallback_value))
			else:
				return _field.isnull()
>>>>>>> a084bad5d5 (fix(apply_field_permissions): improve checks)
		else:
			self.query = self.query.where(operator_fn(_field, _value))

	def get_function_object(self, field: str) -> "Function":
		"""Expects field to look like 'SUM(*)' or 'name' or something similar. Returns PyPika Function object"""
		func = field.split("(", maxsplit=1)[0].capitalize()
		args_start, args_end = len(func) + 1, field.index(")")
		args = field[args_start:args_end].split(",")

		_, alias = field.split(" as ") if " as " in field else (None, None)

		to_cast = "*" not in args
		_args = []

<<<<<<< HEAD
		for arg in args:
			initial_fields = literal_eval_(arg.strip())
			if to_cast:
				has_primitive_operator = False
				for _operator in OPERATOR_MAP.keys():
					if _operator in initial_fields:
						operator_mapping = OPERATOR_MAP[_operator]
						# Only perform this if operator is of primitive type.
						if isinstance(operator_mapping, BuiltinFunctionType):
							has_primitive_operator = True
							field = operator_mapping(
								*map(
									lambda field: (
										Field(field.strip())
										if "`" not in field
										else PseudoColumnMapper(field.strip())
									),
									arg.split(_operator),
								),
							)
=======
			if self._should_apply_ifnull(target_doctype, filter_field_name, _operator, _value):
				fallback_sql = self._get_ifnull_fallback(target_doctype, filter_field_name)
				if fallback_sql == "''":
					fallback_value = ""
				elif fallback_sql.startswith("'") and fallback_sql.endswith("'"):
					fallback_value = fallback_sql[1:-1]
				else:
					try:
						fallback_value = int(fallback_sql)
					except ValueError, TypeError:
						fallback_value = fallback_sql
>>>>>>> a084bad5d5 (fix(apply_field_permissions): improve checks)

				field = (
					(
						Field(initial_fields)
						if "`" not in initial_fields
						else PseudoColumnMapper(initial_fields)
					)
					if not has_primitive_operator
					else field
				)
			else:
				field = initial_fields

			_args.append(field)

		if alias and "`" in alias:
			alias = alias.replace("`", "")
		try:
			if func.casefold() == "now":
				return getattr(functions, func)()
			return getattr(functions, func)(*_args, alias=alias or None)
		except AttributeError:
			# Fall back for functions not present in `SqlFunctions``
			return Function(func, *_args, alias=alias or None)

	def sanitize_fields(self, fields: str | list | tuple):
		if isinstance(fields, list | tuple):
			return [
				_sanitize_field(field, self.is_mariadb) if isinstance(field, str) else field
				for field in fields
			]
		elif isinstance(fields, str):
			return _sanitize_field(fields, self.is_mariadb)
		return fields

	def parse_string_field(self, field: str):
		if field == "*":
			return self.table.star
		alias = None
		if " as " in field:
			field, alias = field.split(" as ")
		if "`" in field:
			if alias:
				return PseudoColumnMapper(f"{field} {alias}")
			return PseudoColumnMapper(field)
		if alias:
			return self.table[field].as_(alias)
		return self.table[field]

	def parse_fields(self, fields: str | list | tuple | None) -> list:
		if not fields:
			return []
		fields = self.sanitize_fields(fields)
		if isinstance(fields, list | tuple | set) and None in fields and Field not in fields:
			return []

		if not isinstance(fields, list | tuple):
			fields = [fields]

		def parse_field(field: str):
			if has_function(field):
				return self.get_function_object(field)
			elif parsed := DynamicTableField.parse(field, self.doctype):
				return parsed
			else:
				return self.parse_string_field(field)

		_fields = []
		for field in fields:
			if isinstance(field, Criterion):
				_fields.append(field)
			elif isinstance(field, dict):
				for child_field, fields in field.items():
					_fields.append(ChildQuery(child_field, fields, self.doctype))
			elif isinstance(field, str):
				if "," in field:
					field = field.casefold() if "`" not in field else field
					field_list = COMMA_PATTERN.split(field)
					for field in field_list:
						if _field := field.strip():
							_fields.append(parse_field(_field))
				else:
					_fields.append(parse_field(field))

		return _fields

	def apply_order_by(self, order_by: str | None):
		if not order_by or order_by == DefaultOrderBy:
			return
		for declaration in order_by.split(","):
			if _order_by := declaration.strip():
				parts = _order_by.split(" ")
				order_field, order_direction = parts[0], parts[1] if len(parts) > 1 else "desc"
				order_direction = Order.asc if order_direction.lower() == "asc" else Order.desc
				self.query = self.query.orderby(order_field, order=order_direction)


class Permission:
	@classmethod
	def check_permissions(cls, query, **kwargs):
		if not isinstance(query, str):
			query = query.get_sql()

		doctype = cls.get_tables_from_query(query)
		if isinstance(doctype, str):
			doctype = [doctype]

<<<<<<< HEAD
		for dt in doctype:
			dt = TAB_PATTERN.sub("", dt)
			if not frappe.has_permission(
				dt,
				"select",
				user=kwargs.get("user"),
				parent_doctype=kwargs.get("parent_doctype"),
			) and not frappe.has_permission(
				dt,
				"read",
				user=kwargs.get("user"),
				parent_doctype=kwargs.get("parent_doctype"),
=======
				if direction and direction not in valid_directions:
					frappe.throw(
						_("Invalid direction in Order By: {0}. Must be 'ASC' or 'DESC'.").format(direction),
						ValueError,
					)

		return parsed_order_fields

	def check_read_permission(self):
		"""Check if user has read permission on the doctype"""

		def has_permission(ptype):
			return frappe.has_permission(
				self.doctype,
				ptype,
				user=self.user,
				parent_doctype=self.parent_doctype,
			)

		if not has_permission("select") and not has_permission("read"):
			self._raise_permission_error()

	def _raise_permission_error(self, doctype=None):
		frappe.throw(
			_("Insufficient Permission for {0}").format(frappe.bold(doctype or self.doctype)),
			frappe.PermissionError,
		)

	def apply_field_permissions(self):
		"""Filter the list of fields based on permlevel."""
		allowed_fields = []
		parent_permission_type = self.get_permission_type(self.doctype)

		permitted_fields_set = self._get_cached_permitted_fields(
			self.doctype, self.parent_doctype, parent_permission_type
		)

		for field in self.fields:
			if isinstance(field, ChildTableField):
				if parent_permission_type == "select":
					# Skip child table fields if parent permission is only 'select'
					continue

				if field.parent_fieldname:
					parent_meta = frappe.get_meta(self.doctype)
					if parent_meta.get_field(
						field.parent_fieldname
					).permlevel not in parent_meta.get_permlevel_access(
						parent_permission_type, user=self.user
					):
						continue

				# Cache permitted fields for child doctypes if accessed multiple times
				permitted_child_fields_set = self._get_cached_permitted_fields(
					field.doctype,
					field.parent_doctype,
					self.get_permission_type(field.doctype, field.parent_doctype),
				)
				# Check permission for the specific field in the child table
				if field.fieldname in permitted_child_fields_set:
					allowed_fields.append(field)
			elif isinstance(field, LinkTableField):
				# Check permission for the link field *in the parent doctype*
				if field.link_fieldname in permitted_fields_set:
					# Also check if user has permission to read/select the target doctype
					target_doctype = field.doctype
					has_target_perm = frappe.has_permission(
						target_doctype, "select", user=self.user
					) or frappe.has_permission(target_doctype, "read", user=self.user)

					if has_target_perm:
						# Finally, check if the specific field *in the target doctype* is permitted
						permitted_target_fields_set = self._get_cached_permitted_fields(
							target_doctype, None, self.get_permission_type(target_doctype)
						)
						if field.fieldname in permitted_target_fields_set:
							allowed_fields.append(field)
			elif isinstance(field, ChildQuery):
				if parent_permission_type == "select":
					# Skip child queries if parent permission is only 'select'
					continue

				parent_meta = frappe.get_meta(self.doctype)
				if parent_meta.get_field(field.fieldname).permlevel not in parent_meta.get_permlevel_access(
					parent_permission_type, user=self.user
				):
					continue

				# Cache permitted fields for the child doctype of the query
				permitted_child_fields_set = self._get_cached_permitted_fields(
					field.doctype,
					field.parent_doctype,
					self.get_permission_type(field.doctype, field.parent_doctype),
				)
				# Filter the fields *within* the ChildQuery object based on permissions
				field.fields = [f for f in field.fields if f in permitted_child_fields_set]
				# Only add the child query if it still has fields after filtering
				if field.fields:
					allowed_fields.append(field)
			elif isinstance(field, Field):
				if field.name == "*":
					# Expand '*' to include all permitted fields
					# Avoid reparsing '*' recursively by passing the actual list
					allowed_fields.extend(self.parse_fields(list(permitted_fields_set)))
				# Check if the field name is an optional field (like _user_tags) or in permitted fields
				elif field.name in OPTIONAL_FIELDS or field.name in permitted_fields_set:
					allowed_fields.append(field)

			elif isinstance(field, Term):
				# Allow any Term subclass, like LiteralValue (raw SQL expressions), AggregateFunction, PseudoColumnMapper (functions or complex terms)
				allowed_fields.append(field)

		return allowed_fields

	def get_user_permission_conditions(
		self, doctype: str | None = None, table: Table | None = None
	) -> list[Criterion]:
		"""Build conditions for user permissions."""
		doctype = doctype or self.permission_doctype
		table = table or self.permission_table
		conditions = []

		if self.ignore_user_permissions:
			return conditions

		user_permissions = frappe.permissions.get_user_permissions(self.user)

		if not user_permissions:
			return conditions

		doctype_link_fields = self.get_doctype_link_fields(doctype)
		for df in doctype_link_fields:
			if df.get("ignore_user_permissions"):
				continue

			user_permission_values = user_permissions.get(df.get("options"), {})
			if user_permission_values:
				docs = []
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
					elif permission.get("applicable_for") == doctype:
						docs.append(permission.get("doc"))

				if docs:
					field_name = df.get("fieldname")
					strict_user_permissions = frappe.get_system_settings("apply_strict_user_permissions")
					if strict_user_permissions:
						conditions.append(table[field_name].isin(docs))
					else:
						empty_value_condition = functions.IfNull(table[field_name], "") == ""
						value_condition = table[field_name].isin(docs)
						conditions.append(empty_value_condition | value_condition)

		return conditions

	def get_doctype_link_fields(self, doctype: str | None = None):
		doctype = doctype or self.permission_doctype
		meta = frappe.get_meta(doctype)
		# append current doctype with fieldname as 'name' as first link field
		doctype_link_fields = [{"options": doctype, "fieldname": "name"}]
		# append other link fields
		doctype_link_fields.extend(meta.get_link_fields())
		return doctype_link_fields

	def add_permission_conditions(self):
		"""
		Logic for adding permission conditions is as follows:

		If no role permissions with read/select exist:
			- apply only share permissions

		If role permissions with read/select exist:
			- apply (if_owner constraints OR user permissions), AND
			- apply permission query conditions

			If if_owner / user permission / permission query constraints are applied,
			final condition = (existing conditions) OR (share condtion)
			(rationale: shared documents trump all other restrictions)

			Else, all documents are accessible based on role permissions.

		For child tables (when parent_doctype is specified):
			- permissions are checked against the parent doctype
			- for non-single parent doctypes: a join to the parent table is added,
		                conditions reference parent fields
			- for single parent doctypes: all permissions are already checked by has_permission,
		                we exit early without adding any conditions
		"""

		if not self.apply_permissions:
			return

		if self.permission_doctype != self.doctype:
			parent_meta = frappe.get_meta(self.permission_doctype)
			if parent_meta.issingle:
				# Child table of single doctype
				# permissions are already checked by has_permission
				return

			self.query = self.query.inner_join(self.permission_table).on(
				self.table.parent == self.permission_table.name
			)

		if condition := self.get_permission_conditions(self.permission_doctype, self.permission_table):
			self.query = self.query.where(condition)

	def get_permission_conditions(self, doctype: str, table: Table) -> Criterion | None:
		role_permissions = frappe.permissions.get_role_permissions(doctype, user=self.user)
		has_role_permission = role_permissions.get("read") or role_permissions.get("select")

		if not has_role_permission:
			# no role permissions, apply only share permissions
			shared_docs = frappe.share.get_shared(doctype, self.user)
			if not shared_docs:
				# no permissions at all
				self._raise_permission_error(doctype=doctype)

			return table.name.isin(shared_docs)

		# build conditions from: if_owner constraint OR user permissions
		conditions = []

		if self.requires_owner_constraint(role_permissions):
			# skip user perm check if owner constraint is required
			conditions.append(table.owner == self.user)
		elif user_perm_conditions := self.get_user_permission_conditions(doctype, table):
			conditions.extend(user_perm_conditions)

		conditions.extend(self.get_permission_query_conditions(doctype))

		if not conditions:
			# no conditions to apply, all documents are accessible
			return

		where_condition = Criterion.all(conditions)

		# since some conditions apply, we need to consider shared docs as well
		shared_docs = frappe.share.get_shared(doctype, self.user)
		if shared_docs:
			# shared docs trump all other restrictions
			where_condition |= table.name.isin(shared_docs)

		return where_condition

	def get_queried_tables(self) -> list[str]:
		"""Extract all table names involved in the current query."""
		tables = []
		for table in self.query._from:
			tables.append(table.get_sql())

		for join in self.query._joins:
			tables.append(join.item.get_sql())
		return list(set(tables))

	def get_permission_query_conditions(self, doctype: str | None = None) -> list["RawCriterion"]:
		"""Add permission query conditions from hooks and server scripts"""
		from frappe.core.doctype.server_script.server_script_utils import get_server_script_map

		doctype = doctype or self.permission_doctype
		conditions = []
		hooks = frappe.get_hooks("permission_query_conditions", {})
		condition_methods = hooks.get(doctype, []) + hooks.get("*", [])

		for method in condition_methods:
			if c := frappe.call(frappe.get_attr(method), self.user, doctype=doctype):
				conditions.append(RawCriterion(f"({c})"))

		active_child_tables = []
		current_tables = self.get_queried_tables()
		if len(current_tables) > 1:
			main_table_name = f"tab{self.doctype}"
			for table_name in current_tables:
				if table_name != main_table_name:
					active_child_tables.append(table_name)

		# Get conditions from server scripts
		if permission_script_name := get_server_script_map().get("permission_query", {}).get(doctype):
			script = frappe.get_doc("Server Script", permission_script_name)
			if condition := script.get_permission_query_conditions(
				self.user, active_child_tables=active_child_tables
>>>>>>> a084bad5d5 (fix(apply_field_permissions): improve checks)
			):
				frappe.throw(_("Insufficient Permission for {0}").format(frappe.bold(dt)))

	@staticmethod
	def get_tables_from_query(query: str):
		return [table for table in WORDS_PATTERN.findall(query) if table.startswith("tab")]


class DynamicTableField:
	def __init__(
		self,
		doctype: str,
		fieldname: str,
		parent_doctype: str,
		alias: str | None = None,
	) -> None:
		self.doctype = doctype
		self.fieldname = fieldname
		self.alias = alias
		self.parent_doctype = parent_doctype

	def __str__(self) -> str:
		table_name = f"`tab{self.doctype}`"
		fieldname = f"`{self.fieldname}`"
		if frappe.db.db_type == "postgres":
			table_name = table_name.replace("`", '"')
			fieldname = fieldname.replace("`", '"')
		alias = f"AS {self.alias}" if self.alias else ""
		return f"{table_name}.{fieldname} {alias}".strip()

	@staticmethod
	def parse(field: str, doctype: str):
		if "." in field:
			alias = None
			if " as " in field:
				field, alias = field.split(" as ")
			if field.startswith("`tab") or field.startswith('"tab'):
				_, child_doctype, child_field = re.search(r'([`"])tab(.+?)\1.\1(.+)\1', field).groups()
				if child_doctype == doctype:
					return
				return ChildTableField(child_doctype, child_field, doctype, alias=alias)
			else:
				linked_fieldname, fieldname = field.split(".")
				linked_field = frappe.get_meta(doctype).get_field(linked_fieldname)
				linked_doctype = linked_field.options
				if linked_field.fieldtype == "Link":
					return LinkTableField(linked_doctype, fieldname, doctype, linked_fieldname, alias=alias)
				elif linked_field.fieldtype in frappe.model.table_fields:
					return ChildTableField(linked_doctype, fieldname, doctype, alias=alias)

	def apply_select(self, query: QueryBuilder) -> QueryBuilder:
		raise NotImplementedError


class ChildTableField(DynamicTableField):
	def __init__(
		self,
		doctype: str,
		fieldname: str,
		parent_doctype: str,
		alias: str | None = None,
	) -> None:
		self.doctype = doctype
		self.fieldname = fieldname
		self.alias = alias
		self.parent_doctype = parent_doctype
		self.table = frappe.qb.DocType(self.doctype)
		self.field = self.table[self.fieldname]

	def apply_select(self, query: QueryBuilder) -> QueryBuilder:
		table = frappe.qb.DocType(self.doctype)
		query = self.apply_join(query)
		return query.select(getattr(table, self.fieldname).as_(self.alias or None))

	def apply_join(self, query: QueryBuilder) -> QueryBuilder:
		table = frappe.qb.DocType(self.doctype)
		main_table = frappe.qb.DocType(self.parent_doctype)
		if not query.is_joined(table):
			query = query.left_join(table).on(
				(table.parent == main_table.name) & (table.parenttype == self.parent_doctype)
			)
		return query


class LinkTableField(DynamicTableField):
	def __init__(
		self,
		doctype: str,
		fieldname: str,
		parent_doctype: str,
		link_fieldname: str,
		alias: str | None = None,
	) -> None:
		super().__init__(doctype, fieldname, parent_doctype, alias=alias)
		self.link_fieldname = link_fieldname
		self.table = frappe.qb.DocType(self.doctype)
		self.field = self.table[self.fieldname]

	def apply_select(self, query: QueryBuilder) -> QueryBuilder:
		table = frappe.qb.DocType(self.doctype)
		query = self.apply_join(query)
		return query.select(getattr(table, self.fieldname).as_(self.alias or None))

	def apply_join(self, query: QueryBuilder) -> QueryBuilder:
		table = frappe.qb.DocType(self.doctype)
		main_table = frappe.qb.DocType(self.parent_doctype)
		if not query.is_joined(table):
			query = query.left_join(table).on(table.name == getattr(main_table, self.link_fieldname))
		return query


class ChildQuery:
	def __init__(
		self,
		fieldname: str,
		fields: list,
		parent_doctype: str,
	) -> None:
		field = frappe.get_meta(parent_doctype).get_field(fieldname)
		if field.fieldtype not in frappe.model.table_fields:
			return
		self.fieldname = fieldname
		self.fields = fields
		self.parent_doctype = parent_doctype
		self.doctype = field.options

	def get_query(self, parent_names=None) -> QueryBuilder:
		filters = {
			"parenttype": self.parent_doctype,
			"parentfield": self.fieldname,
			"parent": ["in", parent_names],
		}
		return frappe.qb.get_query(
			self.doctype,
			fields=[*self.fields, "parent", "parentfield"],
			filters=filters,
			order_by="idx asc",
		)


def literal_eval_(literal):
	try:
		return literal_eval(literal)
	except (ValueError, SyntaxError):
		return literal


def has_function(field):
	_field = field.casefold() if (isinstance(field, str) and "`" not in field) else field
	if not issubclass(type(_field), Criterion):
		if any([f"{func}(" in _field for func in SQL_FUNCTIONS]):  # ) <- ignore this comment.
			return True


def get_nested_set_hierarchy_result(doctype: str, name: str, hierarchy: str) -> list[str]:
	"""Get matching nodes based on operator."""
	table = frappe.qb.DocType(doctype)
	try:
		lft, rgt = frappe.qb.from_(table).select("lft", "rgt").where(table.name == name).run()[0]
	except IndexError:
		lft, rgt = None, None

	if hierarchy in ("descendants of", "not descendants of", "descendants of (inclusive)"):
		result = (
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.lft > lft)
			.where(table.rgt < rgt)
			.orderby(table.lft, order=Order.asc)
			.run(pluck=True)
		)
		if hierarchy == "descendants of (inclusive)":
			result += [name]
	else:
		# Get ancestor elements of a DocType with a tree structure
		result = (
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.lft < lft)
			.where(table.rgt > rgt)
			.orderby(table.lft, order=Order.desc)
			.run(pluck=True)
		)
	return result


@lru_cache(maxsize=1024)
def _sanitize_field(field: str, is_mariadb):
	if field == "*" or not SPECIAL_CHAR_PATTERN.search(field):
		# Skip checking if there are no special characters
		return field

	stripped_field = sqlparse.format(field, strip_comments=True, keyword_case="lower")
	if is_mariadb:
		return MARIADB_SPECIFIC_COMMENT.sub("", stripped_field)
	return stripped_field
