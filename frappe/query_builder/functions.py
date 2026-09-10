import json
from datetime import time
from enum import Enum

from pypika.enums import Arithmetic
from pypika.functions import *
from pypika.functions import Coalesce as PypikaCoalesce
from pypika.terms import ArithmeticExpression, CustomFunction, Function, Term
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
	SQLiteFullTextMatch,
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


class Coalesce(PypikaCoalesce):
	"""Return the sole argument directly because SQLite rejects COALESCE with one argument."""

	def get_function_sql(self, **kwargs):
		if getattr(frappe.conf, "db_type", None) == "sqlite" and len(self.args) == 1:
			return self.args[0].get_sql(with_alias=False, subquery=True, **kwargs)
		return super().get_function_sql(**kwargs)


class _StandardTimestamp(Function):
	def __init__(self, term: str, time=None, alias=None):
		if time is not None:
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

Match = ImportMapper(
	{
		db_type_is.MARIADB: MATCH,
		db_type_is.POSTGRES: TO_TSVECTOR,
		db_type_is.SQLITE: SQLiteFullTextMatch,
	}
)


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


class _SQLiteTimestamp(Function):
	"""Render timestamp conversion and date-plus-duration operations for SQLite."""

	def __init__(self, datepart, timepart=None, alias=None):
		if timepart is None:
			super().__init__("DATETIME", datepart, alias=alias)
		else:
			super().__init__("FRAPPE_COMBINE_DATETIME", datepart, timepart, alias=alias)


Timestamp = ImportMapper(
	{
		db_type_is.MARIADB: _StandardTimestamp,
		db_type_is.POSTGRES: _StandardTimestamp,
		db_type_is.SQLITE: _SQLiteTimestamp,
	}
)


CombineDatetime = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("TIMESTAMP", ["date", "time"]),
		db_type_is.POSTGRES: _PostgresTimestamp,
		db_type_is.SQLITE: _SQLiteTimestamp,
	}
)


SQLITE_STRFTIME_TOKENS = {
	"%%": "%%",
	"%d": "%d",
	"%H": "%H",
	"%i": "%M",
	"%j": "%j",
	"%m": "%m",
	"%S": "%S",
	"%s": "%S",
	"%T": "%H:%M:%S",
	"%u": "%W",
	"%w": "%w",
	"%Y": "%Y",
}


def _translate_date_format_for_sqlite(format_string: str) -> str | None:
	"""Translate only the MariaDB date tokens SQLite's native STRFTIME reproduces exactly."""
	translated_parts = []
	index = 0
	while index < len(format_string):
		if format_string[index] != "%":
			translated_parts.append(format_string[index])
			index += 1
			continue

		token = format_string[index : index + 2]
		if len(token) != 2 or token not in SQLITE_STRFTIME_TOKENS:
			return None
		translated_parts.append(SQLITE_STRFTIME_TOKENS[token])
		index += 2

	return "".join(translated_parts)


class _SQLiteDateFormat(Function):
	def __init__(self, date_value, format_string, alias=None):
		translated_format = (
			_translate_date_format_for_sqlite(format_string) if isinstance(format_string, str) else None
		)
		if translated_format is not None:
			super().__init__("STRFTIME", translated_format, date_value, alias=alias)
		else:
			super().__init__("FRAPPE_DATE_FORMAT", date_value, format_string, alias=alias)


DateFormat = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("DATE_FORMAT", ["date", "format"]),
		db_type_is.POSTGRES: ToChar,
		db_type_is.SQLITE: _SQLiteDateFormat,
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
			"CAST(TRUNC(EXTRACT(EPOCH FROM "
			f"(CAST({field_sql} AS TIMESTAMP) AT TIME ZONE CURRENT_SETTING('TimeZone')))) AS BIGINT)"
		)
		if with_alias:
			return format_alias_sql(sql, self.alias, **kwargs)
		return sql


class _SQLiteUnixTimestamp(Function):
	def __init__(self, field, alias=None):
		super().__init__("FRAPPE_UNIX_TIMESTAMP", field, alias=alias)


UnixTimestamp = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("unix_timestamp", ["date"]),
		db_type_is.POSTGRES: _PostgresUnixTimestamp,
		db_type_is.SQLITE: _SQLiteUnixTimestamp,
	}
)


class _PostgresDateDiff(ArithmeticExpression):
	"""Postgres subtracts two dates to get an integer number of days, which matches
	MariaDB's DATEDIFF(date1, date2). Both operands are cast to date: subtracting
	timestamps would yield an interval that carries the time of day, so a Datetime
	field would return a timedelta where MariaDB returns whole days."""

	def __init__(self, date1, date2, alias=None):
		super().__init__(
			operator=Arithmetic.sub,
			left=Cast(date1, "date"),
			right=Cast(date2, "date"),
			alias=alias,
		)


class _SQLiteDateDiff(Function):
	"""Return the difference between calendar dates, ignoring their times of day."""

	def __init__(self, date1, date2, alias=None):
		super().__init__("DATEDIFF", date1, date2, alias=alias)

	def get_function_sql(self, **kwargs):
		date1_sql, date2_sql = (
			argument.get_sql(with_alias=False, subquery=True, **kwargs) for argument in self.args
		)
		return f"CAST(JULIANDAY(DATE({date1_sql})) - JULIANDAY(DATE({date2_sql})) AS INTEGER)"


DateDiff = ImportMapper(
	{
		db_type_is.MARIADB: CustomFunction("DATEDIFF", ["date1", "date2"]),
		db_type_is.POSTGRES: _PostgresDateDiff,
		db_type_is.SQLITE: _SQLiteDateDiff,
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


class _SQLiteJSONExtract(Function):
	"""Return JSON text like MariaDB JSON_EXTRACT, including quotes around strings."""

	def __init__(self, field, path, **kwargs):
		super().__init__("JSON_EXTRACT", field, path, **kwargs)

	def get_function_sql(self, **kwargs):
		field_sql, path_sql = (
			argument.get_sql(with_alias=False, subquery=True, **kwargs) for argument in self.args
		)
		extracted_value = f"JSON_EXTRACT({field_sql},{path_sql})"
		json_type = f"JSON_TYPE({field_sql},{path_sql})"
		return (
			f"CASE WHEN {json_type} IS NULL THEN NULL "
			f"WHEN {json_type} IN ('true','false','null') THEN {json_type} "
			f"ELSE JSON_QUOTE({extracted_value}) END"
		)


class _SQLiteJSONValue(Function):
	"""Return an unquoted JSON scalar like MariaDB JSON_VALUE."""

	def __init__(self, field, path, **kwargs):
		super().__init__("JSON_EXTRACT", field, path, **kwargs)

	def get_function_sql(self, **kwargs):
		field_sql, path_sql = (
			argument.get_sql(with_alias=False, subquery=True, **kwargs) for argument in self.args
		)
		extracted_value = f"JSON_EXTRACT({field_sql},{path_sql})"
		json_type = f"JSON_TYPE({field_sql},{path_sql})"
		return (
			f"CASE {json_type} WHEN 'object' THEN NULL WHEN 'array' THEN NULL "
			f"WHEN 'true' THEN 'true' WHEN 'false' THEN 'false' "
			f"ELSE CAST({extracted_value} AS TEXT) END"
		)


class _SQLiteJSONContains(Function):
	def __init__(self, target, candidate, **kwargs):
		if candidate is not None and not isinstance(candidate, Term):
			candidate = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
		super().__init__("FRAPPE_JSON_CONTAINS", target, candidate, **kwargs)


JSONExtract = ImportMapper(
	{
		db_type_is.MARIADB: _MariaDBJSONExtract,
		db_type_is.POSTGRES: lambda field, path, **kw: field.get_json_value(path),
		db_type_is.SQLITE: _SQLiteJSONExtract,
	}
)

JSONValue = ImportMapper(
	{
		db_type_is.MARIADB: _MariaDBJSONValue,
		db_type_is.POSTGRES: lambda field, path, **kw: field.get_text_value(path),
		db_type_is.SQLITE: _SQLiteJSONValue,
	}
)

JSONContains = ImportMapper(
	{
		db_type_is.MARIADB: _MariaDBJSONContains,
		db_type_is.POSTGRES: lambda target, candidate, **kw: target.contains(candidate),
		db_type_is.SQLITE: _SQLiteJSONContains,
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
