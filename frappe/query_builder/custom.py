from typing import Any

from pypika.functions import DistinctOptionFunction, Function
from pypika.terms import Term
from pypika.utils import builder, format_alias_sql, format_quotes

import frappe


class GROUP_CONCAT(DistinctOptionFunction):
	def __init__(self, column: str, alias: str | None = None):
		"""[ Implements the group concat function read more about it at https://www.geeksforgeeks.org/mysql-group_concat-function ]
		Args:
		        column (str): [ name of the column you want to concat]
		        alias (Optional[str], optional): [ is this an alias? ]. Defaults to None.
		"""
		super().__init__("GROUP_CONCAT", column, alias=alias)
		self._separator = ","

	@builder
	def separator(self, separator: str = ""):
		"""Adds a separator to the GROUP_CONCAT function.
		Args:
				separator (str, optional): [separator to be used]. Defaults to ",".
		"""
		self._separator = separator

	def get_sql(self, **kwargs):
		# SEPARATOR goes inside the closing paren, so render without the alias and re-attach it
		# below rather than let Function.get_sql place it before the clause exists.
		query_alias = self.alias
		self.alias = None
		try:
			sql = super().get_sql(**kwargs)
		finally:
			self.alias = query_alias
		if self._separator:
			sql = f"{sql[:-1]} SEPARATOR {frappe.db.escape(self._separator)})"

		# Re-attach through format_alias_sql, the same path every other term uses: it escapes the
		# quote char in the alias, and honours `with_alias` so the alias is emitted in the SELECT
		# clause only. Hand-rolling it quoted the alias raw -- disagreeing with the escaped alias
		# pypika renders for the same term in GROUP BY / ORDER BY -- and appended it in operand
		# position too, where `GROUP_CONCAT(...) `a` LIKE ...` is a syntax error.
		if kwargs.get("with_alias"):
			return format_alias_sql(sql, query_alias, **kwargs)
		return sql


class STRING_AGG(DistinctOptionFunction):
	def __init__(self, column: str, separator: str = ",", alias: str | None = None):
		"""[ Implements the group concat function read more about it at https://docs.microsoft.com/en-us/sql/t-sql/functions/string-agg-transact-sql?view=sql-server-ver15 ]

		Args:
		        column (str): [ name of the column you want to concat ]
		        separator (str, optional): [separator to be used]. Defaults to ",".
		        alias (Optional[str], optional): [description]. Defaults to None.
		"""
		super().__init__("STRING_AGG", column, separator, alias=alias)


class MATCH(DistinctOptionFunction):
	def __init__(self, column: str, *args, **kwargs):
		"""[ Implementation of Match Against read more about it https://dev.mysql.com/doc/refman/8.0/en/fulltext-search.html#function_match ]

		Args:
		        column (str):[ column to search in ]
		"""
		alias = kwargs.get("alias")
		super().__init__(" MATCH", column, *args, alias=alias)
		self._Against = False

	def get_function_sql(self, **kwargs):
		s = super(DistinctOptionFunction, self).get_function_sql(**kwargs)

		if self._Against:
			return f"{s} AGAINST ({frappe.db.escape(f'+{self._Against}*')} IN BOOLEAN MODE)"
		raise Exception("Chain the `Against()` method with match to complete the query")

	@builder
	def Against(self, text: str):
		"""[ Text that has to be searched against ]

		Args:
		        text (str): [ the text string that we match it against ]
		"""
		self._Against = text


class TO_TSVECTOR(DistinctOptionFunction):
	def __init__(self, column: str, *args, **kwargs):
		"""[ Implementation of TO_TSVECTOR read more about it https://www.postgresql.org/docs/9.1/textsearch-controls.html]

		Args:
		        column (str): [ column to search in ]
		"""
		alias = kwargs.get("alias")
		super().__init__("TO_TSVECTOR", column, *args, alias=alias)
		self._PLAINTO_TSQUERY = False

	def get_function_sql(self, **kwargs):
		s = super(DistinctOptionFunction, self).get_function_sql(**kwargs)
		if self._PLAINTO_TSQUERY:
			return f"{s} @@ PLAINTO_TSQUERY({frappe.db.escape(self._PLAINTO_TSQUERY)})"
		return s

	@builder
	def Against(self, text: str):
		"""[ Text that has to be searched against ]

		Args:
		        text (str): [ the text string that we match it against ]
		"""
		self._PLAINTO_TSQUERY = text


class ConstantColumn(Term):
	alias = None

	def __init__(self, value: str) -> None:
		"""Return a pseudo column with the given constant `value` in all the rows."""
		self.value = value

	def get_sql(self, quote_char: str | None = None, **kwargs: Any) -> str:
		return format_alias_sql(
			format_quotes(self.value, kwargs.get("secondary_quote_char") or ""),
			self.alias or self.value,
			quote_char=quote_char,
			**kwargs,
		)


class MonthName(Function):
	def __init__(self, field, alias=None):
		super().__init__("MONTHNAME", field, alias=alias)


class Quarter(Function):
	def __init__(self, field, alias=None):
		super().__init__("QUARTER", field, alias=alias)


class Month(Function):
	def __init__(self, field, alias=None):
		super().__init__("MONTH", field, alias=alias)


class Year(Function):
	def __init__(self, field, alias=None):
		super().__init__("YEAR", field, alias=alias)
