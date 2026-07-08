from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pypika.queries import QueryBuilder, Table
from pypika.terms import Field, Star

ENV_ENABLE_RUST_QB = "FRAPPE_QUERY_BUILDER_RUST"

_ORIGINAL_GET_SQL_ATTR = "_frappe_python_get_sql"


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


def _plain_select_fields(selects: list[Any], table: Table) -> list[str] | None:
	fields = []
	for select in selects:
		if isinstance(select, Star):
			fields.append("*")
		elif isinstance(select, Field) and select.alias is None and select.table in (None, table):
			fields.append(select.name)
		else:
			return None
	return fields
