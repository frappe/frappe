from pypika.functions import *
from pypika.terms import Arithmetic, ArithmeticExpression, CustomFunction, Function

from frappe.database.query import Query
from frappe.query_builder.custom import GROUP_CONCAT, MATCH, STRING_AGG, TO_TSVECTOR
from frappe.query_builder.utils import ImportMapper, db_type_is

from .utils import Column


class Concat_ws(Function):
	def __init__(self, *terms, **kwargs):
		super(Concat_ws, self).__init__("CONCAT_WS", *terms, **kwargs)


GroupConcat = ImportMapper({db_type_is.MARIADB: GROUP_CONCAT, db_type_is.POSTGRES: STRING_AGG})

Match = ImportMapper({db_type_is.MARIADB: MATCH, db_type_is.POSTGRES: TO_TSVECTOR})


class _PostgresTimestamp(ArithmeticExpression):
	def __init__(self, datepart, timepart, alias=None):
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


class Cast_(Function):
	def __init__(self, value, as_type, alias=None):
		if db_type_is.MARIADB and (
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
			return "AS {type}".format(type=type_sql)


def _aggregate(function, dt, fieldname, filters, **kwargs):
	return (
		Query().build_conditions(dt, filters).select(function(Column(fieldname))).run(**kwargs)[0][0]
		or 0
	)


def _max(dt, fieldname, filters=None, **kwargs):
	return _aggregate(Max, dt, fieldname, filters, **kwargs)


def _min(dt, fieldname, filters=None, **kwargs):
	return _aggregate(Min, dt, fieldname, filters, **kwargs)


def _avg(dt, fieldname, filters=None, **kwargs):
	return _aggregate(Avg, dt, fieldname, filters, **kwargs)


def _sum(dt, fieldname, filters=None, **kwargs):
	return _aggregate(Sum, dt, fieldname, filters, **kwargs)
