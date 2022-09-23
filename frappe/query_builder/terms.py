from datetime import time, timedelta
from typing import Any

from pypika.queries import QueryBuilder
from pypika.terms import Criterion, Function, ValueWrapper
from pypika.utils import format_alias_sql

from frappe.utils.data import format_time, format_timedelta


class NamedParameterWrapper:
	"""Utility class to hold parameter values and keys"""

	def __init__(self) -> None:
		self.parameters = {}

	def get_sql(self, param_value: Any, **kwargs) -> str:
		"""returns SQL for a parameter, while adding the real value in a dict

		Args:
		                param_value (Any): Value of the parameter

		Returns:
		                str: parameter used in the SQL query
		"""
		param_key = f"%(param{len(self.parameters) + 1})s"
		self.parameters[param_key[2:-2]] = param_value
		return param_key

	def get_parameters(self) -> dict[str, Any]:
		"""get dict with parameters and values

		Returns:
		                Dict[str, Any]: parameter dict
		"""
		return self.parameters


class ParameterizedValueWrapper(ValueWrapper):
	"""
	Class to monkey patch ValueWrapper

	Adds functionality to parameterize queries when a `param wrapper` is passed in get_sql()
	"""

	def get_sql(
		self,
		quote_char: str | None = None,
		secondary_quote_char: str = "'",
		param_wrapper: NamedParameterWrapper | None = None,
		**kwargs: Any,
	) -> str:
		if param_wrapper and isinstance(self.value, str):
			# add quotes if it's a string value
			value_sql = self.get_value_sql(quote_char=quote_char, **kwargs)
			sql = param_wrapper.get_sql(param_value=value_sql, **kwargs)
		else:
			# * BUG: pypika doesen't parse timedeltas and datetime.time
			if isinstance(self.value, timedelta):
				self.value = format_timedelta(self.value)
			elif isinstance(self.value, time):
				self.value = format_time(self.value)

			sql = self.get_value_sql(
				quote_char=quote_char,
				secondary_quote_char=secondary_quote_char,
				param_wrapper=param_wrapper,
				**kwargs,
			)
		return format_alias_sql(sql, self.alias, quote_char=quote_char, **kwargs)


class ParameterizedFunction(Function):
	"""
	Class to monkey patch pypika.terms.Functions

	Only to pass `param_wrapper` in `get_function_sql`.
	"""

	def get_sql(self, **kwargs: Any) -> str:
		with_alias = kwargs.pop("with_alias", False)
		with_namespace = kwargs.pop("with_namespace", False)
		quote_char = kwargs.pop("quote_char", None)
		dialect = kwargs.pop("dialect", None)
		param_wrapper = kwargs.pop("param_wrapper", None)

		function_sql = self.get_function_sql(
			with_namespace=with_namespace,
			quote_char=quote_char,
			param_wrapper=param_wrapper,
			dialect=dialect,
		)

		if self.schema is not None:
			function_sql = "{schema}.{function}".format(
				schema=self.schema.get_sql(quote_char=quote_char, dialect=dialect, **kwargs),
				function=function_sql,
			)

		if with_alias:
			return format_alias_sql(function_sql, self.alias, quote_char=quote_char, **kwargs)

		return function_sql


class SubQuery(Criterion):
	def __init__(
		self,
		subq: QueryBuilder,
		alias: str | None = None,
	) -> None:
		super().__init__(alias)
		self.subq = subq

	def get_sql(self, **kwg: Any) -> str:
		kwg["subquery"] = True
		return self.subq.get_sql(**kwg)


subqry = SubQuery
