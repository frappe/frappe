from datetime import time
from enum import Enum

from pypika.functions import *
from pypika.terms import Arithmetic, ArithmeticExpression, CustomFunction, Function, Term
from pypika.utils import format_alias_sql

import frappe
from frappe.query_builder.custom import (
	GROUP_CONCAT,
	MATCH,
	STRING_AGG,
	TO_TSVECTOR,
	Month,
	MonthName,
	Quarter,
	Year,
)
from frappe.query_builder.utils import ImportMapper, db_type_is

from .utils import PseudoColumn


class Concat_ws(Function):
	def __init__(self, *terms, **kwargs):
		super().__init__("CONCAT_WS", *terms, **kwargs)


class Locate(Function):
	def __init__(self, needle, haystack, **kwargs):
		super().__init__("LOCATE", needle, haystack, **kwargs)


class Strpos(Function):
	def __init__(self, needle, haystack, **kwargs):
		super().__init__("STRPOS", haystack, needle, **kwargs)


class Instr(Function):
	def __init__(self, needle, haystack, **kwargs):
		super().__init__("INSTR", haystack, needle, **kwargs)


Locate = ImportMapper({db_type_is.MARIADB: Locate, db_type_is.POSTGRES: Strpos, db_type_is.SQLITE: Instr})


# for backward compatibility
Ifnull = IfNull


class Timestamp(Function):
	def __init__(self, term: str, time=None, alias=None):
		if time:
			super().__init__("TIMESTAMP", term, time, alias=alias)
		else:
			super().__init__("TIMESTAMP", term, alias=alias)


class Round(Function):
	def __init__(self, term, decimal=0, **kwargs):
		super().__init__("ROUND", term, decimal, **kwargs)


class Truncate(Function):
	def __init__(self, term, decimal, **kwargs):
		super().__init__("TRUNCATE", term, decimal, **kwargs)


class Abs(Function):
	# pypika ships Abs as an AggregateFunction, which makes get_list/get_value treat a scalar
	# ABS(...) select field as an aggregate query. On postgres that forces the default ORDER BY
	# to be wrapped in MAX(), turning the statement into an implicit aggregate and breaking the
	# (non-grouped) ABS column. ABS is scalar, so define it as a plain Function.
	def __init__(self, term, alias=None):
		super().__init__("ABS", term, alias=alias)


class CurDate(Term):
	"""SQL standard ``CURRENT_DATE`` keyword.

	pypika ships CurDate as a Function, so it renders ``CURRENT_DATE()``. Postgres rejects the
	parentheses — CURRENT_DATE is a reserved keyword there, not a function — while MariaDB accepts
	the bare keyword too. Render it without parentheses so the same query builder works on both.
	"""

	def __init__(self, alias=None):
		super().__init__(alias=alias)

	def get_sql(self, **kwargs):
		with_alias = kwargs.pop("with_alias", False)
		if with_alias:
			return format_alias_sql("CURRENT_DATE", self.alias, **kwargs)
		return "CURRENT_DATE"


GroupConcat = ImportMapper({db_type_is.MARIADB: GROUP_CONCAT, db_type_is.POSTGRES: STRING_AGG})

Match = ImportMapper({db_type_is.MARIADB: MATCH, db_type_is.POSTGRES: TO_TSVECTOR})


class _PostgresTimestamp(ArithmeticExpression):
	def __init__(self, datepart, timepart, alias=None):
		"""Postgres would need both datepart and timepart to be a string for concatenation"""
		if isinstance(timepart, time) or isinstance(datepart, time):
			timepart, datepart = str(timepart), str(datepart)
		if isinstance(datepart, str):
			datepart = Cast(datepart, "date")
		if isinstance(timepart, str):
			timepart = Cast(timepart, "time")

		super().__init__(operator=Arithmetic.add, left=datepart, right=timepart, alias=alias)


CombineDatetime = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("TIMESTAMP", ["date", "time"]),
		db_type_is.POSTGRES: _PostgresTimestamp,
	}
)

DateFormat = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("DATE_FORMAT", ["date", "format"]),
		db_type_is.POSTGRES: ToChar,
	}
)


class YearWeek(Function):
	def __init__(self, term):
		super().__init__("YEARWEEK", term, 1)


class _PostgresUnixTimestamp(Extract):
	# Note: this is just a special case of "Extract" function with "epoch" hardcoded.
	# Check super definition to see how it works.
	def __init__(self, field, alias=None):
		super().__init__("epoch", field=field, alias=alias)
		self.field = field

	def get_sql(self, **kwargs):
		with_alias = kwargs.pop("with_alias", False)
		field = self.field if isinstance(self.field, Term) else Term.wrap_constant(self.field)
		field_sql = field.get_sql(**kwargs)
		sql = (
			"CAST(EXTRACT(EPOCH FROM "
			f"(CAST({field_sql} AS TIMESTAMP) AT TIME ZONE CURRENT_SETTING('TimeZone'))) AS BIGINT)"
		)
		if with_alias:
			return format_alias_sql(sql, self.alias, **kwargs)
		return sql


UnixTimestamp = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("unix_timestamp", ["date"]),
		db_type_is.POSTGRES: _PostgresUnixTimestamp,
	}
)


class _PostgresDateDiff(ArithmeticExpression):
	"""Postgres subtracts two dates to get an integer number of days, which matches
	MariaDB's DATEDIFF(date1, date2). String operands are cast to date so that e.g.
	DateDiff("2024-01-10", field) renders correctly on both backends."""

	def __init__(self, date1, date2, alias=None):
		if isinstance(date1, str):
			date1 = Cast(date1, "date")
		if isinstance(date2, str):
			date2 = Cast(date2, "date")
		super().__init__(operator=Arithmetic.sub, left=date1, right=date2, alias=alias)


DateDiff = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("DATEDIFF", ["date1", "date2"]),
		db_type_is.POSTGRES: _PostgresDateDiff,
	}
)


class _MariaDBJSONExtract(Function):
	def __init__(self, field, path, **kwargs):
		super().__init__("JSON_EXTRACT", field, path, **kwargs)


class _MariaDBJSONValue(Function):
	def __init__(self, field, path, **kwargs):
		super().__init__("JSON_UNQUOTE", _MariaDBJSONExtract(field, path), **kwargs)


class _MariaDBJSONContains(Function):
	def __init__(self, target, candidate, **kwargs):
		from pypika.terms import JSON

		if not isinstance(candidate, Term):
			candidate = JSON(candidate)
		super().__init__("JSON_CONTAINS", target, candidate, **kwargs)


JSONExtract = ImportMapper(
	{
		db_type_is.MARIADB: _MariaDBJSONExtract,
		db_type_is.POSTGRES: lambda field, path, **kw: field.get_json_value(path),
	}
)

JSONValue = ImportMapper(
	{
		db_type_is.MARIADB: _MariaDBJSONValue,
		db_type_is.POSTGRES: lambda field, path, **kw: field.get_text_value(path),
	}
)

JSONContains = ImportMapper(
	{
		db_type_is.MARIADB: _MariaDBJSONContains,
		db_type_is.POSTGRES: lambda target, candidate, **kw: target.contains(candidate),
	}
)


class Cast_(Function):
	def __init__(self, value, as_type, alias=None):
		if frappe.db.db_type == "mariadb" and (
			(hasattr(as_type, "get_sql") and as_type.get_sql().lower() == "varchar")
			or str(as_type).lower() == "varchar"
		):
			# mimics varchar cast in mariadb
			# as mariadb doesn't have varchar data cast
			# https://mariadb.com/kb/en/cast/#description

			# ref: https://stackoverflow.com/a/32542095
			super().__init__("CONCAT", value, "", alias=alias)
		else:
			# from source: https://pypika.readthedocs.io/en/latest/_modules/pypika/functions.html#Cast
			super().__init__("CAST", value, alias=alias)
			self.as_type = as_type

	def get_special_params_sql(self, **kwargs):
		if self.name.lower() == "cast":
			type_sql = (
				self.as_type.get_sql(**kwargs)
				if hasattr(self.as_type, "get_sql")
				else str(self.as_type).upper()
			)
			return f"AS {type_sql}"


def _aggregate(function, dt, fieldname, filters, **kwargs):
	return (
		frappe.qb.get_query(dt, filters=filters, fields=[function(PseudoColumn(fieldname))]).run(**kwargs)[0][
			0
		]
		or 0
	)


class SqlFunctions(Enum):
	DayOfYear = "dayofyear"
	Extract = "extract"
	Locate = "locate"
	Count = "count"
	Sum = "sum"
	Avg = "avg"
	Max = "max"
	Min = "min"
	Abs = "abs"
	Timestamp = "timestamp"
	IfNull = "ifnull"


def _max(dt, fieldname, filters=None, **kwargs):
	return _aggregate(Max, dt, fieldname, filters, **kwargs)


def _min(dt, fieldname, filters=None, **kwargs):
	return _aggregate(Min, dt, fieldname, filters, **kwargs)


def _avg(dt, fieldname, filters=None, **kwargs):
	return _aggregate(Avg, dt, fieldname, filters, **kwargs)


def _sum(dt, fieldname, filters=None, **kwargs):
	return _aggregate(Sum, dt, fieldname, filters, **kwargs)
