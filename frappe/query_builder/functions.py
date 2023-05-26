from datetime import time
from enum import Enum

from pypika.functions import *
from pypika.terms import Arithmetic, ArithmeticExpression, CustomFunction, Function

import frappe
from frappe.query_builder.custom import GROUP_CONCAT, MATCH, STRING_AGG, TO_TSVECTOR
from frappe.query_builder.utils import ImportMapper, db_type_is

from .utils import PseudoColumn


class Concat_ws(Function):
	def __init__(self, *terms, **kwargs):
		super().__init__("CONCAT_WS", *terms, **kwargs)


class Locate(Function):
	def __init__(self, *terms, **kwargs):
		terms = list(terms)
		if not isinstance(terms[0], str):
			terms[0] = terms[0].get_sql()
		super().__init__("LOCATE", *terms, **kwargs)


class Ifnull(IfNull):
	def __init__(self, condition, term, **kwargs):
		if not isinstance(condition, str):
			condition = condition.get_sql()
		if not isinstance(term, str):
			term = term.get_sql()
		super().__init__(condition, term, **kwargs)


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


class _PostgresUnixTimestamp(Extract):
	# Note: this is just a special case of "Extract" function with "epoch" hardcoded.
	# Check super definition to see how it works.
	def __init__(self, field, alias=None):
		super().__init__("epoch", field=field, alias=alias)
		self.field = field


UnixTimestamp = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("unix_timestamp", ["date"]),
		db_type_is.POSTGRES: _PostgresUnixTimestamp,
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
		frappe.qb.get_query(dt, filters=filters, fields=[function(PseudoColumn(fieldname))]).run(
			**kwargs
		)[0][0]
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
