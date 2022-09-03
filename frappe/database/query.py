import operator
import re
from ast import literal_eval
from functools import cached_property
from types import BuiltinFunctionType
from typing import TYPE_CHECKING, Callable

from pypika.dialects import MySQLQueryBuilder, PostgreSQLQueryBuilder

import frappe
from frappe import _
from frappe.database.utils import is_pypika_function_object
from frappe.model.db_query import get_timespan_date_range
from frappe.query_builder import Criterion, Field, Order, Table, functions
from frappe.query_builder.functions import Function, SqlFunctions
from frappe.query_builder.utils import PseudoColumn

if TYPE_CHECKING:
	from frappe.query_builder import DocType

TAB_PATTERN = re.compile("^tab")
WORDS_PATTERN = re.compile(r"\w+")
BRACKETS_PATTERN = re.compile(r"\(.*?\)|$")
SQL_FUNCTIONS = [sql_function.value for sql_function in SqlFunctions]
COMMA_PATTERN = re.compile(r",\s*(?![^()]*\))")
TABLE_PATTERN = re.compile(r"`\btab\w+")


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
	if isinstance(value, str):
		value = value.split(",")
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


def func_not_in(key: Field, value: list | tuple | str):
	"""Wrapper method for `NOT IN`

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `NOT IN`
	"""
	if isinstance(value, str):
		value = value.split(",")
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


def literal_eval_(literal):
	try:
		return literal_eval(literal)
	except (ValueError, SyntaxError):
		return literal


def has_function(field):
	_field = field.casefold() if (isinstance(field, str) and "`" not in field) else field
	if not issubclass(type(_field), Criterion):
		if any([f"{func}(" in _field for func in SQL_FUNCTIONS]) or "(" in _field:
			return True


def table_from_string(table: str) -> "DocType":
	table_name = table.split("`", maxsplit=1)[1].split(".")[0][3:]
	return frappe.qb.DocType(table_name=table_name.replace("`", ""))


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
	tables: dict[str, str] = {}

	@cached_property
	def OPERATOR_MAP(self):
		# default operators
		all_operators = OPERATOR_MAP.copy()

		# TODO: update with site-specific custom operators / removed previous buggy implementation
		if frappe.get_hooks("filters_config"):
			from frappe.utils.commands import warn

			warn(
				"The 'filters_config' hook used to add custom operators is not yet implemented"
				" in frappe.db.query engine. Use db_query (frappe.get_list) instead."
			)

		return all_operators

	def get_condition(self, table: str | Table, **kwargs) -> frappe.qb:
		"""Get initial table object

		Args:
		        table (str): DocType

		Returns:
		        frappe.qb: DocType with initial condition
		"""
		table_object = self.get_table(table)
		if kwargs.get("update"):
			return frappe.qb.update(table_object)
		if kwargs.get("into"):
			return frappe.qb.into(table_object)
		return frappe.qb.from_(table_object)

	def get_table(self, table_name: str | Table) -> Table:
		if isinstance(table_name, Table):
			return table_name
		table_name = table_name.strip('"').strip("'")
		if table_name not in self.tables:
			self.tables[table_name] = frappe.qb.DocType(table_name)
		return self.tables[table_name]

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
		if kwargs.get("orderby") and kwargs.get("orderby") != "KEEP_DEFAULT_ORDERING":
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
						conditions = self.make_function_for_filters(filters[0], filters[2])
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
		if isinstance(table, str):
			table = frappe.qb.DocType(table)
		if not filters:
			conditions = self.add_conditions(conditions, **kwargs)
			return conditions

		for key, value in filters.items():
			if isinstance(value, bool):
				filters.update({key: str(int(value))})

		filters = {
			(self.get_function_object(k) if has_function(k) else k): v for k, v in filters.items()
		}
		for key in filters:
			value = filters.get(key)
			_operator = self.OPERATOR_MAP["="]

			if not isinstance(key, str):
				conditions = conditions.where(self.make_function_for_filters(key, value))
				continue
			if isinstance(value, (list, tuple)):
				_operator = self.OPERATOR_MAP[value[0].casefold()]
				_value = value[1] if value[1] else ("",)
				conditions = conditions.where(_operator(getattr(table, key), _value))
			else:
				if value is not None:
					conditions = conditions.where(_operator(getattr(table, key), value))
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
			filters = {"name": str(filters)}

		if isinstance(filters, Criterion):
			criterion = self.criterion_query(table, filters, **kwargs)

		elif isinstance(filters, (list, tuple)):
			criterion = self.misc_query(table, filters, **kwargs)

		else:
			criterion = self.dict_query(filters=filters, table=table, **kwargs)

		return criterion

	def make_function_for_filters(self, key, value: int | str):
		value = list(value)
		if isinstance(value[1], str) and has_function(value[1]):
			value[1] = self.get_function_object(value[1])
		return OPERATOR_MAP[value[0].casefold()](key, value[1])

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

				field = (
					(Field(initial_fields) if "`" not in initial_fields else PseudoColumn(initial_fields))
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

	def function_objects_from_string(self, fields):
		fields = list(map(lambda str: str.strip(), COMMA_PATTERN.split(fields)))
		return self.function_objects_from_list(fields=fields)

	def function_objects_from_list(self, fields):
		functions = []
		for field in fields:
			field = field.casefold() if (isinstance(field, str) and "`" not in field) else field
			if not issubclass(type(field), Criterion):
				if any([f"{func}(" in field for func in SQL_FUNCTIONS]) or "(" in field:
					functions.append(field)

		return [self.get_function_object(function) for function in functions]

	def remove_string_functions(self, fields, function_objects):
		"""Remove string functions from fields which have already been converted to function objects"""

		def _remove_string_aliasing(function, fields: list | str):
			if function.alias:
				to_replace = " as " + function.alias.casefold()
				if to_replace in fields:
					fields = fields.replace(to_replace, "")
				elif " as " + f"`{function.alias.casefold()}" in fields:
					fields = fields.replace(" as " + f"`{function.alias.casefold()}`", "")
			return fields

		for function in function_objects:
			if isinstance(fields, str):
				fields = _remove_string_aliasing(function, fields)
				fields = BRACKETS_PATTERN.sub("", re.sub(function.name, "", fields, flags=re.IGNORECASE))
				# Check if only comma is left in fields after stripping functions.
				if "," in fields and (len(fields.strip()) == 1):
					fields = ""
			else:
				updated_fields = []
				for field in fields:
					if isinstance(field, str):
						field = _remove_string_aliasing(function, field)
						substituted_string = (
							BRACKETS_PATTERN.sub("", field).strip().casefold()
							if "`" not in field
							else BRACKETS_PATTERN.sub("", field).strip()
						)
						# This is done to avoid casefold of table name.
						if substituted_string.casefold() == function.name.casefold():
							replaced_string = substituted_string.casefold().replace(function.name.casefold(), "")
						else:
							replaced_string = substituted_string.replace(function.name.casefold(), "")
						updated_fields.append(replaced_string)
				fields = [field for field in updated_fields if field]
		return fields

	def get_fieldnames_from_child_table(self, doctype, fields):
		# Hacky and flaky implementation of implicit joins.
		# convert child_table.fieldname to `tabChild DocType`.`fieldname`
		for idx, field in enumerate(fields, start=0):
			if "." in field and "tab" not in field:
				alias = None
				if " as " in field:
					field, alias = field.split(" as ")
				self.fieldname, linked_fieldname = field.split(".")
				linked_field = frappe.get_meta(doctype, cached=True).get_field(self.fieldname)
				try:
					self.linked_doctype = linked_field.options
				except AttributeError:
					return fields
				field = f"`tab{self.linked_doctype}`.`{linked_fieldname}`"
				if alias:
					field = f"{field} as {alias}"
				fields[idx] = field

		return fields

	def set_fields(self, table, fields, **kwargs) -> list:
		fields = kwargs.get("pluck") if kwargs.get("pluck") else fields or "name"
		if isinstance(fields, list) and None in fields and Field not in fields:
			return None
		function_objects = []
		is_list = isinstance(fields, (list, tuple, set))
		if is_list and len(fields) == 1:
			fields = fields[0]
			is_list = False

		if is_list:
			function_objects += self.function_objects_from_list(fields=fields)

		is_str = isinstance(fields, str)
		if is_str:
			fields = fields.casefold() if "`" not in fields else fields
			function_objects += self.function_objects_from_string(fields=fields)

		fields = self.remove_string_functions(fields, function_objects)

		if is_str and "," in fields:
			fields = [field.replace(" ", "") if "as" not in field else field for field in fields.split(",")]
			is_list, is_str = True, False

		if is_str:
			if fields == "*":
				return fields
			if "`" in fields:
				fields = PseudoColumn(fields)
			if " as " in str(fields):
				fields, reference = str(fields).split(" as ")
				if "`" in str(fields):
					fields = PseudoColumn(f"{fields} as {reference}")
				else:
					fields = Field(fields).as_(reference)

		if not is_str and fields:
			if issubclass(type(fields), Criterion):
				return fields
			updated_fields = []
			if "*" in fields:
				return fields
			# fields = self.get_fieldnames_from_child_table(doctype=table, fields=fields)
			for field in fields:
				if not isinstance(field, Criterion) and field:
					if " as " in field:
						field, reference = field.split(" as ")
						if "`" in field:
							updated_fields.append(PseudoColumn(f"{field} as {reference}"))
						else:
							updated_fields.append(Field(field.strip()).as_(reference))

					elif "`" in str(field):
						updated_fields.append(PseudoColumn(field.strip()))
					else:
						updated_fields.append(Field(field))

			fields = updated_fields

		# Need to check instance again since fields modified.
		if not isinstance(fields, (list, tuple, set)):
			fields = [fields] if fields else []

		fields.extend(function_objects)
		return fields

	def join_(self, criterion, fields, table, join):
		"""Handles all join operations on criterion objects"""
		has_join = False
		if not isinstance(fields, Criterion):
			for field in fields:
				# Only perform this bit if foreign doctype in fields
				if (
					not is_pypika_function_object(field)
					and str(field).startswith("`tab")
					and (f"`tab{table}`" not in str(field))
				):
					join_table = table_from_string(str(field))
					if self.fieldname:
						criterion = criterion.left_join(join_table).on(
							getattr(join_table, "name") == getattr(frappe.qb.DocType(table), self.fieldname)
						)
					else:
						criterion = criterion.left_join(join_table).on(
							getattr(join_table, "parent") == getattr(frappe.qb.DocType(table), "name")
						)
					has_join = True

			if has_join:
				for idx, field in enumerate(fields):
					if not is_pypika_function_object(field):
						field = field if isinstance(field, str) else field.get_sql()
						if not TABLE_PATTERN.search(str(field)):
							fields[idx] = getattr(frappe.qb.DocType(table), field)
					else:
						field.args = [getattr(frappe.qb.DocType(table), arg.get_sql()) for arg in field.args]
						field.args[0] = getattr(frappe.qb.DocType(table), field.args[0].get_sql())
						fields[idx] = field

		if len(self.tables) > 1:
			primary_table = self.tables.pop(table)
			for table_object in self.tables.values():
				criterion = getattr(criterion, join)(table_object).on(
					table_object.parent == primary_table.name
				)
				has_join = True

		return criterion, fields

	def get_query(
		self,
		table: str,
		fields: list | tuple,
		filters: dict[str, str | int] | str | int | list[list | str | int] = None,
		**kwargs,
	) -> MySQLQueryBuilder | PostgreSQLQueryBuilder:
		# Clean up state before each query
		self.tables = {}
		self.linked_doctype = None
		self.fieldname = None

		fields = self.set_fields(table, kwargs.get("field_objects") or fields, **kwargs)
		criterion = self.build_conditions(table, filters, **kwargs)
		join = kwargs.get("join").replace(" ", "_") if kwargs.get("join") else "left_join"
		criterion, fields = self.join_(criterion=criterion, fields=fields, table=table, join=join)

		if isinstance(fields, (list, tuple)):
			query = criterion.select(*fields)

		elif isinstance(fields, Criterion):
			query = criterion.select(fields)

		else:
			query = criterion.select(fields)

		return query


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
