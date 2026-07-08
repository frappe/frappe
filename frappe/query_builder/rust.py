from __future__ import annotations

import os
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, ClassVar

from pypika.queries import QueryBuilder, Table
from pypika.terms import Field, Star

ENV_ENABLE_RUST_QB = "FRAPPE_QUERY_BUILDER_RUST"

_ORIGINAL_GET_SQL_ATTR = "_frappe_python_get_sql"
_ORIGINAL_FROM_ATTR = "_frappe_python_from"


def is_enabled() -> bool:
	return os.environ.get(ENV_ENABLE_RUST_QB) == "1" and is_available()


@lru_cache
def load_backend() -> Any | None:
	try:
		import frappe_pypika_rs
	except ImportError:
		return None

	if not frappe_pypika_rs.is_available():
		return None

	return frappe_pypika_rs


def is_available() -> bool:
	return load_backend() is not None


def capability_summary() -> list[str]:
	backend = load_backend()
	if backend is None or backend.capability_summary is None:
		return []
	return list(backend.capability_summary())


def render_select(
	table: str,
	fields: list[str],
	quote_char: str | None = "`",
	limit: int | None = None,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_select is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_select(table, fields, quote_char=quote_char, limit=limit)


def render_select_star(
	table: str,
	quote_char: str | None = "`",
	limit: int | None = None,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_select_star is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_select_star(table, quote_char=quote_char, limit=limit)


def patch_querybuilder_get_sql() -> None:
	if not is_enabled() or hasattr(QueryBuilder, _ORIGINAL_GET_SQL_ATTR):
		return

	original_get_sql = QueryBuilder.get_sql
	setattr(QueryBuilder, _ORIGINAL_GET_SQL_ATTR, original_get_sql)

	def get_sql(self, with_alias: bool = False, subquery: bool = False, **kwargs: Any) -> str:
		if sql := _try_render_simple_select(self, with_alias=with_alias, subquery=subquery, **kwargs):
			return sql
		return original_get_sql(self, with_alias=with_alias, subquery=subquery, **kwargs)

	QueryBuilder.get_sql = get_sql
	patch_query_classes_from()


def patch_query_classes_from() -> None:
	from frappe.query_builder.builder import MariaDB, Postgres, SQLite

	for query_cls in (MariaDB, Postgres, SQLite):
		if hasattr(query_cls, _ORIGINAL_FROM_ATTR):
			continue

		original_from = query_cls.from_
		setattr(query_cls, _ORIGINAL_FROM_ATTR, original_from)

		def from_(cls, table, *args: Any, _original_from=original_from, **kwargs: Any):
			if args or set(kwargs) - {"immutable"}:
				return _original_from(table, *args, **kwargs)
			return RustSelectQuery(cls, table, _original_from, immutable=kwargs.get("immutable", True))

		query_cls.from_ = classmethod(from_)


class RustSelectQuery:
	_child_queries: ClassVar[list[Any]] = []

	def __init__(self, query_cls: type, table: str | Table, original_from: Any, immutable: bool = True):
		self.query_cls = query_cls
		self.table = query_cls.DocType(table) if isinstance(table, str) else table
		self.original_from = original_from
		self.immutable = immutable
		self.quote_char = _quote_char_for_query_cls(query_cls)
		self._select_terms: list[Any] = []
		self._field_names: list[str] = []
		self._limit: int | None = None
		self._fallback_query: QueryBuilder | None = None

	def __copy__(self):
		new = type(self).__new__(type(self))
		new.__dict__.update(self.__dict__)
		new._select_terms = self._select_terms.copy()
		new._field_names = self._field_names.copy()
		return new

	def _builder(self):
		return self.__copy__() if self.immutable else self

	def select(self, *terms: Any):
		if self._fallback_query is not None:
			return self._fallback_query.select(*terms)

		field_names = _plain_select_fields(terms, self.table)
		if field_names is None:
			return self._to_fallback().select(*terms)

		builder = self._builder()
		builder._select_terms.extend(terms)
		builder._field_names.extend(field_names)
		return builder

	def limit(self, limit: int):
		if self._fallback_query is not None:
			return self._fallback_query.limit(limit)

		builder = self._builder()
		builder._limit = limit
		return builder

	def get_sql(self, with_alias: bool = False, subquery: bool = False, **kwargs: Any) -> str:
		if self._fallback_query is not None:
			return self._fallback_query.get_sql(with_alias=with_alias, subquery=subquery, **kwargs)
		if with_alias or subquery or kwargs.get("with_namespace"):
			return self._to_fallback().get_sql(with_alias=with_alias, subquery=subquery, **kwargs)
		if not self._field_names:
			return ""

		quote_char = kwargs.get("quote_char", self.quote_char)
		if self._field_names == ["*"]:
			return render_select_star(self.table._table_name, quote_char=quote_char, limit=self._limit)
		return render_select(
			self.table._table_name, self._field_names, quote_char=quote_char, limit=self._limit
		)

	def walk(self):
		from frappe.query_builder.utils import prepare_query

		return prepare_query(self)

	def run(self, *args: Any, **kwargs: Any):
		from frappe.query_builder.utils import execute_query

		return execute_query(self, *args, **kwargs)

	def _to_fallback(self) -> QueryBuilder:
		if self._fallback_query is None:
			query = self.original_from(self.table, immutable=self.immutable)
			if self._select_terms:
				query = query.select(*self._select_terms)
			if self._limit is not None:
				query = query.limit(self._limit)
			self._fallback_query = query
		return self._fallback_query

	def __getattr__(self, name: str):
		return getattr(self._to_fallback(), name)


def _try_render_simple_select(
	query: QueryBuilder,
	with_alias: bool = False,
	subquery: bool = False,
	**kwargs: Any,
) -> str | None:
	if with_alias or subquery or kwargs.get("with_namespace"):
		return None
	if not _is_plain_select(query):
		return None
	if len(query._from) != 1 or not isinstance(query._from[0], Table):
		return None

	table = query._from[0]
	fields = _plain_select_fields(query._selects, table)
	if fields is None:
		return None

	query._set_kwargs_defaults(kwargs)
	return render_select(
		table._table_name,
		fields,
		quote_char=kwargs.get("quote_char"),
		limit=query._limit,
	)


def _is_plain_select(query: QueryBuilder) -> bool:
	return bool(query._selects) and not any(
		(
			query._with,
			query._insert_table,
			query._update_table,
			query._delete_from,
			query._replace,
			query._force_indexes,
			query._use_indexes,
			query._columns,
			query._values,
			query._distinct,
			query._ignore,
			query._for_update,
			query._wheres,
			query._prewheres,
			query._groupbys,
			query._with_totals,
			query._havings,
			query._qualifys,
			query._orderbys,
			query._joins,
			query._unions,
			query._using,
			query._offset,
			query._updates,
			query._select_star_tables,
			query._mysql_rollup,
			query._select_into,
			query._foreign_table,
		)
	)


def _plain_select_fields(selects: Sequence[Any], table: Table) -> list[str] | None:
	fields = []
	for select in selects:
		if isinstance(select, str):
			fields.append("*" if select == "*" else select)
		elif isinstance(select, Star):
			fields.append("*")
		elif isinstance(select, Field) and select.alias is None and select.table in (None, table):
			fields.append(select.name)
		else:
			return None
	return fields


def _quote_char_for_query_cls(query_cls: type) -> str | None:
	if query_cls.__name__ == "MariaDB":
		return "`"
	if query_cls.__name__ == "Postgres":
		return '"'
	if query_cls.__name__ == "SQLite":
		return ""
	return None
