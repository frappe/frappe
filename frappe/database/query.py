from typing import Tuple, Union, List, Any
import frappe
import operator


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

		self.sql_functions = ["sum", "now", "interval"]

	@staticmethod
	def like(key: str, value: Any):
		"""Wrapper method for `LIKE`

		Args:
			key (str): field
			value (ANy): criterion

		Returns:
			[frappe.qb]: frappe.qb object with `LIKE`
		"""
		return frappe.qb.Field(key).like(value)

	@staticmethod
	def func_in(key, value):
		return frappe.qb.Field(key).isin(value)

	@staticmethod
	def not_like(key, value):
		return frappe.qb.Field(key).not_like(value)

	@staticmethod
	def func_not_in(key, value):
		return frappe.qb.Field(key).notin(value)

	@staticmethod
	def func_regex(key, value):
		return frappe.qb.Field(key).regex(value)

	@staticmethod
	def func_between(key, value):
		return frappe.qb.Field(key)[slice(*value)]

	@staticmethod
	def get_func_obj(func: str):
		return frappe.qb.functions(func)

	def build_conditions(self, filters, table):
		"""
		filters = {columns: condition}
		frappe.qb.from_(table).where(conditions)
		"""

		conditions = frappe.qb.from_(table)

		def _query(key):
			nonlocal conditions
			value = filters.get(key)
			_operator = self.operator_map["="]
			if isinstance(value, (list, tuple)):
				if isinstance(value[1], (list, tuple)) or value[0] in list(self.operator_map.keys())[-4:]:
					_operator = self.operator_map[value[0]]
					conditions = conditions.where(_operator(key, value[1]))
				else:
					_operator = self.operator_map[value[0]]
					conditions = conditions.where(_operator(frappe.qb.Field(key), value[1]))
			else:
				conditions = conditions.where(_operator(frappe.qb.Field(key), value))

		if isinstance(filters, int) or isinstance(filters, str):
			filters = {"name": str(filters)}

		if filters:
			for f in filters:
				_query(f)

		return conditions
