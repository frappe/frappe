from datetime import datetime, time, timedelta
from typing import Any

from pypika.dialects import SQLLiteValueWrapper
from pypika.queries import QueryBuilder
from pypika.terms import BasicCriterion, ComplexCriterion, Criterion, Field, Function, ValueWrapper
from pypika.utils import format_alias_sql

import frappe
from frappe.utils.data import format_time, format_timedelta


class NamedParameterWrapper:
	"""Utility class to hold parameter values and keys"""

	__slots__ = ("parameters",)

	def __init__(self) -> None:
		self.parameters = {}

	def get_sql(self, param_value: Any, **kwargs) -> str:
		"""Return SQL for a parameter, while adding the real value in a dict.

		Args:
		        param_value (Any): Value of the parameter

		Return:
		        str: parameter used in the SQL query
		"""
		param_key = f"%(param{len(self.parameters) + 1})s"
		assert param_key[2:-2] not in self.parameters, "generated parameter keys must be unique"
		self.parameters[param_key[2:-2]] = param_value
		return param_key

	def get_parameters(self) -> dict[str, Any]:
		"""Get dict with parameters and values."""
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
			elif isinstance(self.value, datetime):
				self.value = frappe.db.format_datetime(self.value)

			sql = self.get_value_sql(
				quote_char=quote_char,
				secondary_quote_char=secondary_quote_char,
				param_wrapper=param_wrapper,
				**kwargs,
			)
		return format_alias_sql(sql, self.alias, quote_char=quote_char, **kwargs)


class SQLiteParameterizedValueWrapper(ParameterizedValueWrapper, SQLLiteValueWrapper):
	pass


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

# ================================================================================
# Monkey-patching PyPika Classes used to generate sql through custom `get_sql` method.
# Main intention is to use `f-strings` to speed up formatting, which add too much latency otherwise due to `.format` coupled with keyword arguements.
# NOTE: A better/cleaner way would be to maintain Py-Pika fork, as everything is PATCHED at this point :(
# There is possibility for use of original symbol for PyPika depending upon where such symbol is loaded.
# For frappe `qb` though, we seems to using expected PATCHED classes, hence benefitting almost all SQL queries generation !


# patching `pypika/utils/format_quotes` function.
def format_quotes_patched(value: Any, quote_char: str | None) -> str:
	if not (quote_char):
		quote_char = ""
	return f"{quote_char}{value}{quote_char}"


# patching `terms/Field class get_sql`
class FieldPatched(Field):
	def get_sql(self, **kwargs: Any) -> str:
		# print("hello from patched.. Field")
		with_alias = kwargs.pop("with_alias", False)
		with_namespace = kwargs.pop("with_namespace", False)
		quote_char = kwargs.pop("quote_char", None)

		# Need to add namespace if the table has an alias
		if self.table and (with_namespace or self.table.alias):
			table_name = self.table.get_table_name()
			field_sql = f"{quote_char}{table_name}{quote_char}.{quote_char}{self.name}{quote_char}"
		else:
			field_sql = format_quotes_patched(self.name, quote_char)
		if with_alias:
			field_alias = getattr(self, "alias", None)
			return format_alias_sql(field_sql, field_alias, quote_char=quote_char, **kwargs)
		return field_sql


# patching `terms/BasicCriterion class get_sql`
class BasicCriterionPatched(BasicCriterion):
	def get_sql(self, quote_char: str = '"', with_alias: bool = False, **kwargs: Any) -> str:
		# print("Fdafas")
		# print("hello from patched.. basic")
		sql = f"{self.left.get_sql(quote_char=quote_char, **kwargs)}{self.comparator.value}{self.right.get_sql(quote_char=quote_char, **kwargs)}"
		if with_alias:
			return format_alias_sql(sql, self.alias, **kwargs)
		return sql


class ComplexCriterionPatched(ComplexCriterion):
	def get_sql(self, subcriterion: bool = False, **kwargs: Any) -> str:
		# print("hello from patched.. complex")
		sql = f"{self.left.get_sql(subcriterion=self.needs_brackets(self.left), **kwargs)} {self.comparator.value} {self.right.get_sql(subcriterion=self.needs_brackets(self.right), **kwargs)}"
		if subcriterion:
			return f"({sql})"
		return sql


# =====================================================================================
