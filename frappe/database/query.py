import re
from ast import literal_eval
from functools import lru_cache
from types import BuiltinFunctionType
from typing import TYPE_CHECKING, TypeAlias

import sqlparse
from pypika.queries import QueryBuilder, Table

import frappe
from frappe import _
from frappe.database.operator_map import OPERATOR_MAP
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.database.utils import DefaultOrderBy, FilterValue, convert_to_value, get_doctype_name
from frappe.model import get_permitted_fields
from frappe.query_builder import Criterion, Field, Order, functions
from frappe.query_builder.functions import Function, SqlFunctions
from frappe.query_builder.utils import PseudoColumnMapper
from frappe.utils.data import MARIADB_SPECIFIC_COMMENT

if TYPE_CHECKING:
	from frappe.query_builder import DocType

TAB_PATTERN = re.compile("^tab")
WORDS_PATTERN = re.compile(r"\w+")
BRACKETS_PATTERN = re.compile(r"\(.*?\)|$")
SQL_FUNCTIONS = [sql_function.value for sql_function in SqlFunctions]
COMMA_PATTERN = re.compile(r",\s*(?![^()]*\))")

# less restrictive version of frappe.core.doctype.doctype.doctype.START_WITH_LETTERS_PATTERN
# to allow table names like __Auth
TABLE_NAME_PATTERN = re.compile(r"^[\w -]*$", flags=re.ASCII)


class Engine:
	def get_query(
		self,
		table: str | Table,
		fields: str | list | tuple | None = None,
		filters: dict[str, FilterValue] | FilterValue | list[list | FilterValue] | None = None,
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
		ignore_permissions: bool = True,
		user: str | None = None,
		parent_doctype: str | None = None,
	) -> QueryBuilder:
		self.is_mariadb = frappe.db.db_type == "mariadb"
		self.is_postgres = frappe.db.db_type == "postgres"
		self.validate_filters = validate_filters
		self.user = user or frappe.session.user
		self.parent_doctype = parent_doctype

		if isinstance(table, Table):
			self.table = table
			self.doctype = get_doctype_name(table.get_sql())
		else:
			self.doctype = table
			self.validate_doctype()
			self.table = frappe.qb.DocType(table)

		if update:
			self.query = frappe.qb.update(self.table)
		elif into:
			self.query = frappe.qb.into(self.table)
		elif delete:
			self.query = frappe.qb.from_(self.table).delete()
		else:
			self.query = frappe.qb.from_(self.table)
			self.fields = self.parse_fields(fields)
			if not ignore_permissions:
				self.fields = self.apply_field_permissions()
			self.apply_fields(self.fields)

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

		if not ignore_permissions:
			self.check_read_permission()
			self.add_permission_conditions()

		return self.query

	def validate_doctype(self):
		if not TABLE_NAME_PATTERN.match(self.doctype):
			frappe.throw(_("Invalid DocType: {0}").format(self.doctype))

	def apply_fields(self, fields):
		if not self.fields:
			self.fields = [self.table.name]

		self.query._child_queries = []
		for field in self.fields:
			if isinstance(field, DynamicTableField):
				self.query = field.apply_select(self.query)
			elif isinstance(field, ChildQuery):
				self.query._child_queries.append(field)
			else:
				self.query = self.query.select(field)

	def apply_filters(
		self,
		filters: dict[str, FilterValue] | FilterValue | list[list | FilterValue] | None = None,
	):
		if filters is None:
			return

		if isinstance(filters, FilterValue):
			filters = {"name": convert_to_value(filters)}

		if isinstance(filters, Criterion):
			self.query = self.query.where(filters)

		elif isinstance(filters, dict):
			self.apply_dict_filters(filters)

		elif isinstance(filters, list | tuple):
			if all(isinstance(d, FilterValue) for d in filters) and len(filters) > 0:
				self.apply_dict_filters({"name": ("in", tuple(convert_to_value(f) for f in filters))})
			else:
				for filter in filters:
					if isinstance(filter, FilterValue | Criterion | dict):
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

	def apply_dict_filters(self, filters: dict[str, FilterValue | list]):
		for field, value in filters.items():
			operator = "="
			if isinstance(value, list | tuple):
				operator, value = value

			self._apply_filter(field, value, operator)

	def _apply_filter(
		self,
		field: str,
		value: FilterValue | list | set | None,
		operator: str = "=",
		doctype: str | None = None,
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

		_value = convert_to_value(_value)

		if not _value and isinstance(_value, list | tuple | set):
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
			self.query = self.query.where(_field.isnull())
		else:
			self.query = self.query.where(operator_fn(_field, _value))

	def get_function_object(self, field: str) -> "Function":
		"""Return PyPika Function object. Expect field to look like 'SUM(*)' or 'name' or something similar."""
		func = field.split("(", maxsplit=1)[0].capitalize()
		args_start, args_end = len(func) + 1, field.index(")")
		args = field[args_start:args_end].split(",")

		_, alias = field.split(" as ") if " as " in field else (None, None)

		to_cast = "*" not in args
		_args = []

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
									lambda field: Field(field.strip())
									if "`" not in field
									else PseudoColumnMapper(field.strip()),
									arg.split(_operator),
								),
							)

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
			frappe.throw(_("Insufficient Permission for {0}").format(frappe.bold(self.doctype)))

	def apply_field_permissions(self):
		"""Allow fields that user has permission to read"""
		permitted_fields = get_permitted_fields(
			doctype=self.doctype,
			parenttype=self.parent_doctype,
			permission_type=self.get_permission_type(self.doctype),
			ignore_virtual=True,
		)
		filtered_fields = []
		for field in self.fields:
			if isinstance(field, ChildTableField):
				permitted_child_fields = get_permitted_fields(
					doctype=field.doctype,
					parenttype=field.parent_doctype,
					permission_type=self.get_permission_type(field.doctype),
					ignore_virtual=True,
				)
				if field.child_fieldname in permitted_child_fields:
					filtered_fields.append(field)
			elif isinstance(field, LinkTableField):
				if field.link_fieldname in permitted_fields:
					filtered_fields.append(field)
			elif isinstance(field, ChildQuery):
				permitted_child_fields = get_permitted_fields(
					doctype=field.doctype,
					parenttype=field.parent_doctype,
					permission_type=self.get_permission_type(field.doctype),
					ignore_virtual=True,
				)
				field.fields = [f for f in field.fields if f in permitted_child_fields]
			elif isinstance(field, Field):
				if field.name == "*":
					filtered_fields.extend(self.parse_fields(permitted_fields))
				elif field.name in permitted_fields:
					filtered_fields.append(field)
		return filtered_fields

	def get_user_permission_conditions(self, role_permissions):
		"""Build conditions for user permissions and return tuple of (conditions, fetch_shared_docs)"""
		conditions = []
		fetch_shared_docs = False

		# add user permission only if role has read perm
		if not (role_permissions.get("read") or role_permissions.get("select")):
			return conditions, fetch_shared_docs

		user_permissions = frappe.permissions.get_user_permissions(self.user)

		if not user_permissions:
			return conditions, fetch_shared_docs

		fetch_shared_docs = True

		doctype_link_fields = self.get_doctype_link_fields()
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
					elif permission.get("applicable_for") == self.doctype:
						docs.append(permission.get("doc"))

				if docs:
					field_name = df.get("fieldname")
					strict_user_permissions = frappe.get_system_settings("apply_strict_user_permissions")
					if strict_user_permissions:
						conditions.append(self.table[field_name].isin(docs))
					else:
						empty_value_condition = self.table[field_name].isnull()
						value_condition = self.table[field_name].isin(docs)
						conditions.append(empty_value_condition | value_condition)

		return conditions, fetch_shared_docs

	def get_doctype_link_fields(self):
		meta = frappe.get_meta(self.doctype)
		# append current doctype with fieldname as 'name' as first link field
		doctype_link_fields = [{"options": self.doctype, "fieldname": "name"}]
		# append other link fields
		doctype_link_fields.extend(meta.get_link_fields())
		return doctype_link_fields

	def add_permission_conditions(self):
		conditions = []
		role_permissions = frappe.permissions.get_role_permissions(self.doctype, user=self.user)
		fetch_shared_docs = False

		if self.requires_owner_constraint(role_permissions):
			fetch_shared_docs = True
			conditions.append(self.table.owner == self.user)
		# skip user perm check if owner constraint is required
		elif role_permissions.get("read") or role_permissions.get("select"):
			user_perm_conditions, fetch_shared = self.get_user_permission_conditions(role_permissions)
			conditions.extend(user_perm_conditions)
			fetch_shared_docs = fetch_shared_docs or fetch_shared

		shared_docs = []
		if fetch_shared_docs:
			shared_docs = frappe.share.get_shared(self.doctype, self.user)

		if shared_docs:
			shared_condition = self.table.name.isin(shared_docs)
			if conditions:
				# (permission conditions) OR (shared condition)
				self.query = self.query.where(Criterion.any(conditions) | shared_condition)
			else:
				self.query = self.query.where(shared_condition)
		elif conditions:
			# AND all permission conditions
			self.query = self.query.where(Criterion.all(conditions))

	def get_permission_type(self, doctype) -> str:
		"""Get permission type (select/read) based on user permissions"""
		if frappe.only_has_select_perm(doctype, user=self.user):
			return "select"
		return "read"

	def requires_owner_constraint(self, role_permissions):
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


class Permission:
	@classmethod
	def check_permissions(cls, query, **kwargs):
		if not isinstance(query, str):
			query = query.get_sql()

		doctype = cls.get_tables_from_query(query)
		if isinstance(doctype, str):
			doctype = [doctype]

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
					return ChildTableField(linked_doctype, fieldname, doctype, linked_fieldname, alias=alias)

	def apply_select(self, query: QueryBuilder) -> QueryBuilder:
		raise NotImplementedError


class ChildTableField(DynamicTableField):
	def __init__(
		self,
		doctype: str,
		fieldname: str,
		parent_doctype: str,
		parent_fieldname: str | None = None,
		alias: str | None = None,
	) -> None:
		self.doctype = doctype
		self.fieldname = fieldname
		self.alias = alias
		self.parent_doctype = parent_doctype
		self.parent_fieldname = parent_fieldname
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
	if field == "*" or not SPECIAL_CHAR_PATTERN.match(field):
		# Skip checking if there are no special characters
		return field

	stripped_field = sqlparse.format(field, strip_comments=True, keyword_case="lower")
	if is_mariadb:
		return MARIADB_SPECIFIC_COMMENT.sub("", stripped_field)
	return stripped_field
