import inspect
from collections.abc import Callable
from enum import Enum
from importlib import import_module
from typing import Any, get_type_hints

from pypika.queries import Column, QueryBuilder, _SetOperation
from pypika.terms import PseudoColumn

import frappe
from frappe.query_builder.terms import NamedParameterWrapper

from .builder import Base, MariaDB, Postgres, SQLite


class PseudoColumnMapper(PseudoColumn):
	def __init__(self, name: str) -> None:
		super().__init__(name)

	def get_sql(self, **kwargs):
		if frappe.db.db_type == "postgres":
			self.name = self.name.replace("`", '"')
		return self.name


class db_type_is(Enum):
	MARIADB = "mariadb"
	POSTGRES = "postgres"
	SQLITE = "sqlite"


DB_TYPE_MAP = {
	db_type_is.MARIADB: MariaDB,
	db_type_is.POSTGRES: Postgres,
	db_type_is.SQLITE: SQLite,
}


class ImportMapper:
	def __init__(self, func_map: dict[db_type_is, Callable]) -> None:
		self.func_map = func_map

	def __call__(self, *args: Any, **kwds: Any) -> Callable:
		db = db_type_is(frappe.conf.db_type)
		return self.func_map[db](*args, **kwds)


class BuilderIdentificationFailed(Exception):
	def __init__(self):
		super().__init__("Couldn't guess builder")


def get_query_builder(type_of_db: str) -> Postgres | MariaDB | SQLite:
	"""Return the query builder object.

	Args:
	        type_of_db: string value of the db used
	"""
	return DB_TYPE_MAP[db_type_is(type_of_db)]


def get_query(*args, **kwargs) -> QueryBuilder:
	from frappe.database.query import Engine

	return Engine().get_query(*args, **kwargs)


def get_attr(method_string):
	modulename = ".".join(method_string.split(".")[:-1])
	methodname = method_string.split(".")[-1]
	return getattr(import_module(modulename), methodname)


def DocType(*args, **kwargs):
	return frappe.qb.DocType(*args, **kwargs)


def Table(*args, **kwargs):
	return frappe.qb.Table(*args, **kwargs)


def mask_fields(
	doctype: str,
	fields: list[Any],
	result: list[dict] | list[tuple],
	as_dict: bool = True,
) -> list[dict] | list[tuple]:
	"""Mask fields in the result based on the doctype's masked fields.

	Args:
		doctype: Name of the DocType being queried
		fields: List of field objects from the query
		result: Query results as list of dicts or tuples
		as_dict: Whether results are dictionaries (True) or tuples (False)

	Returns:
		Result with masked field values applied based on user permissions
	"""
	from frappe.database.query import CORE_DOCTYPES
	from frappe.model.utils.mask import mask_dict_results, mask_list_results

	# We can't query meta for core doctypes here
	if doctype in CORE_DOCTYPES:
		return result

	masked_fields = frappe.get_meta(doctype).get_masked_fields()

	if not masked_fields:
		return result

	if not as_dict:
		field_index_map = {}
		for idx, field in enumerate(fields):
			# Handle aliases (e.g. `tabSI`.`posting_date` as posting_date)
			if alias := getattr(field, "alias", None):
				field_index_map[alias] = idx
			elif name := getattr(field, "name", None):
				field_index_map[name] = idx

		return mask_list_results(result, masked_fields, field_index_map)

	# Handle as_dict format
	return mask_dict_results(result, masked_fields)


def execute_query(query, *args, **kwargs):
	dt = query.__dict__.get("_doctype")
	fields = query.__dict__.get("_fields_list", [])
	child_queries = query._child_queries
	query, params = prepare_query(query)
	result = frappe.local.db.sql(query, params, *args, **kwargs)  # nosemgrep

	if child_queries and isinstance(child_queries, list) and result:
		execute_child_queries(child_queries, result)

	if result and dt and fields:
		as_dict = kwargs.get("as_dict", not kwargs.get("as_list", False))
		result = mask_fields(dt, fields, result, as_dict=as_dict)

	return result


def execute_child_queries(queries, result):
	if not isinstance(result[0], dict) or not result[0].name:
		return
	parent_names = [d.name for d in result]
	for child_query in queries:
		data = child_query.get_query(parent_names).run(as_dict=1)
		for row in result:
			row[child_query.fieldname] = []
			for d in data:
				if str(d.parent) == str(row.name) and d.parentfield == child_query.fieldname:
					if "parent" not in child_query.fields:
						del d["parent"]
					if "parentfield" not in child_query.fields:
						del d["parentfield"]
					row[child_query.fieldname].append(d)


def prepare_query(query):
	from frappe.utils.safe_exec import SERVER_SCRIPT_FILE_PREFIX, check_safe_sql_query

	param_collector = NamedParameterWrapper()
	query = query.get_sql(param_wrapper=param_collector)
	if frappe.local.flags.get("in_safe_exec", False):
		if not check_safe_sql_query(query, throw=False):
			callstack = inspect.stack()

			# This check is required because QB can execute from anywhere and we can not
			# reliably provide a safe version for it in server scripts.

			# since query objects are patched everywhere any query.run()
			# will have callstack like this:
			# frame0: this function prepare_query()
			# frame1: execute_query()
			# frame2: frame that called `query.run()`
			#
			# if frame2 is server script <serverscript> is set as the filename it shouldn't be allowed.
			if len(callstack) >= 3 and SERVER_SCRIPT_FILE_PREFIX in callstack[2].filename:
				raise frappe.PermissionError("Only SELECT SQL allowed in scripting")

	if frappe.local.flags.get("in_render_safe_exec", False):
		check_safe_sql_query(query, throw=True)

	assert isinstance(query, str), "prepared query must be a SQL string"
	return query, param_collector.parameters


def patch_query_execute():
	"""Patch the Query Builder with helper execute method
	This excludes the use of `frappe.db.sql` method while
	executing the query object
	"""

	QueryBuilder.run = execute_query
	QueryBuilder.walk = prepare_query

	# To support running union queries
	_SetOperation.run = execute_query
	_SetOperation.walk = prepare_query


def patch_query_aggregation():
	"""Patch aggregation functions to frappe.qb"""
	from frappe.query_builder.functions import _avg, _max, _min, _sum

	Base.max = _max
	Base.min = _min
	Base.avg = _avg
	Base.sum = _sum


def patch_get_query():
	Base.get_query = get_query


def patch_like_operators():
	"""Render the query-builder LIKE / NOT LIKE operators as ILIKE / NOT ILIKE on postgres.

	MariaDB's default collation makes LIKE case-insensitive; postgres compares text
	case-sensitively, so a `.like()` search (link-field autocomplete, etc.) would only match
	exact case on postgres. Mapping to ILIKE keeps pattern matching case-insensitive on both
	backends -- matching MariaDB and the like->ilike translation `frappe.db.get_list` already
	applies for its filter path. MariaDB keeps native LIKE.
	"""
	# pypika has no hook for dialect-specific operator rendering, so patch Term.like/not_like the same
	# way the query-builder patches above (QueryBuilder.run, Base.max, ...) and app.py's
	# Request.max_form_memory_size do. The rule anchors on the import, so suppress it there too.
	from pypika.terms import Term  # nosemgrep: frappe-monkey-patching-not-allowed

	_like, _not_like = Term.like, Term.not_like

	def like(self, expr: str):
		if frappe.db and frappe.db.db_type == "postgres":
			return self.ilike(expr)
		return _like(self, expr)

	def not_like(self, expr: str):
		if frappe.db and frappe.db.db_type == "postgres":
			return self.not_ilike(expr)
		return _not_like(self, expr)

	Term.like = like  # nosemgrep: frappe-monkey-patching-not-allowed
	Term.not_like = not_like  # nosemgrep: frappe-monkey-patching-not-allowed


# Free-text fieldtypes whose equality MariaDB's default collation compares case-insensitively. The
# same set the dict/list filter path folds; `name`, Link and Select are matched exactly on both.
CASE_INSENSITIVE_FIELDTYPES = frozenset(
	{
		"Data",
		"Small Text",
		"Text",
		"Long Text",
		"Text Editor",
		"Code",
		"HTML Editor",
		"Markdown Editor",
	}
)


def _qb_field_is_free_text(field) -> bool:
	"""Return True if a pypika ``Field`` points at a Data/Text-family column whose equality MariaDB
	folds case-insensitively. The DocType is recovered from the field's ``tab<DocType>`` table; bare
	fields, subquery columns, unknown doctypes, ``name``, Link/Select and framework core doctypes all
	return False so the comparison stays exact. Result is memoized on ``frappe.local`` (per request,
	so multi-site and custom-field changes stay correct)."""
	table = getattr(field, "table", None)
	table_name = getattr(table, "_table_name", None)
	fieldname = getattr(field, "name", None)
	if not (isinstance(table_name, str) and table_name.startswith("tab")):
		return False
	if not isinstance(fieldname, str) or fieldname == "name" or "." in fieldname:
		return False
	try:
		cache = frappe.local._qb_free_text_cache
	except AttributeError:
		cache = frappe.local._qb_free_text_cache = {}
	except RuntimeError:
		# frappe.local is not bound to a context yet -- skip folding rather than fail.
		return False
	key = (table_name, fieldname)
	if key in cache:
		return cache[key]
	if getattr(frappe.local, "_qb_resolving_free_text", False):
		# `frappe.get_meta()` itself builds queries (with their own `Field == value` criteria), so a
		# lookup must not re-enter while one is already in flight -- that would recurse forever. Don't
		# fold (and don't cache) the comparisons made *inside* meta resolution.
		return False
	doctype = table_name[len("tab") :]
	from frappe.database.query import CORE_DOCTYPES

	if doctype in CORE_DOCTYPES:
		# Framework meta tables (DocType/DocField/Custom Field/Property Setter, ...) store identifiers
		# -- target doctype names, fieldnames -- in text columns whose equality is meant to be exact.
		# Folding them would corrupt schema sync / meta lookups, so never fold a core doctype.
		cache[key] = False
		return False
	frappe.local._qb_resolving_free_text = True
	try:
		df = frappe.get_meta(doctype).get_field(fieldname)
		cache[key] = bool(df) and df.fieldtype in CASE_INSENSITIVE_FIELDTYPES
	except frappe.DoesNotExistError:
		# `tab<X>` is not a DocType (alias, virtual/temp table, ...) -> compare exactly. Any other
		# error from get_meta propagates so genuine meta failures stay visible instead of silently
		# falling back to a case-sensitive comparison.
		cache[key] = False
	finally:
		frappe.local._qb_resolving_free_text = False
	return cache[key]


def patch_equality_operators():
	"""Fold free-text equality case-insensitively on postgres so a hand-built ``frappe.qb`` criterion
	(``table.text_field == "x"`` or ``table.text_field.isin([...])``) matches the same rows as MariaDB,
	whose default collation compares text case-insensitively. Mirrors :func:`patch_like_operators` for
	``=`` / ``!=`` / ``IN`` and the LOWER() folding the dict/list filter path already applies.

	Only a bare ``Field == <str>`` / ``!= <str>`` / ``.isin([<str>, ...])`` (and ``.notin``) on a
	Data/Text-family column is folded -- Field-vs-Field, numeric, ``None``, a non-string/subquery ``IN``
	argument, ``name``/Link/Select and MariaDB are left exactly as they were. Patched on ``Field`` (not
	``Term``) so the wrapping ``Lower(field)`` -- a ``Function`` -- keeps the native operator and cannot
	recurse.

	The fold decision reads ``frappe.db.db_type`` when the criterion is *built* (the same point
	:func:`patch_like_operators` checks), not when it is executed. db_type is stable within a request,
	so this is safe; a criterion built before ``frappe.db`` is a Postgres connection just renders a
	plain ``=``.

	Note: ``LOWER(field) = '...'`` cannot use a plain B-tree index, so a free-text equality filter that
	was index-backed becomes a scan on Postgres (MariaDB's case-insensitive collation indexes natively).
	Add a functional index ``... (LOWER(column))`` -- or a ``citext`` column -- for hot free-text lookups.
	"""
	from pypika.functions import Lower
	from pypika.terms import Field  # nosemgrep: frappe-monkey-patching-not-allowed

	_eq, _ne, _isin = Field.__eq__, Field.__ne__, Field.isin

	def _is_postgres() -> bool:
		return bool(frappe.db) and frappe.db.db_type == "postgres"

	def _eq_foldable(self, other) -> bool:
		return isinstance(other, str) and other != "" and _is_postgres() and _qb_field_is_free_text(self)

	def _in_foldable(self, arg) -> bool:
		# only a non-empty list/tuple/set of plain strings -- never a subquery Term or mixed types
		return (
			isinstance(arg, (list, tuple, set, frozenset))
			and len(arg) > 0
			and all(isinstance(v, str) for v in arg)
			and _is_postgres()
			and _qb_field_is_free_text(self)
		)

	def __eq__(self, other):
		if _eq_foldable(self, other):
			return _eq(Lower(self), other.lower())
		return _eq(self, other)

	def __ne__(self, other):
		if _eq_foldable(self, other):
			return _ne(Lower(self), other.lower())
		return _ne(self, other)

	def isin(self, arg):
		if _in_foldable(self, arg):
			return _isin(Lower(self), [v.lower() for v in arg])
		return _isin(self, arg)

	Field.__eq__ = __eq__  # nosemgrep: frappe-monkey-patching-not-allowed
	Field.__ne__ = __ne__  # nosemgrep: frappe-monkey-patching-not-allowed
	# `Field.notin` is `Term.notin`, which delegates to `self.isin(...).negate()`, so patching `isin`
	# folds `notin` too.
	Field.isin = isin  # nosemgrep: frappe-monkey-patching-not-allowed


def patch_all():
	patch_query_execute()
	patch_query_aggregation()
	patch_get_query()
	patch_like_operators()
	patch_equality_operators()
