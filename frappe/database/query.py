import operator
import re
from ast import literal_eval
from functools import cached_property
from types import BuiltinFunctionType
<<<<<<< HEAD
from typing import Any, Callable
=======
from typing import TYPE_CHECKING, Callable

import sqlparse
from pypika.dialects import MySQLQueryBuilder, PostgreSQLQueryBuilder
from pypika.queries import QueryBuilder
>>>>>>> 726fcfdb79 (refactor: qb.engine)

import frappe
from frappe import _
from frappe.database.utils import DefaultOrderBy
from frappe.model.db_query import get_timespan_date_range
from frappe.query_builder import Criterion, Field, Order, Table, functions
from frappe.query_builder.functions import Function, SqlFunctions

TAB_PATTERN = re.compile("^tab")
WORDS_PATTERN = re.compile(r"\w+")
BRACKETS_PATTERN = re.compile(r"\(.*?\)|$")
SQL_FUNCTIONS = [sql_function.value for sql_function in SqlFunctions]
COMMA_PATTERN = re.compile(r",\s*(?![^()]*\))")


def like(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `LIKE`

	Args:
	        key (str): field
	        value (str): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `LIKE`
	"""
	return key.like(value)


def func_in(key: Field, value: list | tuple) -> frappe.qb:
	"""Wrapper method for `IN`

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `IN`
	"""
	return key.isin(value)


def not_like(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `NOT LIKE`

	Args:
	        key (str): field
	        value (str): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `NOT LIKE`
	"""
	return key.not_like(value)


def func_not_in(key: Field, value: list | tuple):
	"""Wrapper method for `NOT IN`

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `NOT IN`
	"""
	return key.notin(value)


def func_regex(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `REGEX`

	Args:
	        key (str): field
	        value (str): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `REGEX`
	"""
	return key.regex(value)


def func_between(key: Field, value: list | tuple) -> frappe.qb:
	"""Wrapper method for `BETWEEN`

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `BETWEEN`
	"""
	return key[slice(*value)]


def func_is(key, value):
	"Wrapper for IS"
	return key.isnotnull() if value.lower() == "set" else key.isnull()


def func_timespan(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `TIMESPAN`

	Args:
	        key (str): field
	        value (str): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `TIMESPAN`
	"""

	return func_between(key, get_timespan_date_range(value))


<<<<<<< HEAD
def make_function(key: Any, value: int | str):
	"""returns fucntion query

	Args:
	        key (Any): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: frappe.qb object
	"""
	return OPERATOR_MAP[value[0].casefold()](key, value[1])


def change_orderby(order: str):
	"""Convert orderby to standart Order object

	Args:
	        order (str): Field, order

	Returns:
	        tuple: field, order
	"""
	order = order.split()

	try:
		if order[1].lower() == "asc":
			return order[0], Order.asc
	except IndexError:
		pass

	return order[0], Order.desc


=======
>>>>>>> e272adb0b1 (fix: use table.field instead Field('field'))
def literal_eval_(literal):
	try:
		return literal_eval(literal)
	except (ValueError, SyntaxError):
		return literal


<<<<<<< HEAD
=======
def has_function(field):
	_field = field.casefold() if (isinstance(field, str) and "`" not in field) else field
	if not issubclass(type(_field), Criterion):
		if any([f"{func}(" in _field for func in SQL_FUNCTIONS]):
			return True


def get_nested_set_hierarchy_result(doctype: str, name: str, hierarchy: str):
	table = frappe.qb.DocType(doctype)
	try:
		lft, rgt = frappe.qb.from_(table).select("lft", "rgt").where(table.name == name).run()[0]
	except IndexError:
		lft, rgt = None, None

	if hierarchy in ("descendants of", "not descendants of"):
		result = (
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.lft > lft)
			.where(table.rgt < rgt)
			.orderby(table.lft, order=Order.asc)
			.run()
		)
	else:
		# Get ancestor elements of a DocType with a tree structure
		result = (
			frappe.qb.from_(table)
			.select(table.name)
			.where(table.lft < lft)
			.where(table.rgt > rgt)
			.orderby(table.lft, order=Order.desc)
			.run()
		)
	return result


>>>>>>> 726fcfdb79 (refactor: qb.engine)
# default operators
OPERATOR_MAP: dict[str, Callable] = {
	"+": operator.add,
	"=": operator.eq,
	"-": operator.sub,
	"!=": operator.ne,
	"<": operator.lt,
	">": operator.gt,
	"<=": operator.le,
	"=<": operator.le,
	">=": operator.ge,
	"=>": operator.ge,
	"/": operator.truediv,
	"*": operator.mul,
	"in": func_in,
	"not in": func_not_in,
	"like": like,
	"not like": not_like,
	"regex": func_regex,
	"between": func_between,
	"is": func_is,
	"timespan": func_timespan,
	# TODO: Add support for nested set
	# TODO: Add support for custom operators (WIP) - via filters_config hooks
}


class Engine:
	def __init__(self):
		self.tables: dict[str, str] = {}

	def get_query(
		self,
		table: str,
		fields: list | tuple | None = None,
		filters: dict[str, str | int] | str | int | list[list | str | int] | None = None,
		pluck: str | None = None,
		order_by: str | None = None,
		group_by: str | None = None,
		limit: int | None = None,
		offset: int | None = None,
		distinct: bool = False,
		for_update: bool = False,
		update: bool = False,
		into: bool = False,
		delete: bool = False,
	) -> MySQLQueryBuilder | PostgreSQLQueryBuilder:
		# Clean up state before each query
		self.is_mariadb = frappe.db.db_type == "mariadb"
		self.is_postgres = frappe.db.db_type == "postgres"
		self.tables = {}
		self.implicit_joins = set()

		self.doctype = table
		self.table = self.get_table(table)

		if update:
			self.query = frappe.qb.update(self.table)
		elif into:
			self.query = frappe.qb.into(self.table)
		elif delete:
			self.query = frappe.qb.from_(self.table).delete()
		else:
			self.query = frappe.qb.from_(self.table)

		self.fields = self.parse_fields(fields)
		if not self.fields:
			self.fields = [getattr(self.table, pluck or "name")]

		for field in self.fields:
			if isinstance(field, DynamicTableField):
				self.query = field.apply_select(self.query)
			else:
				self.query = self.query.select(field)

		self.apply_filters(filters)
		self.apply_implicit_joins()
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

		return self.query

	def get_table(self, table_name: str | Table) -> Table:
		if isinstance(table_name, Table):
			return table_name
		table_name = table_name.strip('"').strip("'")
		if table_name not in self.tables:
			self.tables[table_name] = frappe.qb.DocType(table_name)
		return self.tables[table_name]

<<<<<<< HEAD
	def criterion_query(self, table: str, criterion: Criterion, **kwargs) -> frappe.qb:
		"""Generate filters from Criterion objects

		Args:
		        table (str): DocType
		        criterion (Criterion): Filters

		Returns:
		        frappe.qb: condition object
		"""
		condition = self.add_conditions(self.get_condition(table, **kwargs), **kwargs)
		return condition.where(criterion)

	def add_conditions(self, conditions: frappe.qb, **kwargs):
		"""Adding additional conditions

		Args:
		        conditions (frappe.qb): built conditions

		Returns:
		        conditions (frappe.qb): frappe.qb object
		"""
		if kwargs.get("orderby") and kwargs.get("orderby") != DefaultOrderBy:
			orderby = kwargs.get("orderby")
			if isinstance(orderby, str) and len(orderby.split()) > 1:
				for ordby in orderby.split(","):
					if ordby := ordby.strip():
						orderby, order = change_orderby(ordby)
						conditions = conditions.orderby(orderby, order=order)
			else:
				conditions = conditions.orderby(orderby, order=kwargs.get("order") or Order.desc)

		if kwargs.get("limit"):
			conditions = conditions.limit(kwargs.get("limit"))
			conditions = conditions.offset(kwargs.get("offset", 0))

		if kwargs.get("distinct"):
			conditions = conditions.distinct()

		if kwargs.get("for_update"):
			conditions = conditions.for_update()

		if kwargs.get("groupby"):
			conditions = conditions.groupby(kwargs.get("groupby"))

		return conditions

	def misc_query(self, table: str, filters: list | tuple = None, **kwargs):
		"""Build conditions using the given Lists or Tuple filters

		Args:
		        table (str): DocType
		        filters (Union[List, Tuple], optional): Filters. Defaults to None.
		"""
		conditions = self.get_condition(table, **kwargs)
		if not filters:
			return conditions
		if isinstance(filters, list):
			for f in filters:
				if isinstance(f, (list, tuple)):
					_operator = self.OPERATOR_MAP[f[-2].casefold()]
					if len(f) == 4:
						table_object = self.get_table(f[0])
						_field = table_object[f[1]]
					else:
						_field = Field(f[0])
					conditions = conditions.where(_operator(_field, f[-1]))
				elif isinstance(f, dict):
					conditions = self.dict_query(table, f, **kwargs)
				else:
					_operator = self.OPERATOR_MAP[filters[1].casefold()]
					if not isinstance(filters[0], str):
						conditions = make_function(filters[0], filters[2])
						break
					conditions = conditions.where(_operator(Field(filters[0]), filters[2]))
					break

		return self.add_conditions(conditions, **kwargs)

	def dict_query(self, table: str, filters: dict[str, str | int] = None, **kwargs) -> frappe.qb:
		"""Build conditions using the given dictionary filters

		Args:
		        table (str): DocType
		        filters (Dict[str, Union[str, int]], optional): Filters. Defaults to None.

		Returns:
		        frappe.qb: conditions object
		"""
		conditions = self.get_condition(table, **kwargs)
		if not filters:
			conditions = self.add_conditions(conditions, **kwargs)
			return conditions

		for key, value in filters.items():
			if isinstance(value, bool):
				filters.update({key: str(int(value))})

		for key in filters:
			value = filters.get(key)
			_operator = self.OPERATOR_MAP["="]

			if not isinstance(key, str):
				conditions = conditions.where(make_function(key, value))
				continue
			if isinstance(value, (list, tuple)):
				_operator = self.OPERATOR_MAP[value[0].casefold()]
				_value = value[1] if value[1] else ("",)
				conditions = conditions.where(_operator(Field(key), _value))
			else:
				if value is not None:
					conditions = conditions.where(_operator(Field(key), value))
				else:
					_table = conditions._from[0]
					field = getattr(_table, key)
					conditions = conditions.where(field.isnull())

		return self.add_conditions(conditions, **kwargs)

	def build_conditions(
		self, table: str, filters: dict[str, str | int] | str | int = None, **kwargs
	) -> frappe.qb:
		"""Build conditions for sql query

		Args:
		        filters (Union[Dict[str, Union[str, int]], str, int]): conditions in Dict
		        table (str): DocType

		Returns:
		        frappe.qb: frappe.qb conditions object
		"""
		if isinstance(filters, int) or isinstance(filters, str):
=======
	def apply_filters(
		self, filters: dict[str, str | int | list] | str | int | list[list] | None = None
	):
		if not filters:
			return

		if isinstance(filters, (str, int)):
>>>>>>> 726fcfdb79 (refactor: qb.engine)
			filters = {"name": str(filters)}

		if isinstance(filters, Criterion):
			self.query = self.query.where(filters)

		elif isinstance(filters, dict):
			self.apply_dict_filters(filters)

		elif isinstance(filters, (list, tuple)):
			self.apply_list_filters(filters)

	def apply_list_filters(self, filters: list[list]):
		for filter in filters:
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
		for key in filters:
			value = filters.get(key)
			self._apply_filter(key, value)

	def _apply_filter(
		self, field: str, value: str | int | list | None, operator: str = "=", doctype: str | None = None
	):
		_field = field
		_value = value
		_operator = operator

		if dynamic_field := DynamicTableField.parse(field, self.doctype):
			# apply implicit join if link field's field is referenced
			self.query = dynamic_field.apply_join(self.query)
			_field = dynamic_field.field
		elif has_function(field):
			_field = self.get_function_object(field)
		elif not doctype or doctype == self.doctype:
			_field = self.table[field]
		elif doctype:
			_field = self.get_table(doctype)[field]

		# apply implicit join if child table is referenced
		if doctype and doctype != self.doctype:
			meta = frappe.get_meta(doctype)
			table = self.get_table(doctype)
			if meta.istable and not self.query.is_joined(table):
				self.query = self.query.left_join(table).on(
					(table.parent == self.table.name) & (table.parenttype == self.doctype)
				)

		if isinstance(_value, (str, int)):
			_value = str(_value)
		elif isinstance(_value, (list, tuple)):
			_operator, _value = _value
		elif isinstance(_value, bool):
			_value = int(_value)

		if isinstance(_value, str) and has_function(_value):
			_value = self.get_function_object(_value)

		# Nested set
		if _operator in self.OPERATOR_MAP["nested_set"]:
			hierarchy = _operator
			docname = _value
			result = get_nested_set_hierarchy_result(self.doctype, docname, hierarchy)
			operator_fn = (
				self.OPERATOR_MAP["not in"]
				if hierarchy in ("not ancestors of", "not descendants of")
				else self.OPERATOR_MAP["in"]
			)
			if result:
				result = list(itertools.chain.from_iterable(result))
				self.query = self.query.where(operator_fn(_field, result))
			else:
				self.query = self.query.where(operator_fn(_field, ("",)))
			return

		operator_fn = self.OPERATOR_MAP[_operator.casefold()]
		if _value is None and isinstance(_field, Field):
			self.query = self.query.where(_field.isnull())
		else:
<<<<<<< HEAD
			criterion = self.dict_query(filters=filters, table=table, **kwargs)

		return criterion
=======
			self.query = self.query.where(operator_fn(_field, _value))
>>>>>>> 726fcfdb79 (refactor: qb.engine)

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
								*map(lambda field: Field(field.strip()), arg.split(_operator)),
							)

				field = Field(initial_fields) if not has_primitive_operator else field
			else:
				field = initial_fields

			_args.append(field)
		try:
			return getattr(functions, func)(*_args, alias=alias or None)
		except AttributeError:
			# Fall back for functions not present in `SqlFunctions``
			return Function(func, *_args, alias=alias or None)

<<<<<<< HEAD
	def function_objects_from_string(self, fields):
		fields = list(map(lambda str: str.strip(), COMMA_PATTERN.split(fields)))
		return self.function_objects_from_list(fields=fields)

	def function_objects_from_list(self, fields):
		functions = []
		for field in fields:
			field = field.casefold() if isinstance(field, str) else field
			if not issubclass(type(field), Criterion):
				if any([f"{func}(" in field for func in SQL_FUNCTIONS]) or "(" in field:
					functions.append(field)

		return [self.get_function_object(function) for function in functions]

	def remove_string_functions(self, fields, function_objects):
		"""Remove string functions from fields which have already been converted to function objects"""
		for function in function_objects:
			if isinstance(fields, str):
				if function.alias:
					fields = fields.replace(" as " + function.alias.casefold(), "")
				fields = BRACKETS_PATTERN.sub("", fields.replace(function.name.casefold(), ""))
				# Check if only comma is left in fields after stripping functions.
				if "," in fields and (len(fields.strip()) == 1):
					fields = ""
			else:
				updated_fields = []
				for field in fields:
					if isinstance(field, str):
						if function.alias:
							field = field.replace(" as " + function.alias.casefold(), "")
						field = (
							BRACKETS_PATTERN.sub("", field).strip().casefold().replace(function.name.casefold(), "")
						)
						updated_fields.append(field)

					fields = [field for field in updated_fields if field]

		return fields

	def set_fields(self, fields, **kwargs):
		fields = kwargs.get("pluck") if kwargs.get("pluck") else fields or "name"
		if isinstance(fields, list) and None in fields and Field not in fields:
			return None

		function_objects = []

		is_list = isinstance(fields, (list, tuple, set))
		if is_list and len(fields) == 1:
			fields = fields[0]
			is_list = False
=======
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
>>>>>>> 726fcfdb79 (refactor: qb.engine)

		if not isinstance(fields, (list, tuple)):
			fields = [fields]

<<<<<<< HEAD
		is_str = isinstance(fields, str)
		if is_str:
			fields = fields.casefold()
			function_objects += self.function_objects_from_string(fields=fields)

		fields = self.remove_string_functions(fields, function_objects)

		if is_str and "," in fields:
			fields = [field.replace(" ", "") if "as" not in field else field for field in fields.split(",")]
			is_list, is_str = True, False

		if is_str:
			if fields == "*":
				return fields
			if " as " in fields:
				fields, reference = fields.split(" as ")
				fields = Field(fields).as_(reference)

		if not is_str and fields:
			if issubclass(type(fields), Criterion):
				return fields
			updated_fields = []
			if "*" in fields:
				return fields
			for field in fields:
				if not isinstance(field, Criterion) and field:
					if " as " in field:
						field, reference = field.split(" as ")
						updated_fields.append(Field(field.strip()).as_(reference))
					else:
						updated_fields.append(Field(field))

					fields = updated_fields

		# Need to check instance again since fields modified.
		if not isinstance(fields, (list, tuple, set)):
			fields = [fields] if fields else []

		fields.extend(function_objects)
		return fields

	def get_query(
		self,
		table: str,
		fields: list | tuple,
		filters: dict[str, str | int] | str | int | list[list | str | int] = None,
		**kwargs,
	):
		# Clean up state before each query
		self.tables = {}
		criterion = self.build_conditions(table, filters, **kwargs)
		fields = self.set_fields(kwargs.get("field_objects") or fields, **kwargs)

		join = kwargs.get("join").replace(" ", "_") if kwargs.get("join") else "left_join"

		if len(self.tables) > 1:
			primary_table = self.tables[table]
			del self.tables[table]
			for table_object in self.tables.values():
				criterion = getattr(criterion, join)(table_object).on(
					table_object.parent == primary_table.name
				)
=======
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

	def apply_implicit_joins(self):
		for d in self.implicit_joins:
			doctype, join_type = d
			table = self.get_table(doctype)
			if join_type == "child":
				self.query = self.query.left_join(table).on(
					(table.parent == self.table.name) & (table.parenttype == self.doctype)
				)

	def apply_order_by(self, order_by: str | None):
		if not order_by or order_by == "KEEP_DEFAULT_ORDERING":
			return
		for declaration in order_by.split(","):
			if _order_by := declaration.strip():
				parts = _order_by.split(" ")
				order_field, order_direction = parts[0], parts[1] if len(parts) > 1 else "asc"
				order_direction = Order.asc if order_direction.lower() == "asc" else Order.desc
				self.query = self.query.orderby(order_field, order=order_direction)

	@cached_property
	def OPERATOR_MAP(self):
		# default operators
		all_operators = OPERATOR_MAP.copy()

		# TODO: update with site-specific custom operators / removed previous buggy implementation
		if frappe.get_hooks("filters_config"):
			from frappe.utils.commands import warn
>>>>>>> 726fcfdb79 (refactor: qb.engine)

			warn(
				"The 'filters_config' hook used to add custom operators is not yet implemented"
				" in frappe.db.query engine. Use db_query (frappe.get_list) instead."
			)

		return all_operators


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
