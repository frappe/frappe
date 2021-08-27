import operator
from typing import Any, Dict, List, Tuple, Union

from frappe.query_builder import Order

import frappe


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

	def dict_query(self, table: str, filters: Dict[str, Union[str, int]] = None,
				   orderby:str = None, order:Order = None):
		"""Generate condition object using filters

		Args:
			table (str): DocType
			filters (Dict[str, Union[str, int]], optional): Conditions. Defaults to None.
			orderby (str, optional): field to order by. Defaults to None.
			order (Order, optional): order. Defaults to None.

		Returns:
			condition: conditions object
		"""
		conditions = frappe.qb.from_(table)
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
		if orderby:
			order = order if order else Order.desc
			return conditions.orderby(orderby, order)
		return conditions

	def build_conditions(self, table: str, filters: Union[Dict[str, Union[str, int]], str, int] = None,
						 orderby: str = None, order: Order = None) -> frappe.qb:
		"""Build conditions for sql query

		Args:
				filters (Union[Dict[str, Union[str, int]], str, int]): conditions built from filters provided
				table (str): DocType

		Returns:
				frappe.qb: frappe.qb conditions object
		"""
		if isinstance(filters, int) or isinstance(filters, str):
			filters = {"name": str(filters)}

		return self.dict_query(filters=filters, table=table, orderby=orderby, order=order)