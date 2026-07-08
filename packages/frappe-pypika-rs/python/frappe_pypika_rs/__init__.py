from __future__ import annotations

try:
	from frappe_pypika_rs._rust import capability_summary, version
except ImportError:
	capability_summary = None
	version = None


def is_available() -> bool:
	return version is not None


__all__ = ("capability_summary", "is_available", "version")
