from __future__ import annotations

try:
	from frappe_pypika_rs._rust import (
		capability_summary,
		render_delete,
		render_insert,
		render_insert_literals,
		render_select,
		render_select_fragments,
		render_select_query,
		render_select_star,
		render_simple_select_query,
		render_simple_select_query_literal,
		render_simple_select_query_prepared,
		render_simple_select_query_prepared_one_filter,
		render_update,
		version,
	)
except ImportError:
	capability_summary = None
	render_delete = None
	render_insert = None
	render_insert_literals = None
	render_select = None
	render_select_fragments = None
	render_select_query = None
	render_select_star = None
	render_simple_select_query = None
	render_simple_select_query_literal = None
	render_simple_select_query_prepared = None
	render_simple_select_query_prepared_one_filter = None
	render_update = None
	version = None


def is_available() -> bool:
	return version is not None


__all__ = (
	"capability_summary",
	"is_available",
	"render_delete",
	"render_insert",
	"render_insert_literals",
	"render_select",
	"render_select_fragments",
	"render_select_query",
	"render_select_star",
	"render_simple_select_query",
	"render_simple_select_query_literal",
	"render_simple_select_query_prepared",
	"render_simple_select_query_prepared_one_filter",
	"render_update",
	"version",
)
