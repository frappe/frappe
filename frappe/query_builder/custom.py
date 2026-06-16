from typing import Any

from pypika.functions import DistinctOptionFunction, Function
from pypika.terms import Criterion, Term
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
		query_alias = self.alias
		self.alias = None
		sql = super().get_sql(**kwargs)
		if self._separator:
			sql = f"{sql[:-1]} SEPARATOR {frappe.db.escape(self._separator)})"

		self.alias = query_alias
		if self.alias:
			quote = kwargs.get("quote_char", "`")
			sql += f" {quote}{self.alias}{quote}"
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


class Xor(Criterion):
	"""Logical XOR of two expressions, portable across database backends.

	MariaDB has a native ``XOR`` operator, but SQLite and Postgres do not, so this
	renders the equivalent boolean expression there. Prefer this over pypika's ``^``
	operator (``a ^ b``), which always renders ``XOR`` and so is a syntax error on
	SQLite/Postgres.

	The fallback ``(((a) AND NOT (b)) OR ((b) AND NOT (a)))`` is fully bracketed,
	including an outer pair so the top-level ``OR`` keeps its meaning when this is
	combined with other conditions (``AND`` binds tighter than ``OR``).

	The operands are expected to be boolean expressions. Postgres requires boolean
	operands for ``AND``/``OR``/``NOT`` and will reject bare numeric columns/values;
	MariaDB and SQLite coerce them via numeric truthiness, but for portability pass
	explicit comparisons (e.g. ``col != 0``) rather than raw numerics.
	"""

	def __init__(self, left: Term, right: Term, alias: str | None = None) -> None:
		super().__init__(alias)
		self.left = left
		self.right = right

	def get_sql(self, quote_char: str | None = None, with_alias: bool = False, **kwargs: Any) -> str:
		left = self.left.get_sql(quote_char=quote_char, **kwargs)
		right = self.right.get_sql(quote_char=quote_char, **kwargs)
		if frappe.db.db_type == "mariadb":
			sql = f"(({left}) XOR ({right}))"
		else:
			sql = f"((({left}) AND NOT ({right})) OR (({right}) AND NOT ({left})))"
		if with_alias and self.alias:
			return format_alias_sql(sql, self.alias, quote_char=quote_char, **kwargs)
		return sql


class MonthName(Function):
	def __init__(self, field, alias=None):
		super().__init__("MONTHNAME", field, alias=alias)


class Quarter(Function):
	def __init__(self, field, alias=None):
		super().__init__("QUARTER", field, alias=alias)


class Month(Function):
	def __init__(self, field, alias=None):
		super().__init__("MONTH", field, alias=alias)
