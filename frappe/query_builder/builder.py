import re
import types
import typing
from typing import Any, Optional, Type, Union

from pypika import MySQLQuery, OracleQuery, Order, PostgreSQLQuery, terms
from pypika.dialects import MySQLQueryBuilder, OracleQueryBuilder, PostgreSQLQueryBuilder
from pypika.queries import Query, QueryBuilder, Schema, Table, Field
from pypika.terms import BasicCriterion, ComplexCriterion, ContainsCriterion, Function
from pypika.utils import format_alias_sql, format_quotes

import frappe
from frappe.query_builder.terms import ParameterizedValueWrapper
from frappe.utils import get_table_name


class FrappeField(Field):
	def get_sql(self, **kwargs: Any) -> str:
		if frappe.is_oracledb:
			with_alias = kwargs.pop("with_alias", False)
			with_namespace = kwargs.pop("with_namespace", False)
			quote_char = kwargs.pop("quote_char", None)

			field_sql = self.name

			# Need to add namespace if the table has an alias
			if self.table and (with_namespace or self.table.alias):
				table_name = self.table.get_table_name()
				if field_sql[0] == '"' and field_sql[-1] == '"':
					field_sql = f"{table_name}.{field_sql}"
				else:
					field_sql = f"{table_name}.\"{field_sql}\""

			else:
				field_sql = format_quotes(field_sql, quote_char)

			field_alias = getattr(self, "alias", None)
			if with_alias:
				return format_alias_sql(field_sql, field_alias, quote_char='"', **kwargs)
			return field_sql
		return super().get_sql(**kwargs)



class FrappeTable(Table):

	def __init__(
		self,
		name: str,
		schema: Schema | str | None = None,
		alias: str | None = None,
		query_cls: Query | None = None,
	) -> None:
		super().__init__(
			name=name,
			schema=schema,
			alias=alias if alias else name.replace(' ', '_').removeprefix('__').removesuffix('__'),
			query_cls=query_cls
		)

	def __repr__(self) -> str:
		if self._schema:
			return f"FrappeTable('{self._table_name}', schema='{self._schema}')"
		return f"FrappeTable('{self._table_name}')"

	def get_sql(self, **kwargs: Any) -> str:
		# quote_char = kwargs.get("quote_char")
		# # FIXME escape
		# table_sql = format_quotes(self._table_name, quote_char)
		table_sql = self._table_name

		if self._schema is not None:
			table_sql = f'{self._schema.get_sql(**kwargs).upper()}."{table_sql}"'

		if self._for:
			table_sql = f"{table_sql} FOR {self._for.get_sql(**kwargs)}"
		elif self._for_portion:
			table_sql = f"{table_sql} FOR PORTION OF {self._for_portion.get_sql(**kwargs)}"

		return format_alias_sql(table_sql, self.alias, **kwargs)


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
		if ' ' in table_name and 'alias' not in kwargs:
			if frappe.is_oracledb:
				return FrappeTable(table_name,
								   alias=table_name.replace(' ', '_'), *args, **kwargs)
			return Table(table_name, alias=table_name.replace(' ', '_'), *args, **kwargs)
		if frappe.is_oracledb:
			return FrappeTable(table_name, *args, **kwargs)
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
		print(f"MariaDB; [{table}]")
		return super().from_(table, *args, **kwargs)


class Postgres(Base, PostgreSQLQuery):
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
	IGNORE_TABLES_LIST = ('all_tables', 'user_tab_columns', 'user_tables')

	def _from_sql(self, with_namespace: bool = False, **kwargs: Any) -> str:
		print(f"self._form: {self._from}")
		_table = []

		for clause in self._from:
			table_name = clause.get_sql(
				subquery=True,
				with_alias=True,
				**kwargs
			)
			_table.append(table_name)

		return " FROM {selectable}".format(
			selectable=",".join(_table)
		)

	def is_db_metadata_table(self):
		if self._from is not None and self._from:
			return self._from[0].get_table_name() in FrappeOracleQueryBuilder.IGNORE_TABLES_LIST
		elif self._update_table is not None and self._update_table:
			return self._update_table.get_table_name() in FrappeOracleQueryBuilder.IGNORE_TABLES_LIST

	# def get_sql(self, with_alias: bool = False, subquery: bool = False, **kwargs) -> str:
	# 	return super().get_sql(with_alias=with_alias, subquery=subquery, **kwargs)

	# def _select_sql(self, **kwargs: Any) -> str:
	# 	# if not self.is_db_metadata_table():
	# 	# 	for term in self._selects:
	# 	# 		term.name = f'"{term.name}"'
	# 	return super()._select_sql(**kwargs)

	def _orderby_sql(self, **kwargs: Any) -> str:
		if not self.is_db_metadata_table():
			for field, _ in self._orderbys:
				field.name = FrappeOracleQueryBuilder.check_double_quotes(field.name)
		return super()._orderby_sql(**kwargs)

	# def _where_sql(self, quote_char: Optional[str] = None, **kwargs: Any) -> str:
	# 	if not self.is_db_metadata_table():
	# 		self.handle_where_clause(self._wheres)
	# 	return super()._where_sql(quote_char=quote_char, **kwargs)
	#
	# @staticmethod
	# def handle_where_clause(where_statement):
	# 	if isinstance(where_statement, ComplexCriterion):
	# 		FrappeOracleQueryBuilder.handle_where_clause(where_statement.left)
	# 		FrappeOracleQueryBuilder.handle_where_clause(where_statement.right)
	# 	elif isinstance(where_statement, ContainsCriterion):
	# 		where_statement.term.name = FrappeOracleQueryBuilder.check_double_quotes(where_statement.term.name)
	# 	else:
	# 		where_statement.left.name = FrappeOracleQueryBuilder.check_double_quotes(where_statement.left.name)
	#
	@staticmethod
	def check_double_quotes(name):
		if not (name[0] == '"' and name[-1] == '"'):
			return f'"{name}"'
		return name

	def _set_sql(self, **kwargs: Any) -> str:
		if not self.is_db_metadata_table():
			for field, value in self._updates:
				if not (field.name[0] == '"' and field.name[-1] == '"'):
					field.name = f'"{field.name}"'
				if isinstance(value.value, str) and re.search('^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+$', value.value):  # noqa: W605
					value.value = f"to_timestamp('{value.value}', 'yyyy-mm-dd hh24:mi:ss.ff6')"
		expr = []
		for field, value in self._updates:
			left = field.name
			right = value.get_sql(**kwargs)
			expr.append(f"{left} = {right}")

		return f" SET {', '.join(expr)}"

	def _limit_sql(self) -> str:
		return f" FETCH FIRST {self._limit} ROWS ONLY"

	def _columns_sql(self, with_namespace: bool = False, **kwargs: Any) -> str:
		"""
		SQL for Columns clause for INSERT queries
		:param with_namespace:
			Remove from kwargs, never format the column terms with namespaces since only one table can be inserted into
		"""
		return " ({columns})".format(
			columns=",".join(f'"{term.name}"' for term in self._columns)
		)
		# term.get_sql(with_namespace=False, **kwargs)
		# )

	def _values_sql(self, **kwargs: Any) -> str:

		values = "),(".join(
			",".join(conversion_column_value(term.get_sql(with_alias=True, subquery=True, **kwargs)) for term in row)
			for row in self._values
		)
		return f" VALUES ({values})"

	def _insert_sql(self, **kwargs: Any) -> str:
		table = self._insert_table.get_sql(**kwargs)

		return "INSERT {ignore}INTO {table}".format(
			table=table,
			ignore="IGNORE " if self._ignore else "",
		)

	def __repr__(self):
		return f"{self}"




class OracleDB(Base, OracleQuery):
	Field = FrappeField
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

	@staticmethod
	def DocType(table_name: str, *args, **kwargs) -> Table:
		table_name = get_table_name(table_name)
		if table_name not in FrappeOracleQueryBuilder.IGNORE_TABLES_LIST:
			kwargs["schema"] = frappe.conf.db_name

		if ' ' in table_name and 'alias' not in kwargs:
			return FrappeTable(table_name, alias=table_name.replace(' ', '_'), *args, **kwargs)
		return FrappeTable(table_name, *args, **kwargs)

	@classmethod
	def Field(cls, field_name, *args, **kwargs):
		# if field_name in cls.field_translation:
		# 	field_name = cls.field_translation[field_name]
		# return terms.Field(field_name, *args, **kwargs)
		return FrappeField(field_name, *args, **kwargs)

	@classmethod
	def get_table(cls, table):
		if not isinstance(table, str) and table.get_table_name() not in FrappeOracleQueryBuilder.IGNORE_TABLES_LIST:
			# table._schema = FrappeTable._init_schema(frappe.conf.db_name.upper())

			table = FrappeTable(
				name=table._table_name,
				schema=frappe.conf.db_name.upper()
			)

		if isinstance(table, str):
			table = cls.DocType(table)

		return table

	@classmethod
	def from_(cls, table, *args, **kwargs):
		table = OracleDB.get_table(table=table)
		return super().from_(table, *args, **kwargs)

	@classmethod
	def update(cls, table, *args, **kwargs) -> OracleQueryBuilder:
		table = OracleDB.get_table(table=table)
		return super().update(table, *args, **kwargs)

def conversion_column_value(value: str | int):
	if isinstance(value, str):
		if not value:
			return "''"

		if value[0] == "'" and value[-1] == "'":
			value = value[1:-1]

		if re.search('^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+$', value):  # noqa: W605
			ret = f"to_timestamp('{value}', 'yyyy-mm-dd hh24:mi:ss.ff6')"
		elif re.search('^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', value):  # noqa: W605
			ret = f"to_timestamp('{value}', 'yyyy-mm-dd hh24:mi:ss')"
		elif value[0] != "'" or value[-1] != "'":
			ret = "'{}'".format(value.replace("'", "''"))
		else:
			ret = value
	elif value is None:
		ret = 'NULL'
	else:
		ret = str(value)

	return ret
