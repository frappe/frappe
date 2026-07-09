from __future__ import annotations

import os
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, ClassVar

from pypika.enums import JoinType
from pypika.queries import QueryBuilder, Table
from pypika.terms import (
	AggregateFunction,
	BasicCriterion,
	BetweenCriterion,
	ComplexCriterion,
	ContainsCriterion,
	Criterion,
	EmptyCriterion,
	ExistsCriterion,
	Field,
	Function,
	Not,
	NullCriterion,
	Star,
	Term,
	Tuple,
	ValueWrapper,
)

ENV_ENABLE_RUST_QB = "FRAPPE_QUERY_BUILDER_RUST"

_ORIGINAL_GET_SQL_ATTR = "_frappe_python_get_sql"
_ORIGINAL_FROM_ATTR = "_frappe_python_from"
_ORIGINAL_INTO_ATTR = "_frappe_python_into"
_ORIGINAL_UPDATE_ATTR = "_frappe_python_update"

SIMPLE_FUNCTIONS = frozenset(("COALESCE", "IFNULL", "CONCAT", "NULLIF"))
SUPPORTED_LITERAL_TYPES = (str, bool, int, float)


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
	offset: int | None = None,
	distinct: bool = False,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_select is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_select(
		table, fields, quote_char=quote_char, limit=limit, offset=offset, distinct=distinct
	)


def render_select_star(
	table: str,
	quote_char: str | None = "`",
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_select_star is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_select_star(
		table, quote_char=quote_char, limit=limit, offset=offset, distinct=distinct
	)


def render_select_query(
	table: str,
	fields: list[str],
	quote_char: str | None = "`",
	where_sql: str | None = None,
	orderbys: list[str] | None = None,
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_select_query is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_select_query(
		table,
		fields,
		quote_char=quote_char,
		where_sql=where_sql,
		orderbys=orderbys,
		limit=limit,
		offset=offset,
		distinct=distinct,
	)


def render_simple_select_query(
	table: str,
	fields: list[str],
	filters: list[tuple[str, str, Any]],
	orderbys: list[tuple[str, str]] | None = None,
	quote_char: str | None = "`",
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
	groupbys: list[str] | None = None,
	select_sqls: list[str] | None = None,
) -> tuple[str, str, dict[str, Any]]:
	backend = load_backend()
	if backend is None or backend.render_simple_select_query is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	sql, prepared_sql, params = backend.render_simple_select_query(
		table,
		fields,
		filters,
		orderbys=orderbys,
		quote_char=quote_char,
		limit=limit,
		offset=offset,
		distinct=distinct,
		groupbys=groupbys,
		select_sqls=select_sqls,
	)
	return sql, prepared_sql, dict(params)


def render_simple_select_query_literal(
	table: str,
	fields: list[str],
	filters: list[tuple[str, str, Any]],
	orderbys: list[tuple[str, str]] | None = None,
	quote_char: str | None = "`",
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_simple_select_query_literal is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_simple_select_query_literal(
		table,
		fields,
		filters,
		orderbys=orderbys,
		quote_char=quote_char,
		limit=limit,
		offset=offset,
		distinct=distinct,
	)


def render_simple_select_query_with_or(
	table: str,
	fields: list[str],
	filters: list[tuple[str, str, Any]],
	or_filters: list[tuple[str, str, Any]],
	orderbys: list[tuple[str, str]] | None = None,
	quote_char: str | None = "`",
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
) -> tuple[str, str, dict[str, Any]]:
	backend = load_backend()
	if backend is None or backend.render_simple_select_query_with_or is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	sql, prepared_sql, params = backend.render_simple_select_query_with_or(
		table,
		fields,
		filters,
		or_filters,
		orderbys=orderbys,
		quote_char=quote_char,
		limit=limit,
		offset=offset,
		distinct=distinct,
	)
	return sql, prepared_sql, dict(params)


def render_simple_select_query_prepared(
	table: str,
	fields: list[str],
	filters: list[tuple[str, str, Any]],
	orderbys: list[tuple[str, str]] | None = None,
	quote_char: str | None = "`",
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
	groupbys: list[str] | None = None,
	select_sqls: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
	backend = load_backend()
	if backend is None or backend.render_simple_select_query_prepared is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	prepared_sql, params = backend.render_simple_select_query_prepared(
		table,
		fields,
		filters,
		orderbys=orderbys,
		quote_char=quote_char,
		limit=limit,
		offset=offset,
		distinct=distinct,
		groupbys=groupbys,
		select_sqls=select_sqls,
	)
	return prepared_sql, dict(params)


def render_simple_select_query_prepared_with_or(
	table: str,
	fields: list[str],
	filters: list[tuple[str, str, Any]],
	or_filters: list[tuple[str, str, Any]],
	orderbys: list[tuple[str, str]] | None = None,
	quote_char: str | None = "`",
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
) -> tuple[str, dict[str, Any]]:
	backend = load_backend()
	if backend is None or backend.render_simple_select_query_prepared_with_or is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	prepared_sql, params = backend.render_simple_select_query_prepared_with_or(
		table,
		fields,
		filters,
		or_filters,
		orderbys=orderbys,
		quote_char=quote_char,
		limit=limit,
		offset=offset,
		distinct=distinct,
	)
	return prepared_sql, dict(params)


def render_simple_select_query_prepared_one_filter(
	table: str,
	fields: list[str],
	field: str,
	operator: str,
	value: Any,
	orderbys: list[tuple[str, str]] | None = None,
	quote_char: str | None = "`",
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
) -> tuple[str, dict[str, Any]]:
	backend = load_backend()
	if backend is None or backend.render_simple_select_query_prepared_one_filter is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	prepared_sql, params = backend.render_simple_select_query_prepared_one_filter(
		table,
		fields,
		field,
		operator,
		value,
		orderbys=orderbys,
		quote_char=quote_char,
		limit=limit,
		offset=offset,
		distinct=distinct,
	)
	return prepared_sql, dict(params)


def render_select_fragments(
	table: str,
	select_sqls: list[str],
	quote_char: str | None = "`",
	join_sqls: list[str] | None = None,
	where_sql: str | None = None,
	groupbys: list[str] | None = None,
	orderbys: list[str] | None = None,
	limit: int | None = None,
	offset: int | None = None,
	distinct: bool = False,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_select_fragments is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_select_fragments(
		table,
		select_sqls,
		quote_char=quote_char,
		join_sqls=join_sqls,
		where_sql=where_sql,
		groupbys=groupbys,
		orderbys=orderbys,
		limit=limit,
		offset=offset,
		distinct=distinct,
	)


def render_insert(
	table: str,
	columns: list[str],
	rows: list[list[str]],
	quote_char: str | None = "`",
) -> str:
	backend = load_backend()
	if backend is None or backend.render_insert is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_insert(table, columns, rows, quote_char=quote_char)


def render_insert_literals(
	table: str,
	columns: list[str],
	rows: list[list[Any]],
	quote_char: str | None = "`",
) -> str:
	backend = load_backend()
	if backend is None or backend.render_insert_literals is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_insert_literals(table, columns, rows, quote_char=quote_char)


def render_update(
	table: str,
	assignments: list[str],
	quote_char: str | None = "`",
	where_sql: str | None = None,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_update is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_update(table, assignments, quote_char=quote_char, where_sql=where_sql)


def render_delete(
	table: str,
	quote_char: str | None = "`",
	where_sql: str | None = None,
) -> str:
	backend = load_backend()
	if backend is None or backend.render_delete is None:
		raise RuntimeError("frappe-pypika-rs is not available")
	return backend.render_delete(table, quote_char=quote_char, where_sql=where_sql)


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
		original_from = getattr(query_cls, _ORIGINAL_FROM_ATTR, query_cls.from_)
		original_into = getattr(query_cls, _ORIGINAL_INTO_ATTR, query_cls.into)
		original_update = getattr(query_cls, _ORIGINAL_UPDATE_ATTR, query_cls.update)
		setattr(query_cls, _ORIGINAL_FROM_ATTR, original_from)
		setattr(query_cls, _ORIGINAL_INTO_ATTR, original_into)
		setattr(query_cls, _ORIGINAL_UPDATE_ATTR, original_update)

		def from_(cls, table, *args: Any, _original_from=original_from, **kwargs: Any):
			if args or set(kwargs) - {"immutable"}:
				return _original_from(table, *args, **kwargs)
			if isinstance(table, Table) and table._schema is not None:
				return _original_from(table, *args, **kwargs)
			return RustSelectQuery(cls, table, _original_from, immutable=kwargs.get("immutable", True))

		def into(cls, table, *args: Any, _original_into=original_into, **kwargs: Any):
			if args or set(kwargs) - {"immutable"}:
				return _original_into(table, *args, **kwargs)
			if isinstance(table, Table) and table._schema is not None:
				return _original_into(table, *args, **kwargs)
			return RustInsertQuery(cls, table, _original_into, immutable=kwargs.get("immutable", True))

		def update(cls, table, *args: Any, _original_update=original_update, **kwargs: Any):
			if args or set(kwargs) - {"immutable"}:
				return _original_update(table, *args, **kwargs)
			if isinstance(table, Table) and table._schema is not None:
				return _original_update(table, *args, **kwargs)
			return RustUpdateQuery(cls, table, _original_update, immutable=kwargs.get("immutable", True))

		query_cls.from_ = classmethod(from_)
		query_cls.into = classmethod(into)
		query_cls.update = classmethod(update)


class RustSelectQuery:
	_child_queries: ClassVar[list[Any]] = []

	def __init__(self, query_cls: type, table: str | Table, original_from: Any, immutable: bool = True):
		self.query_cls = query_cls
		self.table = query_cls.DocType(table) if isinstance(table, str) else table
		self._from = [self.table]
		self.original_from = original_from
		self.immutable = immutable
		self.quote_char = _quote_char_for_query_cls(query_cls)
		self._select_terms: list[Any] = []
		self._field_names: list[str] = []
		self._where: Term | None = None
		self._orderbys: list[tuple[Any, Any]] = []
		self._groupbys: list[Any] = []
		self._joins: list[RustStoredJoin] = []
		self._where_can_prepare = True
		self._limit: int | None = None
		self._offset: int | None = None
		self._distinct = False
		self._fallback_query: QueryBuilder | None = None

	def __copy__(self):
		return self._copy_with(
			"_select_terms",
			"_field_names",
			"_orderbys",
			"_groupbys",
			"_joins",
		)

	def _copy_with(self, *list_attrs: str):
		new = type(self).__new__(type(self))
		new.query_cls = self.query_cls
		new.table = self.table
		new._from = self._from
		new.original_from = self.original_from
		new.immutable = self.immutable
		new.quote_char = self.quote_char
		new._select_terms = self._select_terms.copy() if "_select_terms" in list_attrs else self._select_terms
		new._field_names = self._field_names.copy() if "_field_names" in list_attrs else self._field_names
		new._where = self._where
		new._orderbys = self._orderbys.copy() if "_orderbys" in list_attrs else self._orderbys
		new._groupbys = self._groupbys.copy() if "_groupbys" in list_attrs else self._groupbys
		new._joins = self._joins.copy() if "_joins" in list_attrs else self._joins
		new._where_can_prepare = self._where_can_prepare
		new._limit = self._limit
		new._offset = self._offset
		new._distinct = self._distinct
		new._fallback_query = self._fallback_query
		return new

	def _builder(self, *list_attrs: str):
		return self._copy_with(*list_attrs) if self.immutable else self

	def select(self, *terms: Any):
		if self._fallback_query is not None:
			return self._fallback_query.select(*terms)

		field_names = _plain_select_fields(terms, self.table)
		if field_names is None and not all(isinstance(term, Term) for term in terms):
			return self._to_fallback().select(*terms)

		builder = self._builder("_select_terms", "_field_names")
		builder._select_terms.extend(terms)
		if field_names is not None:
			builder._field_names.extend(field_names)
		return builder

	def where(self, criterion: Term | EmptyCriterion):
		if self._fallback_query is not None:
			return self._fallback_query.where(criterion)
		if isinstance(criterion, EmptyCriterion):
			return self._builder()

		builder = self._builder()
		builder._where = criterion if builder._where is None else builder._where & criterion
		builder._where_can_prepare = builder._where_can_prepare and _is_preparable_criterion_shape(criterion)
		return builder

	def orderby(self, *fields: Any, **kwargs: Any):
		if self._fallback_query is not None:
			return self._fallback_query.orderby(*fields, **kwargs)
		order = kwargs.get("order")

		orderbys = []
		for field in fields:
			if isinstance(field, str):
				field = Field(field, table=self.table)
			elif not isinstance(field, Term):
				return self._to_fallback().orderby(*fields, **kwargs)
			orderbys.append((field, order))

		builder = self._builder("_orderbys")
		builder._orderbys.extend(orderbys)
		return builder

	def groupby(self, *terms: Any):
		if self._fallback_query is not None:
			return self._fallback_query.groupby(*terms)

		groupbys = []
		for term in terms:
			if isinstance(term, str):
				term = Field(term, table=self.table)
			elif not isinstance(term, Term):
				return self._to_fallback().groupby(*terms)
			groupbys.append(term)

		builder = self._builder("_groupbys")
		builder._groupbys.extend(groupbys)
		return builder

	def distinct(self):
		if self._fallback_query is not None:
			return self._fallback_query.distinct()

		builder = self._builder()
		builder._distinct = True
		return builder

	def join(self, item: Any, how: JoinType = JoinType.inner):
		if self._fallback_query is not None:
			return self._fallback_query.join(item, how)
		if not isinstance(item, Table) or item._schema is not None or item.alias is not None:
			return self._to_fallback().join(item, how)
		return RustJoiner(self, item, how)

	def is_joined(self, table: Table) -> bool:
		return any(table == join.item for join in self._joins)

	def inner_join(self, item: Any):
		return self.join(item, JoinType.inner)

	def left_join(self, item: Any):
		return self.join(item, JoinType.left)

	def left_outer_join(self, item: Any):
		return self.join(item, JoinType.left_outer)

	def right_join(self, item: Any):
		return self.join(item, JoinType.right)

	def right_outer_join(self, item: Any):
		return self.join(item, JoinType.right_outer)

	def outer_join(self, item: Any):
		return self.join(item, JoinType.outer)

	def full_outer_join(self, item: Any):
		return self.join(item, JoinType.full_outer)

	def delete(self):
		if self._fallback_query is not None:
			return self._fallback_query.delete()
		if (
			self._select_terms
			or self._where
			or self._orderbys
			or self._groupbys
			or self._joins
			or self._limit is not None
			or self._offset is not None
			or self._distinct
		):
			return self._to_fallback().delete()
		return RustDeleteQuery(self.query_cls, self.table, self.original_from, immutable=self.immutable)

	def limit(self, limit: int):
		if self._fallback_query is not None:
			return self._fallback_query.limit(limit)

		builder = self._builder()
		builder._limit = limit
		return builder

	def offset(self, offset: int):
		if self._fallback_query is not None:
			return self._fallback_query.offset(offset)

		builder = self._builder()
		builder._offset = offset
		return builder

	def get_sql(self, with_alias: bool = False, subquery: bool = False, **kwargs: Any) -> str:
		if self._fallback_query is not None:
			return self._fallback_query.get_sql(with_alias=with_alias, subquery=subquery, **kwargs)
		if with_alias or subquery or kwargs.get("with_namespace"):
			return self._to_fallback().get_sql(with_alias=with_alias, subquery=subquery, **kwargs)
		if not self._select_terms:
			return ""

		quote_char = kwargs.get("quote_char", self.quote_char)
		render_kwargs = kwargs.copy()
		render_kwargs.pop("quote_char", None)
		render_kwargs.pop("with_namespace", None)
		with_namespace = bool(self._joins)

		if (
			self._where is not None
			and self._where_can_prepare
			and not self._joins
			and not self._groupbys
			and self._field_names
			and not render_kwargs
		):
			filter_specs = _try_extract_simple_filter_specs(self._where)
			orderby_specs = _try_extract_simple_orderby_specs(self._orderbys)
			if filter_specs is not None and orderby_specs is not None:
				return render_simple_select_query_literal(
					self.table._table_name,
					self._field_names,
					filter_specs,
					orderbys=orderby_specs,
					quote_char=quote_char,
					limit=self._limit,
					offset=self._offset,
					distinct=self._distinct,
				)

		where_sql = None
		if self._where is not None:
			where_sql = _render_where(
				self._where, quote_char=quote_char, with_namespace=with_namespace, **render_kwargs
			)
		orderbys = _render_orderbys(
			self._orderbys, quote_char=quote_char, with_namespace=with_namespace, **render_kwargs
		)
		groupbys = _render_terms(
			self._groupbys, quote_char=quote_char, with_namespace=with_namespace, **render_kwargs
		)
		if orderbys is None:
			return self._to_fallback().get_sql(with_alias=with_alias, subquery=subquery, **kwargs)
		if groupbys is None:
			return self._to_fallback().get_sql(with_alias=with_alias, subquery=subquery, **kwargs)
		if self._joins or self._groupbys or not self._field_names:
			select_sqls = _render_select_fragments(
				self._select_terms, quote_char=quote_char, with_namespace=with_namespace, **render_kwargs
			)
			join_sqls = _render_joins(self._joins, quote_char=quote_char, **render_kwargs)
			if select_sqls is None or join_sqls is None:
				return self._to_fallback().get_sql(with_alias=with_alias, subquery=subquery, **kwargs)
			return render_select_fragments(
				self.table._table_name,
				select_sqls,
				quote_char=quote_char,
				join_sqls=join_sqls,
				where_sql=where_sql,
				groupbys=groupbys,
				orderbys=orderbys,
				limit=self._limit,
				offset=self._offset,
				distinct=self._distinct,
			)
		if where_sql or orderbys:
			return render_select_query(
				self.table._table_name,
				self._field_names,
				quote_char=quote_char,
				where_sql=where_sql,
				orderbys=orderbys,
				limit=self._limit,
				offset=self._offset,
				distinct=self._distinct,
			)
		if self._field_names == ["*"]:
			return render_select_star(
				self.table._table_name,
				quote_char=quote_char,
				limit=self._limit,
				offset=self._offset,
				distinct=self._distinct,
			)
		return render_select(
			self.table._table_name,
			self._field_names,
			quote_char=quote_char,
			limit=self._limit,
			offset=self._offset,
			distinct=self._distinct,
		)

	def walk(self):
		from frappe.query_builder.utils import prepare_query

		return prepare_query(self)

	def _frappe_prepare_query(self) -> tuple[str, dict[str, Any]] | tuple[None, None]:
		if self._fallback_query is not None or self._joins:
			return None, None
		if self._where is not None:
			if not self._where_can_prepare:
				return None, None
			prepared_where, params = _try_render_prepared_where(self._where)
			if prepared_where is None:
				return None, None

			quote_char = self.quote_char
			orderbys = _render_orderbys(self._orderbys, quote_char=quote_char)
			groupbys = _render_terms(self._groupbys, quote_char=quote_char)
			if orderbys is None or groupbys is None:
				return None, None
			if self._joins or self._groupbys or not self._field_names:
				select_sqls = _render_select_fragments(self._select_terms, quote_char=quote_char)
				if select_sqls is None:
					return None, None
				return (
					render_select_fragments(
						self.table._table_name,
						select_sqls,
						quote_char=quote_char,
						where_sql=prepared_where,
						groupbys=groupbys,
						orderbys=orderbys,
						limit=self._limit,
						offset=self._offset,
						distinct=self._distinct,
					),
					params,
				)
			return (
				render_select_query(
					self.table._table_name,
					self._field_names,
					quote_char=quote_char,
					where_sql=prepared_where,
					orderbys=orderbys,
					limit=self._limit,
					offset=self._offset,
					distinct=self._distinct,
				),
				params,
			)
		return self.get_sql(), {}

	def run(self, *args: Any, **kwargs: Any):
		from frappe.query_builder.utils import execute_query

		return execute_query(self, *args, **kwargs)

	def _to_fallback(self) -> QueryBuilder:
		if self._fallback_query is None:
			query = self.original_from(self.table, immutable=self.immutable)
			if self._select_terms:
				query = query.select(*self._select_terms)
			if self._where is not None:
				query = query.where(self._where)
			if self._distinct:
				query = query.distinct()
			if self._groupbys:
				query = query.groupby(*self._groupbys)
			for join in self._joins:
				query = query.join(join.item, join.how).on(join.criterion)
			for field, order in self._orderbys:
				query = query.orderby(field, order=order)
			if self._limit is not None:
				query = query.limit(self._limit)
			if self._offset is not None:
				query = query.offset(self._offset)
			self._fallback_query = query
		return self._fallback_query

	def __getattr__(self, name: str):
		return getattr(self._to_fallback(), name)


class RustRawSelectQuery:
	_child_queries: ClassVar[list[Any]] = []

	def __init__(
		self,
		sql: str | None,
		prepared_sql: str,
		params: dict[str, Any] | None = None,
		literal_render_args: tuple[Any, ...] | None = None,
		literal_render_kwargs: dict[str, Any] | None = None,
	):
		self.sql = sql
		self.prepared_sql = prepared_sql
		self.params = params or {}
		self.literal_render_args = literal_render_args
		self.literal_render_kwargs = literal_render_kwargs or {}
		self.immutable = True

	def get_sql(self, **kwargs: Any) -> str:
		if param_wrapper := kwargs.get("param_wrapper"):
			query = self.prepared_sql
			for key, value in self.params.items():
				query = query.replace(f"%({key})s", param_wrapper.get_sql(value), 1)
			return query
		if self.sql is None:
			self.sql = render_simple_select_query(
				*self.literal_render_args,
				**self.literal_render_kwargs,
			)[0]
		return self.sql

	def walk(self):
		from frappe.query_builder.utils import prepare_query

		return prepare_query(self)

	def run(self, *args: Any, **kwargs: Any):
		from frappe.query_builder.utils import execute_query

		return execute_query(self, *args, **kwargs)

	def _frappe_prepare_query(self) -> tuple[str, dict[str, Any]]:
		return self.prepared_sql, self.params

	def __str__(self) -> str:
		return self.get_sql()


class RustLazyRawSelectQuery(RustRawSelectQuery):
	def __init__(
		self,
		table: str,
		fields: list[str],
		filters: list[tuple[str, str, Any]],
		or_filters: list[tuple[str, str, Any]] | None = None,
		**render_kwargs: Any,
	):
		super().__init__(None, "", {})
		self.table = table
		self.fields = fields
		self.filters = filters
		self.or_filters = or_filters or []
		self.render_kwargs = render_kwargs

	def _ensure_rendered(self) -> None:
		if self.prepared_sql:
			return
		if self.or_filters:
			self.sql, self.prepared_sql, self.params = render_simple_select_query_with_or(
				self.table,
				self.fields,
				self.filters,
				self.or_filters,
				**self.render_kwargs,
			)
		else:
			self.sql, self.prepared_sql, self.params = render_simple_select_query(
				self.table,
				self.fields,
				self.filters,
				**self.render_kwargs,
			)

	def get_sql(self, **kwargs: Any) -> str:
		self._ensure_rendered()
		return super().get_sql(**kwargs)

	def _frappe_prepare_query(self) -> tuple[str, dict[str, Any]]:
		self._ensure_rendered()
		return self.prepared_sql, self.params


class RustJoiner:
	def __init__(self, query: RustSelectQuery, item: Table, how: JoinType):
		self.query = query
		self.item = item
		self.how = how

	def on(self, criterion: Criterion | None, collate: str | None = None):
		if collate is not None or criterion is None:
			return self.query._to_fallback().join(self.item, self.how).on(criterion, collate=collate)

		builder = self.query._builder("_joins")
		builder._joins.append(RustStoredJoin(self.item, self.how, criterion))
		return builder

	def on_field(self, *fields: Any):
		return self.query._to_fallback().join(self.item, self.how).on_field(*fields)

	def using(self, *fields: Any):
		return self.query._to_fallback().join(self.item, self.how).using(*fields)

	def cross(self):
		return self.query._to_fallback().join(self.item, self.how).cross()


class RustStoredJoin:
	def __init__(self, item: Table, how: JoinType, criterion: Criterion):
		self.item = item
		self.how = how
		self.criterion = criterion


class RustDeleteQuery:
	def __init__(self, query_cls: type, table: Table, original_from: Any, immutable: bool = True):
		self.query_cls = query_cls
		self.table = table
		self.original_from = original_from
		self.immutable = immutable
		self.quote_char = _quote_char_for_query_cls(query_cls)
		self._where: Term | None = None
		self._fallback_query: QueryBuilder | None = None

	def __copy__(self):
		return self._copy()

	def _copy(self):
		new = type(self).__new__(type(self))
		new.query_cls = self.query_cls
		new.table = self.table
		new.original_from = self.original_from
		new.immutable = self.immutable
		new.quote_char = self.quote_char
		new._where = self._where
		new._fallback_query = self._fallback_query
		return new

	def _builder(self):
		return self._copy() if self.immutable else self

	def where(self, criterion: Term | EmptyCriterion):
		if self._fallback_query is not None:
			return self._fallback_query.where(criterion)
		if isinstance(criterion, EmptyCriterion):
			return self._builder()

		builder = self._builder()
		builder._where = criterion if builder._where is None else builder._where & criterion
		return builder

	def get_sql(self, **kwargs: Any) -> str:
		if self._fallback_query is not None:
			return self._fallback_query.get_sql(**kwargs)

		quote_char = kwargs.get("quote_char", self.quote_char)
		where_sql = None
		if self._where is not None:
			where_sql = _render_where(self._where, quote_char=quote_char, **kwargs)
		return render_delete(self.table._table_name, quote_char=quote_char, where_sql=where_sql)

	def run(self, *args: Any, **kwargs: Any):
		from frappe.query_builder.utils import execute_query

		return execute_query(self, *args, **kwargs)

	def walk(self):
		from frappe.query_builder.utils import prepare_query

		return prepare_query(self)

	def _frappe_prepare_query(self) -> tuple[str, dict[str, Any]] | tuple[None, None]:
		if self._fallback_query is not None or self._where is not None:
			return None, None
		return self.get_sql(), {}

	def _to_fallback(self) -> QueryBuilder:
		if self._fallback_query is None:
			query = self.original_from(self.table, immutable=self.immutable).delete()
			if self._where is not None:
				query = query.where(self._where)
			self._fallback_query = query
		return self._fallback_query

	def __getattr__(self, name: str):
		return getattr(self._to_fallback(), name)


class RustInsertQuery:
	def __init__(self, query_cls: type, table: str | Table, original_into: Any, immutable: bool = True):
		self.query_cls = query_cls
		self.table = query_cls.DocType(table) if isinstance(table, str) else table
		self.original_into = original_into
		self.immutable = immutable
		self.quote_char = _quote_char_for_query_cls(query_cls)
		self._columns: list[Field | None] = []
		self._column_names: list[str] = []
		self._rows: list[list[Term]] = []
		self._raw_rows: list[list[Any]] | None = []
		self._rows_materialized = True
		self._fallback_query: QueryBuilder | None = None

	def __copy__(self):
		return self._copy_with("_columns", "_column_names", "_rows", "_raw_rows")

	def _copy_with(self, *list_attrs: str):
		new = type(self).__new__(type(self))
		new.query_cls = self.query_cls
		new.table = self.table
		new.original_into = self.original_into
		new.immutable = self.immutable
		new.quote_char = self.quote_char
		new._columns = self._columns.copy() if "_columns" in list_attrs else self._columns
		new._column_names = self._column_names.copy() if "_column_names" in list_attrs else self._column_names
		new._rows = [row.copy() for row in self._rows] if "_rows" in list_attrs else self._rows
		if self._raw_rows is None:
			new._raw_rows = None
		elif "_raw_rows" in list_attrs:
			new._raw_rows = [row.copy() for row in self._raw_rows]
		else:
			new._raw_rows = self._raw_rows
		new._rows_materialized = self._rows_materialized
		new._fallback_query = self._fallback_query
		return new

	def _builder(self, *list_attrs: str):
		return self._copy_with(*list_attrs) if self.immutable else self

	def columns(self, *terms: Any):
		if self._fallback_query is not None:
			return self._fallback_query.columns(*terms)
		if terms and isinstance(terms[0], (list, tuple)):
			terms = terms[0]

		columns: list[Field | None] = []
		column_names = []
		for term in terms:
			if isinstance(term, str):
				columns.append(None)
				column_names.append(term)
			elif isinstance(term, Field) and term.table in (None, self.table):
				columns.append(term)
				column_names.append(term.name)
			else:
				return self._to_fallback().columns(*terms)

		builder = self._builder("_columns", "_column_names")
		builder._columns.extend(columns)
		builder._column_names.extend(column_names)
		return builder

	def insert(self, *terms: Any):
		if self._fallback_query is not None:
			return self._fallback_query.insert(*terms)
		if not terms:
			return self._builder()
		if not isinstance(terms[0], (list, tuple, set)):
			terms = [terms]

		rows = []
		raw_rows = None if self._raw_rows is None else [row.copy() for row in self._raw_rows]
		rows_materialized = self._rows_materialized
		for values in terms:
			if raw_rows is not None and all(_is_supported_literal(value) for value in values):
				raw_rows.append(list(values))
				rows_materialized = False
				continue

			if raw_rows is not None and not rows_materialized:
				rows.extend([[_wrap_constant(self.query_cls, value) for value in row] for row in raw_rows])
			raw_rows = None
			rows_materialized = True
			rows.append(
				[
					value if isinstance(value, Term) else _wrap_constant(self.query_cls, value)
					for value in values
				]
			)

		builder = self._builder("_rows", "_raw_rows")
		builder._rows.extend(rows)
		builder._raw_rows = raw_rows
		builder._rows_materialized = rows_materialized
		return builder

	def get_sql(self, **kwargs: Any) -> str:
		if self._fallback_query is not None:
			return self._fallback_query.get_sql(**kwargs)
		if not self._column_names or (not self._rows and not self._raw_rows):
			return ""

		quote_char = kwargs.get("quote_char", self.quote_char)
		columns = self._column_names
		if kwargs.get("param_wrapper") is None and self._raw_rows is not None:
			rows = [[_render_insert_literal(value) for value in row] for row in self._raw_rows]
			return render_insert(self.table._table_name, columns, rows, quote_char=quote_char)
		self._materialize_rows()
		rows = [
			[value.get_sql(with_alias=True, subquery=True, quote_char=quote_char, **kwargs) for value in row]
			for row in self._rows
		]
		return render_insert(self.table._table_name, columns, rows, quote_char=quote_char)

	def run(self, *args: Any, **kwargs: Any):
		from frappe.query_builder.utils import execute_query

		return execute_query(self, *args, **kwargs)

	def walk(self):
		from frappe.query_builder.utils import prepare_query

		return prepare_query(self)

	def _frappe_prepare_query(self) -> tuple[str, dict[str, Any]] | tuple[None, None]:
		if self._fallback_query is not None or self._raw_rows is None:
			return None, None
		return self.get_sql(), {}

	def _materialize_rows(self) -> None:
		if self._rows_materialized:
			return
		self._rows = [
			[_wrap_constant(self.query_cls, value) for value in row] for row in self._raw_rows or []
		]
		self._rows_materialized = True

	def _materialized_columns(self) -> list[Field]:
		return [
			column if column is not None else Field(name, table=self.table)
			for column, name in zip(self._columns, self._column_names, strict=True)
		]

	def _to_fallback(self) -> QueryBuilder:
		if self._fallback_query is None:
			self._materialize_rows()
			query = self.original_into(self.table, immutable=self.immutable)
			if self._column_names:
				query = query.columns(*self._materialized_columns())
			for row in self._rows:
				query = query.insert(row)
			self._fallback_query = query
		return self._fallback_query

	def __getattr__(self, name: str):
		return getattr(self._to_fallback(), name)


class RustUpdateQuery:
	def __init__(self, query_cls: type, table: str | Table, original_update: Any, immutable: bool = True):
		self.query_cls = query_cls
		self.table = query_cls.DocType(table) if isinstance(table, str) else table
		self.original_update = original_update
		self.immutable = immutable
		self.quote_char = _quote_char_for_query_cls(query_cls)
		self._updates: list[tuple[Field, str, Term]] = []
		self._raw_updates: list[tuple[Field, str, Any]] | None = []
		self._updates_materialized = True
		self._where: Term | None = None
		self._fallback_query: QueryBuilder | None = None

	def __copy__(self):
		return self._copy_with("_updates", "_raw_updates")

	def _copy_with(self, *list_attrs: str):
		new = type(self).__new__(type(self))
		new.query_cls = self.query_cls
		new.table = self.table
		new.original_update = self.original_update
		new.immutable = self.immutable
		new.quote_char = self.quote_char
		new._updates = self._updates.copy() if "_updates" in list_attrs else self._updates
		if self._raw_updates is None:
			new._raw_updates = None
		elif "_raw_updates" in list_attrs:
			new._raw_updates = self._raw_updates.copy()
		else:
			new._raw_updates = self._raw_updates
		new._updates_materialized = self._updates_materialized
		new._where = self._where
		new._fallback_query = self._fallback_query
		return new

	def _builder(self, *list_attrs: str):
		return self._copy_with(*list_attrs) if self.immutable else self

	def set(self, field: Field | str, value: Any):
		if self._fallback_query is not None:
			return self._fallback_query.set(field, value)
		field = Field(field, table=self.table) if isinstance(field, str) else field
		if not isinstance(field, Field) or field.table not in (None, self.table):
			return self._to_fallback().set(field, value)

		builder = self._builder("_updates", "_raw_updates")
		if builder._raw_updates is not None and _is_supported_literal(value):
			builder._raw_updates.append((field, field.name, value))
			builder._updates_materialized = False
		else:
			builder._materialize_updates()
			builder._raw_updates = None
			builder._updates.append(
				(
					field,
					field.name,
					value if isinstance(value, Term) else _wrap_constant(self.query_cls, value),
				)
			)
			builder._updates_materialized = True
		return builder

	def where(self, criterion: Term | EmptyCriterion):
		if self._fallback_query is not None:
			return self._fallback_query.where(criterion)
		if isinstance(criterion, EmptyCriterion):
			return self._builder()

		builder = self._builder()
		builder._where = criterion if builder._where is None else builder._where & criterion
		return builder

	def get_sql(self, **kwargs: Any) -> str:
		if self._fallback_query is not None:
			return self._fallback_query.get_sql(**kwargs)
		if not self._updates and not self._raw_updates:
			return ""

		quote_char = kwargs.get("quote_char", self.quote_char)
		assignments = self._render_assignments(quote_char=quote_char, **kwargs)
		where_sql = None
		if self._where is not None:
			where_sql = _render_where(self._where, quote_char=quote_char, **kwargs)
		return render_update(self.table._table_name, assignments, quote_char=quote_char, where_sql=where_sql)

	def run(self, *args: Any, **kwargs: Any):
		from frappe.query_builder.utils import execute_query

		return execute_query(self, *args, **kwargs)

	def walk(self):
		from frappe.query_builder.utils import prepare_query

		return prepare_query(self)

	def _frappe_prepare_query(self) -> tuple[str, dict[str, Any]] | tuple[None, None]:
		if self._fallback_query is not None or self._where is not None:
			return None, None
		return self.get_sql(), {}

	def _render_assignments(self, quote_char: str | None = "`", **kwargs: Any) -> list[str]:
		if kwargs.get("param_wrapper") is None and self._raw_updates is not None:
			return [
				f"{_quote_identifier(field_name, quote_char)}={_render_literal(value)}"
				for _field, field_name, value in self._raw_updates
			]

		self._materialize_updates()
		return [
			f"{_quote_identifier(field_name, quote_char)}={value.get_sql(quote_char=quote_char, **kwargs)}"
			for _field, field_name, value in self._updates
		]

	def _materialize_updates(self) -> None:
		if self._updates_materialized:
			return
		self._updates = [
			(field, field_name, _wrap_constant(self.query_cls, value))
			for field, field_name, value in self._raw_updates or []
		]
		self._updates_materialized = True

	def _to_fallback(self) -> QueryBuilder:
		if self._fallback_query is None:
			self._materialize_updates()
			query = self.original_update(self.table, immutable=self.immutable)
			for field, _field_name, value in self._updates:
				query = query.set(field, value)
			if self._where is not None:
				query = query.where(self._where)
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
	if table._schema is not None:
		return None
	fields = _plain_select_fields(query._selects, table)
	if fields is None:
		return None

	query._set_kwargs_defaults(kwargs)
	return render_select(
		table._table_name,
		fields,
		quote_char=kwargs.get("quote_char"),
		limit=query._limit,
		offset=query._offset,
		distinct=query._distinct,
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


def _is_supported_literal(value: Any) -> bool:
	return value is None or isinstance(value, SUPPORTED_LITERAL_TYPES)


def _wrap_constant(query_cls: type, value: Any) -> Term:
	return query_cls._builder().wrap_constant(value)


def _quote_identifier(value: str, quote_char: str | None = "`") -> str:
	if quote_char != "'":
		return _quote_identifier_cached(value, quote_char)
	return _quote_identifier_uncached(value, quote_char)


@lru_cache(maxsize=4096)
def _quote_identifier_cached(value: str, quote_char: str | None = "`") -> str:
	return _quote_identifier_uncached(value, quote_char)


def _quote_identifier_uncached(value: str, quote_char: str | None = "`") -> str:
	if not quote_char:
		return value
	return f"{quote_char}{value.replace(quote_char, quote_char * 2)}{quote_char}"


def _format_alias(sql: str, alias: str | None, quote_char: str | None = "`") -> str:
	if alias is None:
		return sql
	return f"{sql} {_quote_identifier(alias, quote_char)}"


def _try_render_simple_term(
	term: Term,
	quote_char: str | None = "`",
	with_alias: bool = False,
	with_namespace: bool = False,
) -> str | None:
	if isinstance(term, Star):
		sql = term.get_sql(quote_char=quote_char, with_namespace=with_namespace)
		return _format_alias(sql, term.alias, quote_char) if with_alias else sql
	if isinstance(term, Field):
		sql = _quote_identifier(term.name, quote_char)
		if term.table and (with_namespace or term.table.alias):
			sql = f"{_quote_identifier(term.table.get_table_name(), quote_char)}.{sql}"
		return _format_alias(sql, term.alias, quote_char) if with_alias else sql
	if isinstance(term, AggregateFunction):
		if (
			getattr(term, "schema", None) is not None
			or getattr(term, "_filters", None)
			or getattr(term, "_include_filter", False)
		):
			return None
		args = []
		for arg in term.args:
			if not isinstance(arg, Field | Star):
				return None
			sql = _try_render_simple_term(arg, quote_char=quote_char, with_namespace=with_namespace)
			if sql is None:
				return None
			args.append(sql)
		if getattr(term, "_distinct", False) and args:
			args[0] = f"DISTINCT {args[0]}"
		sql = f"{term.name}({','.join(args)})"
		return _format_alias(sql, term.alias, quote_char) if with_alias else sql
	if isinstance(term, Function):
		if getattr(term, "schema", None) is not None or term.name not in SIMPLE_FUNCTIONS:
			return None
		args = []
		for arg in term.args:
			if not isinstance(arg, Field) and not (
				isinstance(arg, ValueWrapper) and arg.alias is None and _is_supported_literal(arg.value)
			):
				return None
			sql = _try_render_simple_value(arg, quote_char=quote_char, with_namespace=with_namespace)
			if sql is None:
				return None
			args.append(sql)
		sql = f"{term.name}({','.join(args)})"
		return _format_alias(sql, term.alias, quote_char) if with_alias else sql
	return None


def _render_where(
	criterion: Term,
	quote_char: str | None = "`",
	with_namespace: bool = False,
	**kwargs: Any,
) -> str:
	return _try_render_simple_criterion(
		criterion, quote_char=quote_char, with_namespace=with_namespace, **kwargs
	) or criterion.get_sql(quote_char=quote_char, subquery=True, with_namespace=with_namespace, **kwargs)


def _try_render_simple_criterion(
	criterion: Term,
	quote_char: str | None = "`",
	with_namespace: bool = False,
	**kwargs: Any,
) -> str | None:
	if isinstance(criterion, ComplexCriterion):
		left = _render_criterion_part(
			criterion.left, quote_char=quote_char, with_namespace=with_namespace, **kwargs
		)
		right = _render_criterion_part(
			criterion.right, quote_char=quote_char, with_namespace=with_namespace, **kwargs
		)
		if left is None or right is None:
			return None
		return f"{left} {criterion.comparator.value} {right}"

	if isinstance(criterion, BasicCriterion):
		left = _try_render_simple_term(criterion.left, quote_char=quote_char, with_namespace=with_namespace)
		right = _try_render_simple_value(
			criterion.right, quote_char=quote_char, with_namespace=with_namespace, **kwargs
		)
		if left is None or right is None:
			return None
		return f"{left}{criterion.comparator.value}{right}"

	if isinstance(criterion, ContainsCriterion):
		term = _try_render_simple_term(criterion.term, quote_char=quote_char, with_namespace=with_namespace)
		container = _try_render_simple_tuple(criterion.container, quote_char=quote_char, **kwargs)
		if term is None or container is None:
			return None
		operator = "NOT IN" if criterion._is_negated else "IN"
		return f"{term} {operator} {container}"

	if isinstance(criterion, BetweenCriterion):
		term = _try_render_simple_term(criterion.term, quote_char=quote_char, with_namespace=with_namespace)
		start = _try_render_simple_value(
			criterion.start, quote_char=quote_char, with_namespace=with_namespace, **kwargs
		)
		end = _try_render_simple_value(
			criterion.end, quote_char=quote_char, with_namespace=with_namespace, **kwargs
		)
		if term is None or start is None or end is None:
			return None
		return f"{term} BETWEEN {start} AND {end}"

	if isinstance(criterion, NullCriterion):
		term = _try_render_simple_term(criterion.term, quote_char=quote_char, with_namespace=with_namespace)
		if term is None:
			return None
		return f"{term} IS NULL"

	if isinstance(criterion, Not):
		term = _try_render_simple_criterion(
			criterion.term, quote_char=quote_char, with_namespace=with_namespace, **kwargs
		)
		if term is None:
			return None
		return f"NOT {term}"

	return None


def _render_criterion_part(
	criterion: Term,
	quote_char: str | None = "`",
	with_namespace: bool = False,
	**kwargs: Any,
) -> str | None:
	return _try_render_simple_criterion(
		criterion, quote_char=quote_char, with_namespace=with_namespace, **kwargs
	) or criterion.get_sql(quote_char=quote_char, subquery=True, with_namespace=with_namespace, **kwargs)


def _try_render_prepared_where(criterion: Term) -> tuple[str | None, dict[str, Any]]:
	params: dict[str, Any] = {}
	sql = _try_render_prepared_criterion(criterion, params)
	return sql, params


def _try_extract_simple_filter_specs(criterion: Term) -> list[tuple[str, str, Any]] | None:
	if isinstance(criterion, ComplexCriterion):
		if criterion.comparator.value != "AND":
			return None
		left = _try_extract_simple_filter_specs(criterion.left)
		right = _try_extract_simple_filter_specs(criterion.right)
		if left is None or right is None:
			return None
		return left + right

	if isinstance(criterion, BasicCriterion):
		field = _try_extract_simple_filter_field(criterion.left)
		value = _try_extract_simple_filter_value(criterion.right)
		if field is None or value is _UNSUPPORTED:
			return None
		return [(field, criterion.comparator.value, value)]

	if isinstance(criterion, ContainsCriterion):
		field = _try_extract_simple_filter_field(criterion.term)
		value = _try_extract_simple_filter_tuple(criterion.container)
		if field is None or value is None:
			return None
		operator = "NOT IN" if criterion._is_negated else "IN"
		return [(field, operator, value)]

	return None


def _try_extract_simple_orderby_specs(orderbys: list[tuple[Any, Any]]) -> list[tuple[str, str]] | None:
	rendered = []
	for field, order in orderbys:
		if not isinstance(field, Field) or (field.table and field.table.alias):
			return None
		direction = getattr(order, "value", None)
		if direction is None:
			direction = "ASC"
		rendered.append((field.name, direction))
	return rendered


def _try_extract_simple_filter_field(term: Term) -> str | None:
	if not isinstance(term, Field) or term.alias is not None:
		return None
	if term.table and term.table.alias:
		return None
	return term.name


_UNSUPPORTED = object()


def _try_extract_simple_filter_value(term: Term) -> Any:
	if isinstance(term, ValueWrapper) and term.alias is None and _is_supported_literal(term.value):
		return term.value
	return _UNSUPPORTED


def _try_extract_simple_filter_tuple(term: Term) -> list[Any] | None:
	if not isinstance(term, Tuple):
		return None
	values = []
	for value in term.values:
		raw_value = _try_extract_simple_filter_value(value)
		if raw_value is _UNSUPPORTED:
			return None
		values.append(raw_value)
	return values


def _is_preparable_criterion_shape(criterion: Term) -> bool:
	if isinstance(criterion, ComplexCriterion):
		return _is_preparable_criterion_shape(criterion.left) and _is_preparable_criterion_shape(
			criterion.right
		)
	if isinstance(criterion, BasicCriterion):
		return isinstance(criterion.left, Field) and _is_preparable_value_shape(criterion.right)
	if isinstance(criterion, ContainsCriterion):
		return isinstance(criterion.term, Field) and _is_preparable_tuple_shape(criterion.container)
	if isinstance(criterion, BetweenCriterion):
		return (
			isinstance(criterion.term, Field)
			and _is_preparable_value_shape(criterion.start)
			and _is_preparable_value_shape(criterion.end)
		)
	if isinstance(criterion, NullCriterion):
		return isinstance(criterion.term, Field)
	if isinstance(criterion, Not):
		return _is_preparable_criterion_shape(criterion.term)
	if isinstance(criterion, ExistsCriterion):
		return False
	return False


def _is_preparable_tuple_shape(term: Term) -> bool:
	return isinstance(term, Tuple)


def _is_preparable_value_shape(term: Term) -> bool:
	return isinstance(term, Field) or (
		isinstance(term, ValueWrapper) and term.alias is None and _is_supported_literal(term.value)
	)


def _try_render_prepared_criterion(criterion: Term, params: dict[str, Any]) -> str | None:
	if isinstance(criterion, ComplexCriterion):
		left = _try_render_prepared_criterion_part(criterion.left, params)
		right = _try_render_prepared_criterion_part(criterion.right, params)
		if left is None or right is None:
			return None
		return f"{left} {criterion.comparator.value} {right}"

	if isinstance(criterion, BasicCriterion):
		left = _try_render_simple_term(criterion.left)
		right = _try_render_prepared_value(criterion.right, params)
		if left is None or right is None:
			return None
		return f"{left}{criterion.comparator.value}{right}"

	if isinstance(criterion, ContainsCriterion):
		term = _try_render_simple_term(criterion.term)
		container = _try_render_prepared_tuple(criterion.container, params)
		if term is None or container is None:
			return None
		operator = "NOT IN" if criterion._is_negated else "IN"
		return f"{term} {operator} {container}"

	if isinstance(criterion, BetweenCriterion):
		term = _try_render_simple_term(criterion.term)
		start = _try_render_prepared_value(criterion.start, params)
		end = _try_render_prepared_value(criterion.end, params)
		if term is None or start is None or end is None:
			return None
		return f"{term} BETWEEN {start} AND {end}"

	if isinstance(criterion, NullCriterion):
		term = _try_render_simple_term(criterion.term)
		if term is None:
			return None
		return f"{term} IS NULL"

	if isinstance(criterion, Not):
		term = _try_render_prepared_criterion(criterion.term, params)
		if term is None:
			return None
		return f"NOT {term}"

	return None


def _try_render_prepared_criterion_part(criterion: Term, params: dict[str, Any]) -> str | None:
	return _try_render_prepared_criterion(criterion, params)


def _try_render_prepared_tuple(term: Term, params: dict[str, Any]) -> str | None:
	if not isinstance(term, Tuple):
		return None
	values = [_try_render_prepared_value(value, params) for value in term.values]
	if any(value is None for value in values):
		return None
	return f"({','.join(values)})"


def _try_render_prepared_value(term: Term, params: dict[str, Any]) -> str | None:
	if isinstance(term, Field):
		return _try_render_simple_term(term)

	if isinstance(term, ValueWrapper) and term.alias is None:
		value = term.value
		if isinstance(value, str):
			param_name = f"param{len(params) + 1}"
			params[param_name] = value
			return f"%({param_name})s"
		if _is_supported_literal(value):
			return _render_literal(value)

	return None


def _try_render_simple_tuple(
	term: Term,
	quote_char: str | None = "`",
	**kwargs: Any,
) -> str | None:
	if not isinstance(term, Tuple):
		return None
	if kwargs.get("param_wrapper") is None:
		if sql := _try_render_literal_tuple(term):
			return sql
	values = [_try_render_simple_value(value, quote_char=quote_char, **kwargs) for value in term.values]
	if any(value is None for value in values):
		return None
	return f"({','.join(values)})"


def _try_render_literal_tuple(term: Tuple) -> str | None:
	values = []
	for value in term.values:
		if not isinstance(value, ValueWrapper) or value.alias is not None:
			return None
		raw_value = value.value
		if raw_value is None:
			values.append("NULL")
		elif isinstance(raw_value, bool):
			values.append("true" if raw_value else "false")
		elif isinstance(raw_value, int | float):
			values.append(str(raw_value))
		elif isinstance(raw_value, str):
			values.append(_quote_identifier(raw_value, "'"))
		else:
			return None
	return f"({','.join(values)})"


def _try_render_simple_value(
	term: Term,
	quote_char: str | None = "`",
	**kwargs: Any,
) -> str | None:
	if isinstance(term, Field):
		return _try_render_simple_term(
			term, quote_char=quote_char, with_namespace=kwargs.get("with_namespace", False)
		)

	if isinstance(term, ValueWrapper) and term.alias is None:
		value = term.value
		if kwargs.get("param_wrapper") is not None and isinstance(value, str):
			return kwargs["param_wrapper"].get_sql(value)
		if kwargs.get("param_wrapper") is None and _is_supported_literal(value):
			return _render_literal(value)

	return term.get_sql(quote_char=quote_char, **kwargs)


def _render_literal(value: Any) -> str:
	if value is None:
		return "NULL"
	if isinstance(value, bool):
		return "true" if value else "false"
	if isinstance(value, int | float):
		return str(value)
	if isinstance(value, str):
		return _quote_identifier(value, "'")
	raise TypeError(f"unsupported literal value: {type(value).__name__}")


def _render_insert_literal(value: Any) -> str:
	if value is None:
		return "null"
	return _render_literal(value)


def _render_select_fragments(
	selects: Sequence[Any],
	quote_char: str | None = "`",
	with_namespace: bool = False,
	**kwargs: Any,
) -> list[str] | None:
	rendered = []
	for select in selects:
		if not isinstance(select, Term):
			return None
		if sql := _try_render_simple_term(
			select, quote_char=quote_char, with_alias=True, with_namespace=with_namespace
		):
			rendered.append(sql)
			continue
		rendered.append(
			select.get_sql(
				with_alias=True,
				subquery=True,
				quote_char=quote_char,
				with_namespace=with_namespace,
				**kwargs,
			)
		)
	return rendered


def _render_terms(
	terms: Sequence[Any],
	quote_char: str | None = "`",
	with_namespace: bool = False,
	**kwargs: Any,
) -> list[str] | None:
	rendered = []
	for term in terms:
		if not isinstance(term, Term):
			return None
		rendered.append(
			_try_render_simple_term(term, quote_char=quote_char, with_namespace=with_namespace)
			or term.get_sql(quote_char=quote_char, with_namespace=with_namespace, **kwargs)
		)
	return rendered


def _render_joins(
	joins: list[RustStoredJoin], quote_char: str | None = "`", **kwargs: Any
) -> list[str] | None:
	rendered = []
	for join in joins:
		if not isinstance(join.criterion, Criterion):
			return None

		table_sql = _render_join_table(join.item, quote_char=quote_char)
		if table_sql is None:
			table_sql = join.item.get_sql(subquery=True, with_alias=True, quote_char=quote_char, **kwargs)
		join_sql = f"JOIN {table_sql}"
		if join.how.value:
			join_sql = f"{join.how.value} {join_sql}"
		criterion_sql = _try_render_simple_criterion(
			join.criterion, quote_char=quote_char, with_namespace=True, **kwargs
		) or join.criterion.get_sql(
			subquery=True,
			quote_char=quote_char,
			with_namespace=True,
			**kwargs,
		)
		rendered.append(f"{join_sql} ON {criterion_sql}")
	return rendered


def _render_join_table(table: Table, quote_char: str | None = "`") -> str | None:
	if table._schema is not None or table.alias is not None:
		return None
	return _quote_identifier(table._table_name, quote_char)


def _render_orderbys(
	orderbys: list[tuple[Any, Any]],
	quote_char: str | None = "`",
	with_namespace: bool = False,
	**kwargs: Any,
) -> list[str] | None:
	rendered = []
	for field, order in orderbys:
		if not isinstance(field, (Field, Criterion)):
			return None
		field_sql = _try_render_simple_term(field, quote_char=quote_char, with_namespace=with_namespace)
		if field_sql is None:
			field_sql = field.get_sql(quote_char=quote_char, with_namespace=with_namespace, **kwargs)
		if order is not None:
			field_sql = f"{field_sql} {order.value}"
		rendered.append(field_sql)
	return rendered


def _quote_char_for_query_cls(query_cls: type) -> str | None:
	if query_cls.__name__ == "MariaDB":
		return "`"
	if query_cls.__name__ == "Postgres":
		return '"'
	if query_cls.__name__ == "SQLite":
		return ""
	return None
