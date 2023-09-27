import re
from ast import literal_eval
from types import BuiltinFunctionType
from typing import TYPE_CHECKING

import sqlparse
from pypika.queries import QueryBuilder, Table

import frappe
import frappe.share
import frappe.permissions
from frappe import _
from frappe.database.operator_map import OPERATOR_MAP
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.database.utils import DefaultOrderBy, get_doctype_name
from frappe.query_builder import Criterion, Field, Order, functions
from frappe.query_builder.functions import Function, SqlFunctions
from frappe.query_builder.utils import PseudoColumnMapper
from frappe.utils.data import MARIADB_SPECIFIC_COMMENT
from frappe.core.doctype.server_script.server_script_utils import get_server_script_map
from frappe.model import get_permitted_fields, optional_fields

if TYPE_CHECKING:
	from frappe.query_builder import DocType

TAB_PATTERN = re.compile("^tab")
WORDS_PATTERN = re.compile(r"\w+")
BRACKETS_PATTERN = re.compile(r"\(.*?\)|$")
SQL_FUNCTIONS = [sql_function.value for sql_function in SqlFunctions]
COMMA_PATTERN = re.compile(r",\s*(?![^()]*\))")
ALPHANUMERIC = re.compile(r"^[a-zA-Z0-9_]+$")

# less restrictive version of frappe.core.doctype.doctype.doctype.START_WITH_LETTERS_PATTERN
# to allow table names like __Auth
TABLE_NAME_PATTERN = re.compile(r"^[\w -]*$", flags=re.ASCII)


class Engine:
	def get_query(
		self,
		doctype: str | Table,
		fields: list | tuple | None = None,
		filters: dict[str, str | int] | str | int | list[list | str | int] | None = None,
		parent_doctype: str | None = None,
		order_by: str | None = None,
		group_by: str | None = None,
		limit: int | None = None,
		offset: int | None = None,
		distinct: bool = False,
		for_update: bool = False,
		update: bool = False,
		into: bool = False,
		delete: bool = False,
		reference_doctype: str | None = None,
		apply_permissions: bool = False,
	) -> QueryBuilder:
		self.is_mariadb = frappe.db.db_type == "mariadb"
		self.is_postgres = frappe.db.db_type == "postgres"

		if isinstance(doctype, Table):
			self.table = doctype
			self.doctype = get_doctype_name(doctype.get_sql())
		else:
			self.doctype = doctype
			self.validate_doctype()
			self.table = frappe.qb.DocType(doctype)

		# parent_doctype is required for permission check if doctype is a child table
		self.parent_doctype = parent_doctype

		# for contextual user permission check
		# to determine which user permission is applicable on link field of specific doctype
		self.reference_doctype = reference_doctype or self.doctype

		self.apply_permissions = apply_permissions

		if update:
			self.query = frappe.qb.update(self.table)
		elif into:
			self.query = frappe.qb.into(self.table)
		elif delete:
			self.query = frappe.qb.from_(self.table).delete()
		else:
			self.query = frappe.qb.from_(self.table)

		# reference to engine
		self.query._engine = self

		if self.apply_permissions:
			self.query_permissions = QueryPermissions(self.query, frappe.session.user)

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
			self.query = self.query.for_update()

		if group_by:
			self.query = self.query.groupby(group_by)

		if self.apply_permissions:
			where_clause = self.query_permissions.get_where_clause()
			if where_clause:
				self.query = self.query.where(where_clause)

		return self.query

	def validate_doctype(self):
		if not TABLE_NAME_PATTERN.match(self.doctype):
			frappe.throw(_("Invalid DocType: {0}").format(self.doctype))

	def apply_fields(self, fields):
		self.fields = self.parse_fields(fields)

		if not self.fields:
			self.fields = [getattr(self.table, "name")]

		if self.apply_permissions:
			self.fields = self.query_permissions.filter_fields(self.fields)

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
		filters: dict[str, str | int] | str | int | list[list | str | int] | None = None,
	):
		if filters is None:
			return

		if isinstance(filters, (str, int)):
			filters = {"name": str(filters)}

		if isinstance(filters, Criterion):
			self.query = self.query.where(filters)

		elif isinstance(filters, dict):
			self.apply_dict_filters(filters)

		elif isinstance(filters, (list, tuple)):
			if all(isinstance(d, (str, int)) for d in filters) and len(filters) > 0:
				self.apply_dict_filters({"name": ["in", filters]})
			else:
				for filter in filters:
					if isinstance(filter, (str, int, Criterion, dict)):
						self.apply_filters(filter)
					elif isinstance(filter, (list, tuple)):
						self.apply_list_filters(filter)

	def apply_list_filters(self, filter: list):
		if len(filter) == 2:
			field, value = filter
			self._apply_filter(field, value, "=", self.doctype)
		elif len(filter) == 3:
			field, operator, value = filter
			self._apply_filter(field, value, operator, self.doctype)
		elif len(filter) == 4:
			doctype, field, operator, value = filter
			self._apply_filter(field, value, operator, doctype)

	def apply_dict_filters(self, filters: dict[str, str | int | list]):
		for field, value in filters.items():
			operator = "="
			if isinstance(value, (list, tuple)):
				operator, value = value

			self._apply_filter(field, value, operator, self.doctype)

	def _apply_filter(
		self, field: str, value: str | int | list | None, operator: str, doctype: str
	):
		if isinstance(field, str):
			if dynamic_field := DynamicTableField.parse(field, self.doctype):
				# apply implicit join if link/child field's field is referenced
				self.query = dynamic_field.apply_join(self.query)
				_field = dynamic_field.field
			elif validate_fieldname(field, doctype):
				_field = frappe.qb.DocType(doctype)[field]
			else:
				_field = None
		elif isinstance(field, Field):
			_field = field
		else:
			_field = None

		if not _field:
			frappe.throw(f"Invalid fieldname: {_field}")

		# apply implicit join if child table is referenced
		if doctype != self.doctype:
			meta = frappe.get_meta(doctype)
			table = frappe.qb.DocType(doctype)
			if meta.istable and not self.query.is_joined(table):
				self.query = self.query.left_join(table).on(
					(table.parent == self.table.name) & (table.parenttype == self.doctype)
				)

		_value = value
		_operator = operator

		if isinstance(_value, bool):
			_value = int(_value)

		elif not _value and isinstance(_value, (list, tuple)):
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
		"""Expects field to look like 'SUM(*)' or 'name' or something similar. Returns PyPika Function object"""
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
					(Field(initial_fields) if "`" not in initial_fields else PseudoColumnMapper(initial_fields))
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
		def _sanitize_field(field: str):
			if not isinstance(field, str):
				return field
			stripped_field = sqlparse.format(field, strip_comments=True, keyword_case="lower")
			if self.is_mariadb:
				return MARIADB_SPECIFIC_COMMENT.sub("", stripped_field)
			return stripped_field

		if isinstance(fields, (list, tuple)):
			return [_sanitize_field(field) for field in fields]
		elif isinstance(fields, str):
			return _sanitize_field(fields)

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
		if isinstance(fields, (list, tuple, set)) and None in fields and Field not in fields:
			return []

		if not isinstance(fields, (list, tuple)):
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

		if not field_exists(self.fieldname, self.doctype):
			frappe.throw(f"Invalid fieldname: {self.fieldname}")
		if self.alias and not ALPHANUMERIC.match(self.alias):
			frappe.throw(f"Invalid alias: {self.alias}")

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
				alias = alias.strip()
			if field.startswith("`tab") or field.startswith('"tab'):
				_, child_doctype, child_field = re.search(r'([`"])tab(.+?)\1.\1(.+)\1', field).groups()
				if child_doctype == doctype:
					return
				return ChildTableField(child_doctype, child_field, doctype, alias=alias)
			else:
				linked_fieldname, fieldname = field.split(".")
				linked_field = frappe.get_meta(doctype).get_field(linked_fieldname)
				if not linked_field:
					return
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
		child_fieldname: str | None = None,
		alias: str | None = None,
	) -> None:
		super().__init__(doctype, fieldname, parent_doctype, alias=alias)
		self.child_fieldname = child_fieldname
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
			if self.child_fieldname:
				query = query.left_join(table).on(
					(table.parent == main_table.name) & (table.parenttype == self.parent_doctype) & (table.parentfield == self.child_fieldname)
				)
			else:
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
			fields=self.fields + ["parent", "parentfield"],
			filters=filters,
			order_by="idx asc",
		)


class QueryPermissions:
	def __init__(self, query: QueryBuilder, user: str) -> None:
		self.query = query
		# TODO: make this work for queries not built with engine
		self.engine = query._engine
		self.user = user
		self.permission_map = {}
		self.meta = frappe.get_meta(self.engine.doctype)
		self.role_permissions = frappe.permissions.get_role_permissions(self.engine.doctype, user=self.user)
		self.has_if_owner_constraint = False
		self.user_permission_conditions = []
		self.shared_doc_names = []
		self.permitted_fields = {}

	def get_where_clause(self):
		# Role Permissions: select, read
		if not self.has_read_permission(self.engine.doctype, self.engine.parent_doctype):
			self.throw_read_permission_error(self.engine.doctype)

		# Owner based restraints: if_owner
		self.has_if_owner_constraint = self.requires_owner_constraint()

		# User Permissions
		if not self.has_if_owner_constraint:
			self.user_permission_conditions = self.get_user_permissions()

		# Shared docs
		only_shared_applicable = (
			not self.meta.istable
			and not (self.role_permissions.get("select") or self.role_permissions.get("read"))
			and not self.user_permission_conditions
		)

		if only_shared_applicable or self.has_if_owner_constraint or self.user_permission_conditions:
			self.shared_doc_names = self.get_shared_permissions()

		# Permission Query (hook)
		self.permission_query_conditions = self.get_permission_query_conditions()

		where_clause = None
		if only_shared_applicable:
			if self.shared_doc_names:
				where_clause = self.engine.table.name.isin(self.shared_doc_names)
		else:
			conditions = []
			if self.has_if_owner_constraint:
				conditions.append(self.engine.table.owner == self.user)
			elif self.user_permission_conditions:
				for fieldname, values in self.user_permission_conditions.items():
					conditions.append(self.engine.table[fieldname].isin(values))

			if self.permission_query_conditions:
				# permission query is a string of where clause
				# TODO: it should probably also support passing the query object directly
				conditions.append(RawCriterion(self.permission_query_conditions))

			if conditions and self.shared_doc_names:
				# share is an OR condition, if there are other permissions
				where_clause = Criterion.any([Criterion.all([*conditions]), self.engine.table.name.isin(self.shared_doc_names)])
			elif self.shared_doc_names:
				where_clause = self.engine.table.name.isin(self.shared_doc_names)
			elif conditions:
				where_clause = Criterion.all([*conditions])

		return where_clause

	def filter_fields(self, fields):
		'''Filter fields based on perm level'''
		filtered_fields = []
		for field in fields:
			if isinstance(field, LinkTableField):
				# check if the link field itself is permitted as well as the fieldname of the linked doctype
				if self.is_field_permitted(field.link_fieldname, field.parent_doctype) and self.is_field_permitted(field.fieldname, field.doctype):
					filtered_fields.append(field)
			elif isinstance(field, ChildTableField):
				# check if the child table field itself is permitted
				# child field can come from child_field.fieldname or `tabChild Table`.`fieldname` syntax
				# in the latter case, we don't know the child field so we can't check if it's permitted
				child_field_is_valid = self.is_child_field_permitted(field.child_fieldname, field.parent_doctype) if field.child_fieldname else True
				# check if child field itself is valid as well as the fieldname of the child table doctype
				if child_field_is_valid and self.is_field_permitted(field.fieldname, field.doctype, field.parent_doctype):
					filtered_fields.append(field)
			elif isinstance(field, ChildQuery):
				# check if the child table field is permitted
				# not sure if we should filter the child table fields here because you can't configure perm levels for child table fields
				if self.is_field_permitted(field.fieldname, field.parent_doctype):
					filtered_fields.append(field)
			elif isinstance(field, Field) and field.name == '*':
				doctype = get_doctype_name(field.table.get_sql())
				filtered_fields += self.get_permitted_fields(doctype)
			elif isinstance(field, Field):
				# check if the field is permitted
				doctype = get_doctype_name(field.table.get_sql())
				fieldname = field.name
				if self.is_field_permitted(fieldname, doctype):
					filtered_fields.append(field)
		return filtered_fields

	def is_field_permitted(self, fieldname, doctype, parent_doctype=None):
		permitted_fields = self.get_permitted_fields(doctype, parent_doctype)
		return fieldname in (permitted_fields + list(optional_fields))

	def is_child_field_permitted(self, child_field, parent_doctype):
		'''Child field is not considered in `get_permitted_fields`. this has to be done separately'''
		# TODO
		pass

	def get_permitted_fields(self, doctype, parent_doctype=None):
		if doctype not in self.permitted_fields:
			ptype = "select" if frappe.only_has_select_perm(doctype) else "read"
			self.permitted_fields[doctype] = get_permitted_fields(doctype, parent_doctype, self.user, ptype)
		return self.permitted_fields[doctype]

	def get_shared_permissions(self):
		return frappe.share.get_shared(self.engine.doctype, user=self.user, rights=["read"])

	def get_permission_query_conditions(self):
		doctype = self.engine.doctype
		conditions = []
		condition_methods = frappe.get_hooks("permission_query_conditions", {}).get(doctype, [])
		if condition_methods:
			for method in condition_methods:
				c = frappe.call(frappe.get_attr(method), self.user)
				if c:
					conditions.append(c)

		permision_script_name = get_server_script_map().get("permission_query", {}).get(doctype)
		if permision_script_name:
			script = frappe.get_doc("Server Script", permision_script_name)
			condition = script.get_permission_query_conditions(self.user)
			if condition:
				conditions.append(condition)

		return " and ".join(conditions) if conditions else ""

	def has_read_permission(self, doctype, parent_doctype=None):
		if doctype not in self.permission_map:
			ptype = "select" if frappe.only_has_select_perm(doctype) else "read"
			val = frappe.has_permission(
				doctype,
				ptype=ptype,
				parent_doctype=parent_doctype,
			)
			self.permission_map[doctype] = False if not val else ptype
		return self.permission_map[doctype]

	def get_user_permissions(self):
		if not (self.role_permissions.get("read") or self.role_permissions.get("select")):
			return

		user_permissions = frappe.permissions.get_user_permissions(self.user)
		if not user_permissions:
			return

		apply_strict_user_permissions = frappe.get_system_settings("apply_strict_user_permissions")

		# append current doctype with fieldname as 'name' as a link field
		doctype_link_fields = self.meta.get_link_fields() + [{'options': self.engine.doctype, 'fieldname': 'name'}]

		conditions = {}
		for df in doctype_link_fields:
			if df.get("ignore_user_permissions"):
				continue

			user_permission_values = user_permissions.get(df.get("options"), {})
			if not user_permission_values:
				continue

			docs = []
			for permission in user_permission_values:
				if not permission.get("applicable_for"):
					docs.append(permission.get("doc"))

				# append docs based on user permission applicable on reference doctype
				# this is useful when getting list of docs from a link field
				# in this case parent doctype of the link
				# will be the reference doctype

				# TODO: find a way to decouple reference_doctype from query permissions
				elif df.get("fieldname") == "name" and self.engine.reference_doctype:
					if permission.get("applicable_for") == self.engine.reference_doctype:
						docs.append(permission.get("doc"))

				elif permission.get("applicable_for") == self.engine.doctype:
					docs.append(permission.get("doc"))

			if docs:
				if apply_strict_user_permissions:
					values = docs
				else:
					# allow empty values if strict user permissions not enabled
					values = docs + ["", None]
				conditions[df.get('fieldname')] = values

		return conditions

	def requires_owner_constraint(self):
		"""Returns True if "select" or "read" isn't available without being creator."""

		role_permissions = self.role_permissions
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

	def throw_read_permission_error(self, doctype):
		frappe.throw(_("No permission to read {0}").format(doctype), frappe.PermissionError)

class RawCriterion(Criterion):
	def __init__(self, raw: str, alias: str | None = None) -> None:
		super().__init__(alias)
		self.raw = raw

	def get_sql(self, **kwargs) -> str:
		return self.raw

def literal_eval_(literal):
	try:
		return literal_eval(literal)
	except (ValueError, SyntaxError):
		return literal


def has_function(field):
	_field = field.casefold() if (isinstance(field, str) and "`" not in field) else field
	if not issubclass(type(_field), Criterion):
		if any([f"{func}(" in _field for func in SQL_FUNCTIONS]):
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

def validate_fieldname(fieldname, doctype):
	'''
	Validate fieldname for possible SQL injections. Only tries to validate if special characters are present.
	'''
	if not SPECIAL_CHAR_PATTERN.search(fieldname):
		return True

	return field_exists(fieldname, doctype)


def field_exists(fieldname, doctype):
	from frappe.model import default_fields, child_table_fields

	if doctype == 'Singles':
		return fieldname in ['doctype', 'field', 'value']

	if fieldname in (default_fields + child_table_fields):
		return True

	DocField = frappe.qb.DocType('DocField')
	model_field_exists = (
		frappe.qb.from_(DocField)
		.select("fieldname")
		.where((DocField.parent == doctype) & (DocField.fieldname == fieldname))
		.run(pluck=True)
	)
	if model_field_exists:
		return True

	CustomField = frappe.qb.DocType('Custom Field')
	custom_field_exists = (
		frappe.qb.from_(CustomField)
		.select("fieldname")
		.where((CustomField.dt == doctype) & (CustomField.fieldname == fieldname))
		.run(pluck=True)
	)
	if custom_field_exists:
		return True

	return False