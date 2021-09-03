import operator
from typing import Any, Dict, List, Tuple, Union

import frappe
from frappe.query_builder import Criterion, Order


class Query:
	def __init__(self):
		self.operator_map = {
			"+": operator.add,
			"=": operator.eq,
			"-": operator.sub,
			"!=": operator.ne,
			"<": operator.lt,
			">": operator.gt,
			"<=": operator.le,
			">=": operator.ge,
			"in": self.func_in,
			"not in": self.func_not_in,
			"like": self.like,
			"not like": self.not_like,
			"regex": self.func_regex,
			"between": self.func_between
		}


	@staticmethod
	def like(key: str, value: str) -> frappe.qb:
		"""Wrapper method for `LIKE`

		Args:
				key (str): field
				value (ANy): criterion

		Returns:
				frappe.qb: `frappe.qb object with `LIKE`
		"""
		return frappe.qb.Field(key).like(value)

	@staticmethod
	def func_in(key: str, value: Union[List, Tuple]) -> frappe.qb:
		"""Wrapper method for `IN`

		Args:
				key (str): field
				value (ANy): criterion

		Returns:
				frappe.qb: `frappe.qb object with `IN`
		"""
		return frappe.qb.Field(key).isin(value)

	@staticmethod
	def not_like(key: str, value: str) -> frappe.qb:
		"""Wrapper method for `NOT LIKE`

		Args:
				key (str): field
				value (ANy): criterion

		Returns:
				frappe.qb: `frappe.qb object with `NOT LIKE`
		"""
		return frappe.qb.Field(key).not_like(value)

	@staticmethod
	def func_not_in(key: str, value: Union[List, Tuple]):
		"""Wrapper method for `NOT IN`

		Args:
				key (str): field
				value (ANy): criterion

		Returns:
				frappe.qb: `frappe.qb object with `NOT IN`
		"""
		return frappe.qb.Field(key).notin(value)

	@staticmethod
	def func_regex(key: str, value: str) -> frappe.qb:
		"""Wrapper method for `REGEX`

		Args:
				key (str): field
				value (ANy): criterion

		Returns:
				frappe.qb: `frappe.qb object with `REGEX`
		"""
		return frappe.qb.Field(key).regex(value)

	@staticmethod
	def func_between(key: str, value: Union[List, Tuple]) -> frappe.qb:
		"""Wrapper method for `BETWEEN`

		Args:
				key (str): field
				value (ANy): criterion

		Returns:
				frappe.qb: `frappe.qb object with `BETWEEN`
		"""
		return frappe.qb.Field(key)[slice(*value)]

	def make_function(self, key: Any, value: Union[int, str]):
		return self.operator_map[value[0]](key, value[1])

	@staticmethod
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

	@staticmethod
	def get_condition(table: str, **kwargs) -> frappe.qb:
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
		condition = self.get_condition(table, **kwargs)
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
				orderby, order = self.change_orderby(orderby)
			conditions = conditions.orderby(orderby, order=order)

		if kwargs.get("limit"):
			conditions = conditions.limit(kwargs.get("limit"))

		if kwargs.get("distinct"):
			conditions = conditions.distinct()

		if kwargs.get("for_update"):
			conditions = conditions.for_update()

		return conditions

	def dict_query(self, table: str, filters: Dict[str, Union[str, int]] = None, **kwargs):
		"""Build conditions using the given filters

		Args:
			table (str): DocType
			filters (Dict[str, Union[str, int]], optional): Filters. Defaults to None.

		Returns:
			condition: conditions object
		"""
		conditions = self.get_condition(table, **kwargs)
		if not filters:
			return conditions

		for key in filters:
			value = filters.get(key)
			_operator = self.operator_map["="]

			if not isinstance(key, str):
				conditions = conditions.where(self.make_function(key, value))
				continue
			if isinstance(value, (list, tuple)):
				if isinstance(value[1], (list, tuple)) or value[0] in list(self.operator_map.keys())[-4:]:
					_operator = self.operator_map[value[0]]
					conditions = conditions.where(_operator(key, value[1]))
				else:
					_operator = self.operator_map[value[0]]
					conditions = conditions.where(_operator(frappe.qb.Field(key), value[1]))
			else:
				conditions = conditions.where(_operator(frappe.qb.Field(key), value))
		conditions = self.add_conditions(conditions, **kwargs)
		return conditions

	def build_conditions(self, table: str, filters: Union[Dict[str, Union[str, int]], str, int] = None, **kwargs) -> frappe.qb:
		"""Build conditions for sql query

		Args:
				filters (Union[Dict[str, Union[str, int]], str, int]): conditions built from filters provided
				table (str): DocType

		Returns:
				frappe.qb: frappe.qb conditions object
		"""
		if isinstance(filters, Criterion):
			return self.criterion_query(table, filters, **kwargs)

		if isinstance(filters, int) or isinstance(filters, str):
			filters = {"name": str(filters)}

		return self.dict_query(filters=filters, table=table, **kwargs)