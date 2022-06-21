import operator
import re
from ast import literal_eval
from functools import cached_property
from typing import Any, Callable, Dict, List, Tuple, Union

import frappe
from frappe import _
from frappe.boot import get_additional_filters_from_hooks
from frappe.model.db_query import get_timespan_date_range
from frappe.query_builder import Criterion, Field, Order, Table

TAB_PATTERN = re.compile("^tab")
WORDS_PATTERN = re.compile(r"\w+")


def like(key: Field, value: str) -> frappe.qb:
	"""Wrapper method for `LIKE`

	Args:
	        key (str): field
	        value (str): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `LIKE`
	"""
	return key.like(value)


def func_in(key: Field, value: Union[List, Tuple]) -> frappe.qb:
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


def func_not_in(key: Field, value: Union[List, Tuple]):
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


def func_between(key: Field, value: Union[List, Tuple]) -> frappe.qb:
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


def make_function(key: Any, value: Union[int, str]):
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


# default operators
OPERATOR_MAP: Dict[str, Callable] = {
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
	tables: dict = {}

	@cached_property
	def OPERATOR_MAP(self):
		# default operators
		all_operators = OPERATOR_MAP.copy()

		# update with site-specific custom operators
		additional_filters_config = get_additional_filters_from_hooks()

		if additional_filters_config:
			from frappe.utils.commands import warn

			warn("'filters_config' hook is not completely implemented yet in frappe.db.query engine")

		for _operator, function in additional_filters_config.items():
			if callable(function):
				all_operators.update({_operator.casefold(): function})
			elif isinstance(function, dict):
				all_operators[_operator.casefold()] = frappe.get_attr(function.get("get_field"))()["operator"]

		return all_operators

	def get_condition(self, table: Union[str, Table], **kwargs) -> frappe.qb:
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

	def get_table(self, table_name: Union[str, Table]) -> Table:
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

	def misc_query(self, table: str, filters: Union[List, Tuple] = None, **kwargs):
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

	def dict_query(
		self, table: str, filters: Dict[str, Union[str, int]] = None, **kwargs
	) -> frappe.qb:
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
		self, table: str, filters: Union[Dict[str, Union[str, int]], str, int] = None, **kwargs
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

	def set_fields(self, fields, **kwargs):
		fields = kwargs.get("pluck") if kwargs.get("pluck") else fields or "name"
		if isinstance(fields, list) and None in fields and Field not in fields:
			return None

		is_list = isinstance(fields, (list, tuple, set))
		if is_list and len(fields) == 1:
			fields = fields[0]
			is_list = False

		is_str = isinstance(fields, str)

		def add_functions(fields):
			from frappe.query_builder.functions import SqlFunctions

			sql_functions = [sql_function.value for sql_function in SqlFunctions]

			def get_function_objects(fields):
				from frappe.query_builder import functions

				def literal_eval_(literal):
					try:
						return literal_eval(literal)
					except (ValueError, SyntaxError):
						return literal

				func = fields.split("(")[0].casefold().split()
				func = [f for f in func if f in sql_functions][0]
				args = fields[len(func) + 1 : fields.index(")")].split(",")
				args = [Field(literal_eval_((arg.strip()))) for arg in args]
				return getattr(functions, func.capitalize())(*args)

			if is_str and any(
				[func in fields.casefold() and f"{func}(" in fields.casefold() for func in sql_functions]
			):
				function_objects = []
				return function_objects or [get_function_objects(fields)]
			else:
				functions = []
				for field in fields:
					if not issubclass(type(field), Criterion):
						if any(
							[func in field.casefold() and f"{func}(" in field.casefold() for func in sql_functions]
						):
							functions.append(field.casefold())
				return [get_function_objects(function) for function in functions]

		function_objects = (
			add_functions(fields=fields) if not issubclass(type(fields), Criterion) else []
		)
		for function in function_objects:
			if is_str:
				fields = re.sub(
					r"\(.*?\)", "", fields.casefold().replace(str(type(function).__name__).strip().casefold(), "")
				)

			else:
				updated_fields = []
				for field in fields:
					if isinstance(field, str):
						updated_fields.append(
							re.sub(r"\(.*?\)", "", field)
							.strip()
							.casefold()
							.replace(str(type(function).__name__).strip().casefold(), "")
						)
					else:
						updated_fields.append(field)

					fields = updated_fields

		if is_str and "," in fields:
			fields = fields.split(",")
			fields = [field.replace(" ", "") if "as" not in field else field for field in fields]

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

	def get_sql(
		self,
		table: str,
		fields: Union[List, Tuple],
		filters: Union[Dict[str, Union[str, int]], str, int, List[Union[List, str, int]]] = None,
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
