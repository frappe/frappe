from __future__ import annotations

try:
	from frappe_pypika_rs._rust import (
		capability_summary,
		render_delete,
		render_insert,
		render_select,
		render_select_fragments,
		render_select_query,
		render_select_star,
		render_update,
		version,
	)
except ImportError:
	capability_summary = None
	render_delete = None
	render_insert = None
	render_select = None
	render_select_fragments = None
	render_select_query = None
	render_select_star = None
	render_update = None
	version = None


def is_available() -> bool:
	return version is not None


__all__ = (
	"capability_summary",
	"is_available",
	"render_delete",
	"render_insert",
	"render_select",
	"render_select_fragments",
	"render_select_query",
	"render_select_star",
	"render_update",
	"version",
)
