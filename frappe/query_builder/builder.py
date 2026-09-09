import re
import types
import typing
from copy import copy

from pypika import MySQLQuery, Order, PostgreSQLQuery, SQLLiteQuery, terms
from pypika.dialects import MySQLQueryBuilder, PostgreSQLQueryBuilder, SQLLiteQueryBuilder
from pypika.queries import QueryBuilder, Schema, Table
from pypika.terms import Criterion, EmptyCriterion, Field, Function, Term
from pypika.utils import QueryException, builder

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


class RecursiveCTEMixin:
	"""Adds `WITH RECURSIVE` support to a pypika query builder. Pass `recursive=True` to
	`frappe.qb.with_(subquery, name, recursive=True)` and reference the CTE inside its own recursive
	term via `pypika.Table(name)`. Renders `WITH RECURSIVE` on postgres, mariadb (10.2+) and sqlite;
	a non-recursive builder is byte-for-byte unchanged (`recursive` defaults to False)."""

	def __init__(self, *args, recursive: bool = False, **kwargs):
		super().__init__(*args, **kwargs)
		self._recursive_cte = recursive

	def _with_sql(self, **kwargs) -> str:
		keyword = "WITH RECURSIVE " if getattr(self, "_recursive_cte", False) else "WITH "
		return keyword + ",".join(
			clause.name + " AS (" + clause.get_sql(subquery=False, with_alias=False, **kwargs) + ") "
			for clause in self._with
		)


class RecursiveMySQLQueryBuilder(RecursiveCTEMixin, MySQLQueryBuilder):
	pass


class RecursivePostgreSQLQueryBuilder(RecursiveCTEMixin, PostgreSQLQueryBuilder):
	pass


class SQLiteConflictQueryBuilderMixin:
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._on_conflict = False
		self._on_conflict_fields = []
		self._on_conflict_do_nothing = False
		self._on_conflict_do_updates = []
		self._on_conflict_wheres = None
		self._on_conflict_do_update_wheres = None

	def __copy__(self):
		newone = super().__copy__()
		newone._on_conflict_fields = copy(self._on_conflict_fields)
		newone._on_conflict_do_updates = copy(self._on_conflict_do_updates)
		return newone

	@builder
	def on_conflict(self, *target_fields: str | Term):
		if not self._insert_table:
			raise QueryException("On conflict only applies to insert query")

		self._on_conflict = True
		for target_field in target_fields:
			if isinstance(target_field, str):
				self._on_conflict_fields.append(Field(target_field, table=self._insert_table))
			elif isinstance(target_field, Term):
				self._on_conflict_fields.append(target_field)
			elif target_field is not None:
				raise QueryException("Unsupported conflict target")

	@builder
	def do_nothing(self):
		if self._on_conflict_do_updates:
			raise QueryException("Can not have two conflict handlers")
		self._on_conflict_do_nothing = True

	@builder
	def do_update(self, update_field: str | Field, update_value: typing.Any = None):
		if self._on_conflict_do_nothing:
			raise QueryException("Can not have two conflict handlers")

		if isinstance(update_field, str):
			field = Field(update_field, table=self._insert_table)
		elif isinstance(update_field, Field):
			field = update_field
		else:
			raise QueryException("Unsupported update field")

		value = self.wrap_constant(update_value, self._wrapper_cls) if update_value is not None else None
		self._on_conflict_do_updates.append((field, value))

	@builder
	def where(self, criterion: Criterion):
		if not self._on_conflict:
			return super().where(criterion)
		if isinstance(criterion, EmptyCriterion):
			return
		if self._on_conflict_do_nothing:
			raise QueryException("DO NOTHING does not support WHERE")

		if self._on_conflict_fields and self._on_conflict_do_updates:
			if self._on_conflict_do_update_wheres:
				self._on_conflict_do_update_wheres &= criterion
			else:
				self._on_conflict_do_update_wheres = criterion
		elif self._on_conflict_fields:
			if self._on_conflict_wheres:
				self._on_conflict_wheres &= criterion
			else:
				self._on_conflict_wheres = criterion
		else:
			raise QueryException("Can not have fieldless ON CONFLICT WHERE")

	def _on_conflict_sql(self, **kwargs) -> str:
		if not self._on_conflict_do_nothing and not self._on_conflict_do_updates:
			if not self._on_conflict_fields:
				return ""
			raise QueryException("No handler defined for on conflict")
		if self._on_conflict_do_updates and not self._on_conflict_fields:
			raise QueryException("Can not have fieldless on conflict do update")

		query = " ON CONFLICT"
		field_kwargs = {**kwargs, "with_namespace": False}
		if self._on_conflict_fields:
			fields = ", ".join(
				field.get_sql(with_alias=True, **field_kwargs) for field in self._on_conflict_fields
			)
			query += f" ({fields})"
		if self._on_conflict_wheres:
			query += f" WHERE {self._on_conflict_wheres.get_sql(subquery=True, **field_kwargs)}"
		return query

	def _on_conflict_action_sql(self, **kwargs) -> str:
		if self._on_conflict_do_nothing:
			return " DO NOTHING"
		if not self._on_conflict_do_updates:
			return ""

		updates = []
		field_kwargs = {**kwargs, "with_namespace": False}
		for field, value in self._on_conflict_do_updates:
			field_sql = field.get_sql(**field_kwargs)
			value_sql = (
				value.get_sql(with_namespace=True, **kwargs) if value is not None else f"EXCLUDED.{field_sql}"
			)
			updates.append(f"{field_sql}={value_sql}")

		query = f" DO UPDATE SET {','.join(updates)}"
		if self._on_conflict_do_update_wheres:
			where = self._on_conflict_do_update_wheres.get_sql(subquery=True, with_namespace=True, **kwargs)
			query += f" WHERE {where}"
		return query

	def get_sql(self, with_alias: bool = False, subquery: bool = False, **kwargs) -> str:
		self._set_kwargs_defaults(kwargs)
		query = super().get_sql(with_alias, subquery, **kwargs)
		return query + self._on_conflict_sql(**kwargs) + self._on_conflict_action_sql(**kwargs)


class RecursiveSQLLiteQueryBuilder(RecursiveCTEMixin, SQLiteConflictQueryBuilderMixin, SQLLiteQueryBuilder):
	def __init__(self, *args, **kwargs):
		# SQLite rejects parentheses around the individual SELECT statements in a compound query.
		kwargs["wrap_set_operation_queries"] = False
		super().__init__(*args, **kwargs)


class MariaDB(Base, MySQLQuery):
	Field = terms.Field

	_BuilderClasss = RecursiveMySQLQueryBuilder

	@classmethod
	def _builder(cls, *args, **kwargs) -> "RecursiveMySQLQueryBuilder":
		return RecursiveMySQLQueryBuilder(*args, wrapper_cls=ParameterizedValueWrapper, **kwargs)

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

	_BuilderClasss = RecursivePostgreSQLQueryBuilder

	@classmethod
	def _builder(cls, *args, **kwargs) -> "RecursivePostgreSQLQueryBuilder":
		return RecursivePostgreSQLQueryBuilder(*args, wrapper_cls=ParameterizedValueWrapper, **kwargs)

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


class SQLite(Base, SQLLiteQuery):
	Field = terms.Field

	_BuilderClasss = RecursiveSQLLiteQueryBuilder

	@classmethod
	def _builder(cls, *args, **kwargs) -> "RecursiveSQLLiteQueryBuilder":
		return RecursiveSQLLiteQueryBuilder(*args, wrapper_cls=SQLiteParameterizedValueWrapper, **kwargs)

	@classmethod
	def from_(cls, table, *args, **kwargs):
		if isinstance(table, str):
			table = cls.DocType(table)
		return super().from_(table, *args, **kwargs)
