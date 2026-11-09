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
		if _operator.casefold() in OPERATOR_MAP["nested_set"]:
			hierarchy = _operator.casefold()
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
									lambda field: (
										Field(field.strip())
										if "`" not in field
										else PseudoColumnMapper(field.strip())
									),
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

<<<<<<< HEAD
	stripped_field = sqlparse.format(field, strip_comments=True, keyword_case="lower")
	if is_mariadb:
		return MARIADB_SPECIFIC_COMMENT.sub("", stripped_field)
	return stripped_field
=======
	if field.isdigit():
		return field

	# Reject SQL functions in string format - use dict syntax instead
	if _is_function_call(field):
		frappe.throw(
			_(
				"SQL functions are not allowed as strings in SELECT: {0}. Use dict syntax like {{'COUNT': '*'}} instead."
			).format(field),
			frappe.ValidationError,
		)

	if ALLOWED_FIELD_PATTERN.match(field):
		return field

	frappe.throw(
		_(
			"Invalid field format for SELECT: {0}. Field names must be simple, backticked, table-qualified, aliased, or '*'."
		).format(field),
		frappe.PermissionError,
	)


class RawCriterion(Term):
	"""A class to represent raw SQL string as a criterion.

	Allows using raw SQL strings in pypika queries:
		frappe.qb.from_("DocType").where(RawCriterion("name like 'a%'"))
	"""

	def __init__(self, sql_string: str):
		self.sql_string = sql_string
		super().__init__()

	def get_sql(self, **kwargs: Any) -> str:
		return self.sql_string

	def __and__(self, other):
		return CombinedRawCriterion(self, other, "AND")

	def __or__(self, other):
		return CombinedRawCriterion(self, other, "OR")

	def __invert__(self):
		return RawCriterion(f"NOT ({self.sql_string})")


class CombinedRawCriterion(RawCriterion):
	def __init__(self, left, right, operator):
		self.left = left
		self.right = right
		self.operator = operator
		super(RawCriterion, self).__init__()

	def get_sql(self, **kwargs: Any) -> str:
		left_sql = self.left.get_sql(**kwargs) if hasattr(self.left, "get_sql") else str(self.left)
		right_sql = self.right.get_sql(**kwargs) if hasattr(self.right, "get_sql") else str(self.right)
		# Wrap entire expression in parentheses to ensure correct operator precedence
		return f"(({left_sql}) {self.operator} ({right_sql}))"


class SQLFunctionParser:
	"""Parser for SQL function dictionaries in query builder fields."""

	def __init__(self, engine):
		self.engine = engine

	def is_function_dict(self, field_dict: dict) -> bool:
		"""Check if a dictionary represents a SQL function definition."""
		function_keys = [k for k in field_dict.keys() if k.lower() != "as"]
		return len(function_keys) == 1 and function_keys[0] in FUNCTION_MAPPING

	def is_operator_dict(self, field_dict: dict) -> bool:
		"""Check if a dictionary represents an arithmetic operator expression.

		Example: {"ADD": [1, 2], "as": "sum"} or {"DIV": ["total", "count"]}
		"""
		operator_keys = [k for k in field_dict.keys() if k.lower() != "as"]
		return len(operator_keys) == 1 and operator_keys[0] in OPERATOR_MAPPING

	def _extract_dict_components(self, d: dict, valid_keys: dict, error_msg: str) -> tuple:
		"""Extract name, alias, and args from function/operator dict."""
		name = None
		alias = None
		args = None

		for key, value in d.items():
			if key.lower() == "as":
				alias = value
			else:
				name = key
				args = value

		if not name:
			frappe.throw(_("Invalid {0} dictionary format").format(error_msg), frappe.ValidationError)

		if name not in valid_keys:
			frappe.throw(_("Unsupported {0}: {1}").format(error_msg, name), frappe.ValidationError)

		if alias:
			self._validate_alias(alias)

		return name, alias, args

	def parse_function(self, function_dict: dict) -> Field:
		"""Parse a SQL function dictionary into a pypika function call."""
		function_name, alias, function_args = self._extract_dict_components(
			function_dict, FUNCTION_MAPPING, "function or invalid field name"
		)

		func_class = FUNCTION_MAPPING[function_name]

		if isinstance(function_args, str):
			parsed_arg = self._parse_and_validate_argument(function_args, function_name=function_name)
			function_call = func_class(parsed_arg)
		elif isinstance(function_args, list):
			parsed_args = []
			for arg in function_args:
				parsed_arg = self._parse_and_validate_argument(arg, function_name=function_name)
				parsed_args.append(parsed_arg)
			function_call = func_class(*parsed_args)
		elif isinstance(function_args, (int | float)):
			function_call = func_class(function_args)
		elif function_args is None:
			try:
				function_call = func_class()
			except TypeError:
				frappe.throw(
					_("Function {0} requires arguments but none were provided").format(function_name),
					frappe.ValidationError,
				)
		else:
			frappe.throw(
				_(
					"Invalid function argument type: {0}. Only strings, numbers, lists, and None are allowed."
				).format(type(function_args).__name__),
				frappe.ValidationError,
			)

		if alias:
			return function_call.as_(alias)
		else:
			return function_call

	def parse_operator(self, operator_dict: dict) -> ArithmeticExpression:
		"""Parse an arithmetic operator dictionary into a pypika ArithmeticExpression.

		Operators require exactly 2 arguments (left and right operands).
		Arguments can be: numbers, field names, nested functions, or nested operators.
		Example: {"DIV": [1, {"NULLIF": [{"LOCATE": ["'test'", "name"]}, 0]}]}
		"""
		operator_name, alias, operator_args = self._extract_dict_components(
			operator_dict, OPERATOR_MAPPING, "operator"
		)

		operator = OPERATOR_MAPPING[operator_name]

		# Operators require exactly 2 arguments (left and right operands)
		if not isinstance(operator_args, list) or len(operator_args) != 2:
			frappe.throw(
				_("Operator {0} requires exactly 2 arguments (left and right operands)").format(
					operator_name
				),
				frappe.ValidationError,
			)

		# Parse and validate both operands (supports nested functions/operators)
		left = self._parse_and_validate_argument(operator_args[0])
		right = self._parse_and_validate_argument(operator_args[1])

		# Wrap raw values (numbers, strings) in ValueWrapper so pypika can process them
		if not isinstance(left, Term):
			left = ValueWrapper(left)
		if not isinstance(right, Term):
			right = ValueWrapper(right)

		assert isinstance(left, Term) and isinstance(right, Term), "operands must be pypika Terms"
		expression = ArithmeticExpression(operator=operator, left=left, right=right)

		if alias:
			return expression.as_(alias)
		else:
			return expression

	def _parse_and_validate_argument(self, arg, *, function_name: str | None = None):
		"""Parse and validate a single function/operator argument against SQL injection.

		Supports:
		- Numbers: 1, 2.5, etc.
		- Strings: field names or quoted literals
		- Nested dicts: functions {"COUNT": "name"} or operators {"ADD": [1, 2]}
		"""
		if isinstance(arg, (int | float)):
			return arg
		elif isinstance(arg, str):
			return self._validate_string_argument(arg, function_name=function_name)
		elif isinstance(arg, dict):
			# Recursively handle nested functions and operators
			if self.is_function_dict(arg):
				return self.parse_function(arg)
			elif self.is_operator_dict(arg):
				return self.parse_operator(arg)
			else:
				frappe.throw(
					_("Invalid nested expression: dictionary must represent a function or operator"),
					frappe.ValidationError,
				)
		elif arg is None:
			# None is allowed for some functions
			return arg
		else:
			frappe.throw(
				_("Invalid argument type: {0}. Only strings, numbers, dicts, and None are allowed.").format(
					type(arg).__name__
				),
				frappe.ValidationError,
			)

	def _validate_string_argument(self, arg: str, *, function_name: str | None = None):
		"""Validate string arguments to prevent SQL injection."""
		arg = arg.strip()

		if not arg:
			frappe.throw(_("Empty string arguments are not allowed"), frappe.ValidationError)

		# Special case: allow '*' only for specific functions like COUNT(*)
		if arg == "*":
			if function_name not in STAR_ALLOWED_FUNCTIONS:
				frappe.throw(
					_("'*' is only allowed in {0} SQL function(s)").format(", ".join(STAR_ALLOWED_FUNCTIONS)),
					frappe.ValidationError,
				)
			return Star()

		# Check for string literals (quoted strings)
		if len(arg) >= 2 and arg[0] in ("'", '"') and arg[-1] == arg[0]:
			# note: pypika handles proper escaping with wrap_constant
			return arg[1:-1]

		# Check for backtick notation: `tabDocType`.`fieldname`
		# Parse and return as Field object to preserve field reference in operators
		elif "`" in arg:
			if parsed := self.engine._parse_backtick_field_notation(arg):
				table_name, field_name = parsed
				self.engine.check_select_field_permission(table_name, field_name)
				return Table(f"tab{table_name}")[field_name]
			else:
				frappe.throw(
					_(
						"Invalid argument format: {0}. Only quoted string literals or simple field names are allowed."
					).format(arg),
					frappe.ValidationError,
				)

		# Check if it's a numeric string like "1" (for COUNT(1), etc.)
		elif arg.isdigit():
			return int(arg)

		elif self._is_valid_field_name(arg):
			self._check_function_field_permission(arg)
			return self.engine.table[arg]

		else:
			frappe.throw(
				_(
					"Invalid argument format: {0}. Only quoted string literals or simple field names are allowed."
				).format(arg),
				frappe.ValidationError,
			)

	def _is_valid_field_name(self, name: str) -> bool:
		"""Check if a string is a valid field name."""
		# Field names should only contain alphanumeric characters and underscores
		return SIMPLE_FIELD_PATTERN.match(name) is not None

	def _validate_alias(self, alias: str):
		"""Validate alias name for SQL injection."""
		if not isinstance(alias, str):
			frappe.throw(_("Alias must be a string"), frappe.ValidationError)

		alias = alias.strip()
		if not alias:
			frappe.throw(_("Empty alias is not allowed"), frappe.ValidationError)

		# Alias should be a simple identifier
		# Note: pypika wraps aliases in backticks, so anything without backticks is safe
		if not SIMPLE_FIELD_PATTERN.match(alias):
			frappe.throw(
				_("Invalid alias format: {0}. Alias must be a simple identifier.").format(alias),
				frappe.ValidationError,
			)

	def _check_function_field_permission(self, field_name: str):
		if self.engine.apply_permissions and self.engine.doctype:
			self.engine.check_select_field_permission(self.engine.doctype, field_name, self.engine.parent_doctype)
>>>>>>> 2af7628 (fix: enforce child field permissions in function expressions)
