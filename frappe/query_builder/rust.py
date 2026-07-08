from __future__ import annotations

import os
from collections.abc import Sequence
from functools import lru_cache
from typing import Any, ClassVar

from pypika.enums import JoinType
from pypika.queries import QueryBuilder, Table
from pypika.terms import AggregateFunction, Criterion, EmptyCriterion, Field, Star, Term

ENV_ENABLE_RUST_QB = "FRAPPE_QUERY_BUILDER_RUST"

_ORIGINAL_GET_SQL_ATTR = "_frappe_python_get_sql"
_ORIGINAL_FROM_ATTR = "_frappe_python_from"
_ORIGINAL_INTO_ATTR = "_frappe_python_into"
_ORIGINAL_UPDATE_ATTR = "_frappe_python_update"


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
		self._limit: int | None = None
		self._offset: int | None = None
		self._distinct = False
		self._fallback_query: QueryBuilder | None = None

	def __copy__(self):
		new = type(self).__new__(type(self))
		new.__dict__.update(self.__dict__)
		new._select_terms = self._select_terms.copy()
		new._field_names = self._field_names.copy()
		new._orderbys = self._orderbys.copy()
		new._groupbys = self._groupbys.copy()
		new._joins = self._joins.copy()
		return new

	def _builder(self):
		return self.__copy__() if self.immutable else self

	def select(self, *terms: Any):
		if self._fallback_query is not None:
			return self._fallback_query.select(*terms)

		field_names = _plain_select_fields(terms, self.table)
		if field_names is None and not all(isinstance(term, Term) for term in terms):
			return self._to_fallback().select(*terms)

		builder = self._builder()
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

		builder = self._builder()
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

		builder = self._builder()
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
		where_sql = (
			self._where.get_sql(
				quote_char=quote_char,
				subquery=True,
				with_namespace=with_namespace,
				**render_kwargs,
			)
			if self._where is not None
			else None
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


class RustJoiner:
	def __init__(self, query: RustSelectQuery, item: Table, how: JoinType):
		self.query = query
		self.item = item
		self.how = how

	def on(self, criterion: Criterion | None, collate: str | None = None):
		if collate is not None or criterion is None:
			return self.query._to_fallback().join(self.item, self.how).on(criterion, collate=collate)

		builder = self.query._builder()
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
		new = type(self).__new__(type(self))
		new.__dict__.update(self.__dict__)
		return new

	def _builder(self):
		return self.__copy__() if self.immutable else self

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
		where_sql = self._where.get_sql(quote_char=quote_char, **kwargs) if self._where is not None else None
		return render_delete(self.table._table_name, quote_char=quote_char, where_sql=where_sql)

	def run(self, *args: Any, **kwargs: Any):
		from frappe.query_builder.utils import execute_query

		return execute_query(self, *args, **kwargs)

	def walk(self):
		from frappe.query_builder.utils import prepare_query

		return prepare_query(self)

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
		self._columns: list[Field] = []
		self._rows: list[list[Term]] = []
		self._raw_rows: list[list[Any]] | None = []
		self._fallback_query: QueryBuilder | None = None

	def __copy__(self):
		new = type(self).__new__(type(self))
		new.__dict__.update(self.__dict__)
		new._columns = self._columns.copy()
		new._rows = [row.copy() for row in self._rows]
		new._raw_rows = None if self._raw_rows is None else [row.copy() for row in self._raw_rows]
		return new

	def _builder(self):
		return self.__copy__() if self.immutable else self

	def columns(self, *terms: Any):
		if self._fallback_query is not None:
			return self._fallback_query.columns(*terms)
		if terms and isinstance(terms[0], (list, tuple)):
			terms = terms[0]

		columns = []
		for term in terms:
			if isinstance(term, str):
				columns.append(Field(term, table=self.table))
			elif isinstance(term, Field) and term.table in (None, self.table):
				columns.append(term)
			else:
				return self._to_fallback().columns(*terms)

		builder = self._builder()
		builder._columns.extend(columns)
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
		for values in terms:
			if raw_rows is not None:
				if all(_is_supported_literal(value) for value in values):
					raw_rows.append(list(values))
				else:
					raw_rows = None
			rows.append(
				[
					value if isinstance(value, Term) else self.query_cls._builder().wrap_constant(value)
					for value in values
				]
			)

		builder = self._builder()
		builder._rows.extend(rows)
		if builder._raw_rows is not None:
			builder._raw_rows = raw_rows
		return builder

	def get_sql(self, **kwargs: Any) -> str:
		if self._fallback_query is not None:
			return self._fallback_query.get_sql(**kwargs)
		if not self._columns or not self._rows:
			return ""

		quote_char = kwargs.get("quote_char", self.quote_char)
		columns = [column.name for column in self._columns]
		if kwargs.get("param_wrapper") is None and self._raw_rows is not None:
			return render_insert_literals(
				self.table._table_name, columns, self._raw_rows, quote_char=quote_char
			)
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

	def _to_fallback(self) -> QueryBuilder:
		if self._fallback_query is None:
			query = self.original_into(self.table, immutable=self.immutable)
			if self._columns:
				query = query.columns(*self._columns)
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
		self._updates: list[tuple[Field, Term]] = []
		self._where: Term | None = None
		self._fallback_query: QueryBuilder | None = None

	def __copy__(self):
		new = type(self).__new__(type(self))
		new.__dict__.update(self.__dict__)
		new._updates = self._updates.copy()
		return new

	def _builder(self):
		return self.__copy__() if self.immutable else self

	def set(self, field: Field | str, value: Any):
		if self._fallback_query is not None:
			return self._fallback_query.set(field, value)
		field = Field(field, table=self.table) if isinstance(field, str) else field
		if not isinstance(field, Field) or field.table not in (None, self.table):
			return self._to_fallback().set(field, value)
		value = value if isinstance(value, Term) else self.query_cls._builder().wrap_constant(value)

		builder = self._builder()
		builder._updates.append((field, value))
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
		if not self._updates:
			return ""

		quote_char = kwargs.get("quote_char", self.quote_char)
		assignments = [
			f"{field.get_sql(quote_char=quote_char, with_namespace=False, **kwargs)}={value.get_sql(quote_char=quote_char, **kwargs)}"
			for field, value in self._updates
		]
		where_sql = self._where.get_sql(quote_char=quote_char, **kwargs) if self._where is not None else None
		return render_update(self.table._table_name, assignments, quote_char=quote_char, where_sql=where_sql)

	def run(self, *args: Any, **kwargs: Any):
		from frappe.query_builder.utils import execute_query

		return execute_query(self, *args, **kwargs)

	def walk(self):
		from frappe.query_builder.utils import prepare_query

		return prepare_query(self)

	def _to_fallback(self) -> QueryBuilder:
		if self._fallback_query is None:
			query = self.original_update(self.table, immutable=self.immutable)
			for field, value in self._updates:
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


def _is_supported_literal(value: Any) -> bool:
	return value is None or isinstance(value, str | bool | int | float)


def _quote_identifier(value: str, quote_char: str | None = "`") -> str:
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
	if isinstance(term, AggregateFunction) and _is_simple_aggregate(term):
		args = [
			_try_render_simple_term(arg, quote_char=quote_char, with_namespace=with_namespace)
			for arg in term.args
		]
		if any(arg is None for arg in args):
			return None
		if getattr(term, "_distinct", False):
			args[0] = f"DISTINCT {args[0]}"
		sql = f"{term.name}({','.join(args)})"
		return _format_alias(sql, term.alias, quote_char) if with_alias else sql
	return None


def _is_simple_aggregate(term: AggregateFunction) -> bool:
	return (
		getattr(term, "schema", None) is None
		and not getattr(term, "_filters", None)
		and not getattr(term, "_include_filter", False)
		and all(isinstance(arg, Field | Star) for arg in term.args)
	)


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

		table_sql = join.item.get_sql(subquery=True, with_alias=True, quote_char=quote_char, **kwargs)
		join_sql = f"JOIN {table_sql}"
		if join.how.value:
			join_sql = f"{join.how.value} {join_sql}"
		criterion_sql = join.criterion.get_sql(
			subquery=True, quote_char=quote_char, with_namespace=True, **kwargs
		)
		rendered.append(f"{join_sql} ON {criterion_sql}")
	return rendered


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
