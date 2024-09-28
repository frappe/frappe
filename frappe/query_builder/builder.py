import types
import typing
from typing import Any, Optional

from pypika import MySQLQuery, Order, PostgreSQLQuery, terms, OracleQuery
from pypika.dialects import MySQLQueryBuilder, PostgreSQLQueryBuilder, OracleQueryBuilder
from pypika.queries import QueryBuilder, Schema, Table
from pypika.terms import Function

from frappe.query_builder.terms import ParameterizedValueWrapper
from frappe.utils import get_table_name


class Base:
	terms = terms
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


class FrappeOracleQueryBuilder(OracleQueryBuilder):

	def get_sql(self, with_alias: bool = False, subquery: bool = False, **kwargs) -> str:
		if self._from[0].get_table_name() in ('all_tables'):
			return super().get_sql(with_alias=with_alias, subquery=subquery, **kwargs)
		return super().get_sql(with_alias=with_alias, subquery=subquery, **kwargs)

	def _select_sql(self, **kwargs: Any) -> str:
		if self._from[0].get_table_name() not in ('all_tables'):
			for term in self._selects:
				term.name = '"{}"'.format(term.name)
		return super()._select_sql(**kwargs)

	def _orderby_sql(self, **kwargs: Any) -> str:
		if self._from[0].get_table_name() not in ('all_tables'):
			for field, _ in self._orderbys:
				field.name = '"{}"'.format(field.name)
		return super()._orderby_sql(**kwargs)

	def _where_sql(self, quote_char: Optional[str] = None, **kwargs: Any) -> str:
		if self._from[0].get_table_name() not in ('all_tables'):
			self._wheres.left.name = '"{}"'.format(self._wheres.left.name)
		return super()._where_sql(quote_char=quote_char, **kwargs)

	def limit(self, limit: int) -> "QueryBuilder":
		return super().limit(limit)

	def _limit_sql(self) -> str:
		return " FETCH FIRST {} ROWS ONLY".format(self._limit)


	def __str__(self) -> str:
		"test"
		return self.get_sql(dialect=self.dialect)

	def __repr__(self):
		return f"{self}"



class OracleDB(Base, OracleQuery):
	field_translation = types.MappingProxyType(
		{"table_name": "relname", "table_rows": "n_tup_ins"})
	schema_translation = types.MappingProxyType({"tables": "pg_stat_all_tables"})
	# TODO: Find a better way to do this
	# These are interdependent query changes that need fixing. These
	# translations happen in the same query. But there is no check to see if
	# the Fields are changed only when a particular `information_schema` schema
	# is used. Replacing them is not straightforward because the "from_"
	# function can not see the arguments passed to the "select" function as
	# they are two different objects. The quick fix used here is to replace the
	# Field names in the "Field" function.

	_BuilderClasss = FrappeOracleQueryBuilder

	@classmethod
	def _builder(cls, *args, **kwargs) -> "FrappeOracleQueryBuilder":
		return FrappeOracleQueryBuilder(*args, wrapper_cls=ParameterizedValueWrapper, **kwargs)
		# return super()._builder(*args, wrapper_cls=ParameterizedValueWrapper, **kwargs)

	@classmethod
	def Field(cls, field_name, *args, **kwargs):
		if field_name in cls.field_translation:
			field_name = cls.field_translation[field_name]
		return terms.Field(field_name, *args, **kwargs)

	@classmethod
	def from_(cls, table, *args, **kwargs):
		if table.get_table_name() not in ('all_tables'):
			import frappe
			_table = table.get_table_name()
			table = cls.Table(f'"{_table}"', schema= frappe.conf.db_name.upper(), alias=_table)
			print(f"Table: {table}")

		if isinstance(table, str):
			table = cls.DocType(table)

		return super().from_(table, *args, **kwargs)
