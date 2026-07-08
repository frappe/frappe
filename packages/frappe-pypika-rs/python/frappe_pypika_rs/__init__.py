from __future__ import annotations

try:
	from frappe_pypika_rs._rust import capability_summary, render_select, render_select_star, version
except ImportError:
	capability_summary = None
	render_select = None
	render_select_star = None
	version = None


def is_available() -> bool:
	return version is not None


__all__ = ("capability_summary", "is_available", "render_select", "render_select_star", "version")
