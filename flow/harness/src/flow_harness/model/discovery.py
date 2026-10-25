"""Discover models from the providers the user has actually authenticated.

Each provider is queried live with the user's resolved credential, so the result
reflects account- and plan-specific availability. A provider whose query fails
falls back to its static catalog entries and reports the failure, so the picker
still works offline. Native providers (codex, opencode-go) have no static
entries; on failure they contribute only the error.
"""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass

import httpx

from flow_harness.model.auth import ResolvedModelAuth, resolve_model_auth
from flow_harness.model.catalog import (
	ModelInfo,
	configured_providers,
	get_provider,
	list_models,
	model_supports_images,
)
from flow_harness.model.credentials import CredentialStore

MODEL_ENDPOINTS = {
	"openai": "https://api.openai.com/v1/models",
	"anthropic": "https://api.anthropic.com/v1/models",
	"gemini": "https://generativelanguage.googleapis.com/v1beta/models",
	"openrouter": "https://openrouter.ai/api/v1/models",
	"xai": "https://api.x.ai/v1/models",
	"groq": "https://api.groq.com/openai/v1/models",
	"deepseek": "https://api.deepseek.com/models",
	"mistral": "https://api.mistral.ai/v1/models",
	"cerebras": "https://api.cerebras.ai/v1/models",
}


@dataclass(frozen=True)
class ModelCatalog:
	models: list[ModelInfo]
	errors: list[str]


@functools.lru_cache(maxsize=256)
def context_window_for(model: str) -> int | None:
	"""Best-effort static context window for a model name — no network, no auth.
	Serves the UI's context meter; the loop's compaction math still uses the
	authenticated model's own limits. Cached: static per name, slow on first call."""
	try:
		prefix, _, rest = model.partition("/")
		if prefix == "codex":
			from flow_harness.model.providers.codex import static_context_window

			return static_context_window(rest)
		from flow_harness.model.litellm import litellm_limits

		return litellm_limits(model)[0]
	except Exception:
		return None


async def available_models(
	store: CredentialStore, *, client: httpx.AsyncClient | None = None
) -> ModelCatalog:
	"""Provider-qualified models available to configured authorizations."""
	provider_ids = sorted(spec.id for spec in configured_providers(store))
	owns_client = client is None
	client = client or httpx.AsyncClient(timeout=20)
	try:
		results = await asyncio.gather(
			*[_models_for_provider(provider_id, store, client) for provider_id in provider_ids],
			return_exceptions=True,
		)
	finally:
		if owns_client:
			await client.aclose()

	models: dict[str, ModelInfo] = {}
	errors: list[str] = []
	try:
		fallback = _by_provider(list_models(store))
	except Exception as e:  # a broken static catalog must not take live results down
		fallback = {}
		errors.append(f"static catalog: {e}")
	for provider_id, result in zip(provider_ids, results, strict=True):
		if isinstance(result, BaseException):
			errors.append(f"{provider_id}: {result}")
			result = fallback.get(provider_id, [])
		for info in result:
			models.setdefault(info.name, info)
	# custom endpoints declare their models up front — no discovery call to make
	for info in store.list():
		if info.type != "custom":
			continue
		credential = store.get_custom(info.provider_id)
		if credential is None:
			continue
		for name in credential.models:
			models.setdefault(name, ModelInfo(name=name, provider=info.provider_id))
	return ModelCatalog(models=[models[name] for name in sorted(models)], errors=errors)


def _by_provider(models: list[ModelInfo]) -> dict[str, list[ModelInfo]]:
	grouped: dict[str, list[ModelInfo]] = {}
	for info in models:
		grouped.setdefault(info.provider, []).append(info)
	return grouped


async def _models_for_provider(
	provider_id: str, store: CredentialStore, client: httpx.AsyncClient
) -> list[ModelInfo]:
	spec = get_provider(provider_id)
	if spec is None:
		return []
	prefix = spec.model_prefixes[0]
	auth = await resolve_model_auth(f"{prefix}/discovery", store, provider_id=provider_id)
	base = auth.base_url
	if provider_id == "codex":
		raw = await _codex_models(auth, base, client)
	elif provider_id == "opencode-go":
		from flow_harness.model.providers.opencode import BASE_URL

		raw = await _http_models(f"{(base or BASE_URL).rstrip('/')}/models", auth, client)
	else:
		endpoint = _model_endpoint(provider_id, base)
		raw = await _http_models(endpoint, auth, client, provider_id=provider_id)
	return [
		ModelInfo(
			name=(name := _qualify(prefix, model)),
			provider=provider_id,
			supports_images=model_supports_images(name),
			display_name=display_name,
		)
		for model, display_name in raw
		if model
	]


def _model_endpoint(provider_id: str, api_base: str | None) -> str:
	if api_base:
		base = api_base.rstrip("/")
		return base if base.endswith("/models") else f"{base}/models"
	return MODEL_ENDPOINTS[provider_id]


async def _http_models(
	url: str,
	auth: ResolvedModelAuth,
	client: httpx.AsyncClient,
	*,
	provider_id: str | None = None,
) -> list[tuple[str, str | None]]:
	headers = dict(auth.headers)
	if provider_id == "anthropic":
		headers.update({"x-api-key": auth.api_key or "", "anthropic-version": "2023-06-01"})
	elif provider_id == "gemini":
		headers["x-goog-api-key"] = auth.api_key or ""
	else:
		headers["Authorization"] = f"Bearer {auth.api_key}"
	response = await client.get(url, headers=headers)
	response.raise_for_status()
	return _model_rows(response.json(), provider_id)


async def _codex_models(
	auth: ResolvedModelAuth, api_base: str | None, client: httpx.AsyncClient
) -> list[tuple[str, str | None]]:
	from flow_harness.model.providers.codex import codex_client_version

	headers = {**auth.headers, "Authorization": f"Bearer {auth.api_key}"}
	response = await client.get(
		f"{(api_base or '').rstrip('/')}/codex/models",
		headers=headers,
		params={"client_version": codex_client_version()},
	)
	response.raise_for_status()
	return _model_rows(response.json(), "codex")


def _model_rows(data: object, provider_id: str | None = None) -> list[tuple[str, str | None]]:
	"""(model id, display name) for each listed model; a name with no space in it is an id, not
	a title (the id again, or another, as Mistral's dated one for a "-latest" alias), so none."""
	rows = []
	if isinstance(data, dict):
		rows = data.get("models", data.get("data", []))
	if not isinstance(rows, list):
		return []
	models = []
	for row in rows:
		if not isinstance(row, dict) or not _is_selectable(row, provider_id):
			continue
		raw = row.get("slug") or row.get("id") or row.get("name")
		if not raw:
			continue
		model = _clean_id(str(raw), provider_id)
		names = (row.get("display_name"), row.get("displayName"), row.get("name"))
		display_name = next(
			(name.strip() for name in names if isinstance(name, str) and " " in name.strip()),
			None,
		)
		models.append((model, display_name))
	return models


def _is_selectable(row: dict, provider_id: str | None) -> bool:
	if provider_id != "codex":
		return True
	return row.get("visibility", "list") == "list" and row.get("supported_in_api", True)


def _clean_id(model: str, provider_id: str | None) -> str:
	return model.removeprefix("models/") if provider_id == "gemini" else model


def _qualify(prefix: str, model: str) -> str:
	return model if model.startswith(f"{prefix}/") else f"{prefix}/{model}"
