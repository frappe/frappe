from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

ENV_ENABLE_RUST_QB = "FRAPPE_QUERY_BUILDER_RUST"


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
