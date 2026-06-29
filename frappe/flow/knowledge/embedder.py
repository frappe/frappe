# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Embedding calls for the knowledge store, via litellm.

Credentials resolve the same way as chat models: the Flow Model row first,
falling back to the central Flow Provider store.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

BATCH_SIZE = 96  # smallest common provider batch limit (Cohere)
EMBED_TIMEOUT = 120
PROBE_TIMEOUT = 30


def embed_texts(texts: list[str]) -> list[list[float]]:
	"""Embed texts with the model from Flow Knowledge Settings, preserving order."""
	if not texts:
		return []
	config = _embedding_config()
	vectors: list[list[float]] = []
	for start in range(0, len(texts), BATCH_SIZE):
		vectors.extend(_embed_batch(texts[start : start + BATCH_SIZE], config, timeout=EMBED_TIMEOUT))
	return vectors


def probe_dimension(model: str) -> int:
	"""Vector width a Flow Model's embeddings come back with, via a one-input call."""
	config = _model_config(model)
	(vector,) = _embed_batch(["dimension probe"], config, timeout=PROBE_TIMEOUT)
	return len(vector)


def _embedding_config() -> dict[str, Any]:
	settings = frappe.get_cached_doc("Flow Knowledge Settings")
	if not settings.embedding_model:
		frappe.throw(
			_("Set an embedding model in Flow Knowledge Settings first."),
			title=_("Knowledge Not Configured"),
		)
	return _model_config(settings.embedding_model)


def _model_config(model: str) -> dict[str, Any]:
	from flow.lib.model import resolve_provider_credentials

	doc = frappe.get_doc("Flow Model", model)
	if not doc.enabled:
		frappe.throw(_("Flow Model {0} is disabled.").format(model), title=_("Model Disabled"))

	provider_creds = resolve_provider_credentials(doc.model_id)
	config: dict[str, Any] = {
		"model": doc.model_id,
		"api_key": doc.get_password("api_key", raise_exception=False) or provider_creds.get("api_key") or "",
	}
	base_url = doc.base_url or provider_creds.get("base_url")
	if base_url:
		config["api_base"] = base_url
	return config


def _embed_batch(texts: list[str], config: dict[str, Any], *, timeout: int) -> list[list[float]]:
	import litellm

	try:
		response = litellm.embedding(input=texts, timeout=timeout, **config)
	except Exception as e:
		frappe.throw(str(e)[:500] or type(e).__name__, title=_("Embedding Failed"))

	entries = sorted(response.data, key=lambda entry: _get(entry, "index") or 0)
	vectors = [[float(value) for value in _get(entry, "embedding")] for entry in entries]
	if len(vectors) != len(texts):
		frappe.throw(
			_("Embedding provider returned {0} vectors for {1} inputs.").format(len(vectors), len(texts)),
			title=_("Embedding Failed"),
		)
	return vectors


def _get(entry: Any, key: str) -> Any:
	return entry.get(key) if isinstance(entry, dict) else getattr(entry, key, None)
