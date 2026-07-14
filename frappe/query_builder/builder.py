import re
import types
import typing

from pypika import MySQLQuery, Order, PostgreSQLQuery, SQLLiteQuery, terms
from pypika.dialects import MySQLQueryBuilder, PostgreSQLQueryBuilder, SQLLiteQueryBuilder
from pypika.queries import QueryBuilder, Schema, Table
from pypika.terms import Function
from pypika.utils import format_quotes

from frappe.query_builder.terms import ParameterizedValueWrapper, SQLiteParameterizedValueWrapper
from frappe.utils import get_table_name

# less restrictive version of frappe.core.doctype.doctype.doctype.START_WITH_LETTERS_PATTERN
# to allow table names like __Auth
TABLE_NAME_PATTERN = re.compile(r"^[\w -]*$", flags=re.ASCII)


def _flatten(module):
	import inspect

	from frappe.types import _dict

	new_mod = _dict()
	for name, obj in inspect.getmembers(module, lambda x: not inspect.ismodule(x)):
		if not name.startswith("_"):
			new_mod[name] = obj
	return new_mod


class Base:
	terms = _flatten(terms)
	desc = Order.desc
	asc = Order.asc
	Schema = Schema
	Table = Table

	# Added dynamic type hints for engine attribute
	# which is to be assigned later.
	if typing.TYPE_CHECKING:
		from frappe.database.query import Engine

		engine: Engine

	@staticmethod
	def functions(name: str, *args, **kwargs) -> Function:
		return Function(name, *args, **kwargs)

	@staticmethod
	def DocType(table_name: str, *args, **kwargs) -> Table:
		Base.validate_doctype(table_name)
		table_name = get_table_name(table_name)
		return Table(table_name, *args, **kwargs)

	@classmethod
	def into(cls, table, *args, **kwargs) -> QueryBuilder:
		if isinstance(table, str):
			table = cls.DocType(table)
		return super().into(table, *args, **kwargs)

	@classmethod
	def update(cls, table, *args, **kwargs) -> QueryBuilder:
		if isinstance(table, str):
			table = cls.DocType(table)
		return super().update(table, *args, **kwargs)

	@staticmethod
	def validate_doctype(doctype) -> None:
		from frappe import _, throw

		if not TABLE_NAME_PATTERN.match(doctype):
			throw(_("Invalid DocType: {0}").format(doctype))


class MariaDB(Base, MySQLQuery):
	Field = terms.Field

	_BuilderClasss = MySQLQueryBuilder

	@classmethod
	def _builder(cls, *args, **kwargs) -> "MySQLQueryBuilder":
		return super()._builder(*args, wrapper_cls=ParameterizedValueWrapper, **kwargs)

	@classmethod
	def from_(cls, table, *args, **kwargs):
		if isinstance(table, str):
			table = cls.DocType(table)
		return super().from_(table, *args, **kwargs)


class Postgres(Base, PostgreSQLQuery):
	field_translation = types.MappingProxyType({"table_name": "relname", "table_rows": "n_tup_ins"})
	schema_translation = types.MappingProxyType({"tables": "pg_stat_all_tables"})
	# TODO: Find a better way to do this
	# These are interdependent query changes that need fixing. These
	# translations happen in the same query. But there is no check to see if
	# the Fields are changed only when a particular `information_schema` schema
	# is used. Replacing them is not straightforward because the "from_"
	# function can not see the arguments passed to the "select" function as
	# they are two different objects. The quick fix used here is to replace the
	# Field names in the "Field" function.

	_BuilderClasss = PostgreSQLQueryBuilder

	@classmethod
	def _builder(cls, *args, **kwargs) -> "PostgreSQLQueryBuilder":
		return super()._builder(*args, wrapper_cls=ParameterizedValueWrapper, **kwargs)

	@classmethod
	def Field(cls, field_name, *args, **kwargs):
		if field_name in cls.field_translation:
			field_name = cls.field_translation[field_name]
		return terms.Field(field_name, *args, **kwargs)

	@classmethod
	def from_(cls, table, *args, **kwargs):
		if isinstance(table, Table):
			if table._schema:
				if table._schema._name == "information_schema":
					table = cls.schema_translation.get(table._table_name) or table

		elif isinstance(table, str):
			table = cls.DocType(table)

		return super().from_(table, *args, **kwargs)


# pypika renders `Now() - Interval(days=7)` for SQLite as `CURRENT_TIMESTAMP - datetime('now',
# '+7 days')` -- a nonsensical subtraction of two timestamps. It has to be folded into a single
# `datetime('now', '-7 days')`. This is the one construct pypika can't render correctly on its own:
# the Interval renders independently of the surrounding +/- operator, so it can't know its sign.
# The fold needs the whole expression, so it runs once over the finished SQL string.
_NOW_INTERVAL_PATTERN = re.compile(
	r"(?:CURRENT_TIMESTAMP|datetime\('now'\))\s*([+-])\s*datetime\('now',\s*([^)]*)\)",
	re.IGNORECASE,
)


def _flip_modifier_signs(modifiers: str) -> str:
	"""Flip the leading sign of each quoted datetime modifier, e.g. ``'+7 days'`` -> ``'-7 days'``
	and ``'+1 years', '+2 months'`` -> ``'-1 years', '-2 months'``."""
	flipped = []
	for part in modifiers.split(","):
		part = part.strip()
		if len(part) > 1 and part[1] in "+-":
			part = part[0] + ("-" if part[1] == "+" else "+") + part[2:]
		flipped.append(part)
	return ", ".join(flipped)


def _fold_now_interval(sql: str) -> str:
	if "datetime('now'" not in sql:
		return sql

	def repl(match: re.Match) -> str:
		modifiers = match.group(2)
		if match.group(1) == "-":
			modifiers = _flip_modifier_signs(modifiers)
		return f"datetime('now', {modifiers})"

	return _NOW_INTERVAL_PATTERN.sub(repl, sql)


class FrappeSQLiteQueryBuilder(SQLLiteQueryBuilder):
	"""SQLite builder that emits SQL matching frappe's MariaDB semantics with no post-processing,
	so ``SQLiteDatabase.sql`` can skip its dialect-rewrite pass for query-builder output."""

	def get_sql(self, *args, **kwargs) -> str:
		return _fold_now_interval(super().get_sql(*args, **kwargs))

	def _orderby_sql(
		self, quote_char=None, alias_quote_char=None, orderby_alias: bool = True, **kwargs
	) -> str:
		# Tag plain-column ORDER BY terms with COLLATE NOCASE so text sorts case-insensitively,
		# matching MariaDB's default collation (SQLite's default BINARY collation is case-sensitive
		# and sorts '_' after letters). Function/expression terms and select-aliases are left as-is,
		# mirroring MariaDB, which doesn't apply its collation to an expression's result. Otherwise
		# identical to QueryBuilder._orderby_sql.
		clauses = []
		selected_aliases = {s.alias for s in self._selects}
		for field, directionality in self._orderbys:
			if orderby_alias and field.alias and field.alias in selected_aliases:
				term = format_quotes(field.alias, alias_quote_char or quote_char)
			else:
				term = field.get_sql(quote_char=quote_char, alias_quote_char=alias_quote_char, **kwargs)
				if isinstance(field, terms.Field):
					term += " COLLATE NOCASE"
			clauses.append(f"{term} {directionality.value}" if directionality is not None else term)

		return " ORDER BY {}".format(",".join(clauses))


class SQLite(Base, SQLLiteQuery):
	Field = terms.Field

	_BuilderClasss = FrappeSQLiteQueryBuilder

	@classmethod
	def _builder(cls, *args, **kwargs) -> "FrappeSQLiteQueryBuilder":
		builder = FrappeSQLiteQueryBuilder(*args, wrapper_cls=SQLiteParameterizedValueWrapper, **kwargs)
		# SQLite does not allow parenthesised operands around set operations, i.e.
		# invalid syntax -> `(SELECT ...) UNION (SELECT ...)`
		# valid syntax ->`SELECT ... UNION SELECT ...`.
		builder.wrap_set_operation_queries = False  # Instruct pypika to not wrap set operations
		return builder

	@classmethod
	def from_(cls, table, *args, **kwargs):
		if isinstance(table, str):
			table = cls.DocType(table)
		return super().from_(table, *args, **kwargs)
