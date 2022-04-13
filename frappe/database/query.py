import operator
import re
from typing import Any, Dict, List, Tuple, Union

import frappe
from frappe import _
from frappe.query_builder import Criterion, Field, Order


def like(key: str, value: str) -> frappe.qb:
	"""Wrapper method for `LIKE`

	Args:
	        key (str): field
	        value (str): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `LIKE`
	"""
	return Field(key).like(value)


def func_in(key: str, value: Union[List, Tuple]) -> frappe.qb:
	"""Wrapper method for `IN`

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `IN`
	"""
	return Field(key).isin(value)


def not_like(key: str, value: str) -> frappe.qb:
	"""Wrapper method for `NOT LIKE`

	Args:
	        key (str): field
	        value (str): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `NOT LIKE`
	"""
	return Field(key).not_like(value)


def func_not_in(key: str, value: Union[List, Tuple]):
	"""Wrapper method for `NOT IN`

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `NOT IN`
	"""
	return Field(key).notin(value)


def func_regex(key: str, value: str) -> frappe.qb:
	"""Wrapper method for `REGEX`

	Args:
	        key (str): field
	        value (str): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `REGEX`
	"""
	return Field(key).regex(value)


def func_between(key: str, value: Union[List, Tuple]) -> frappe.qb:
	"""Wrapper method for `BETWEEN`

	Args:
	        key (str): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: `frappe.qb object with `BETWEEN`
	"""
	return Field(key)[slice(*value)]


def make_function(key: Any, value: Union[int, str]):
	"""returns fucntion query

	Args:
	        key (Any): field
	        value (Union[int, str]): criterion

	Returns:
	        frappe.qb: frappe.qb object
	"""
	return OPERATOR_MAP[value[0]](key, value[1])


def change_orderby(order: str):
	"""Convert orderby to standart Order object

	Args:
	        order (str): Field, order

	Returns:
	        tuple: field, order
	"""
	order = order.split()
	if order[1].lower() == "asc":
		orderby, order = order[0], Order.asc
		return orderby, order
	orderby, order = order[0], Order.desc
	return orderby, order


OPERATOR_MAP = {
	"+": operator.add,
	"=": operator.eq,
	"-": operator.sub,
	"!=": operator.ne,
	"<": operator.lt,
	">": operator.gt,
	"<=": operator.le,
	">=": operator.ge,
	"in": func_in,
	"not in": func_not_in,
	"like": like,
	"not like": not_like,
	"regex": func_regex,
	"between": func_between,
}


class Query:
	def get_condition(self, table: str, **kwargs) -> frappe.qb:
		"""Get initial table object

		Args:
		        table (str): DocType

		Returns:
		        frappe.qb: DocType with initial condition
		"""
		if kwargs.get("update"):
			return frappe.qb.update(table)
		if kwargs.get("into"):
			return frappe.qb.into(table)
		return frappe.qb.from_(table)

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
		if kwargs.get("orderby"):
			orderby = kwargs.get("orderby")
			order = kwargs.get("order") if kwargs.get("order") else Order.desc
			if isinstance(orderby, str) and len(orderby.split()) > 1:
				orderby, order = change_orderby(orderby)
			conditions = conditions.orderby(orderby, order=order)

		if kwargs.get("limit"):
			conditions = conditions.limit(kwargs.get("limit"))

		if kwargs.get("distinct"):
			conditions = conditions.distinct()

		if kwargs.get("for_update"):
			conditions = conditions.for_update()

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
				if not isinstance(f, (list, tuple)):
					_operator = OPERATOR_MAP[filters[1]]
					if not isinstance(filters[0], str):
						conditions = make_function(filters[0], filters[2])
						break
					conditions = conditions.where(_operator(Field(filters[0]), filters[2]))
					break
				else:
					_operator = OPERATOR_MAP[f[1]]
					conditions = conditions.where(_operator(Field(f[0]), f[2]))

		conditions = self.add_conditions(conditions, **kwargs)
		return conditions

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

		for key in filters:
			value = filters.get(key)
			_operator = OPERATOR_MAP["="]

			if not isinstance(key, str):
				conditions = conditions.where(make_function(key, value))
				continue
			if isinstance(value, (list, tuple)):
				if isinstance(value[1], (list, tuple)) or value[0] in list(OPERATOR_MAP.keys())[-4:]:
					_operator = OPERATOR_MAP[value[0]]
					conditions = conditions.where(_operator(key, value[1]))
				else:
					_operator = OPERATOR_MAP[value[0]]
					conditions = conditions.where(_operator(Field(key), value[1]))
			else:
				if value is not None:
					conditions = conditions.where(_operator(Field(key), value))
				else:
					_table = conditions._from[0]
					field = getattr(_table, key)
					conditions = conditions.where(field.isnull())

		conditions = self.add_conditions(conditions, **kwargs)
		return conditions

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

	def get_sql(
		self,
		table: str,
		fields: Union[List, Tuple],
		filters: Union[Dict[str, Union[str, int]], str, int] = None,
		**kwargs
	):
		criterion = self.build_conditions(table, filters, **kwargs)
		if isinstance(fields, (list, tuple)):
			query = criterion.select(*kwargs.get("field_objects", fields))

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
			dt = re.sub("^tab", "", dt)
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
		return [table for table in re.findall(r"\w+", query) if table.startswith("tab")]
