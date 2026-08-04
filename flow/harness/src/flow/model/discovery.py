"""Discover models from the providers the user has actually authenticated.

Each provider is queried live with the user's resolved credential, so the result
reflects account- and plan-specific availability. A provider whose query fails
falls back to its static catalog entries and reports the failure, so the picker
still works offline. Native providers (codex, opencode-go) have no static
entries; on failure they contribute only the error.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from dataclasses import dataclass

import httpx

from flow.model.auth import ResolvedModelAuth, resolve_model_auth
from flow.model.catalog import ModelInfo, configured_providers, get_provider, list_models
from flow.model.credentials import CredentialStore

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
		from flow.model.providers.opencode import BASE_URL

		raw = await _http_models(f"{(base or BASE_URL).rstrip('/')}/models", auth, client)
	else:
		endpoint = _model_endpoint(provider_id, base)
		raw = await _http_models(endpoint, auth, client, provider_id=provider_id)
	return [ModelInfo(name=_qualify(prefix, model), provider=provider_id) for model in raw if model]


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
) -> list[str]:
	headers = dict(auth.headers)
	if provider_id == "anthropic":
		headers.update({"x-api-key": auth.api_key or "", "anthropic-version": "2023-06-01"})
	elif provider_id == "gemini":
		headers["x-goog-api-key"] = auth.api_key or ""
	else:
		headers["Authorization"] = f"Bearer {auth.api_key}"
	response = await client.get(url, headers=headers)
	response.raise_for_status()
	return _model_ids(response.json(), provider_id)


async def _codex_models(
	auth: ResolvedModelAuth, api_base: str | None, client: httpx.AsyncClient
) -> list[str]:
	headers = {**auth.headers, "Authorization": f"Bearer {auth.api_key}"}
	response = await client.get(
		f"{(api_base or '').rstrip('/')}/codex/models",
		headers=headers,
		params={"client_version": _codex_client_version()},
	)
	response.raise_for_status()
	return _model_ids(response.json(), "codex")


def _codex_client_version() -> str:
	"""The backend gates its catalog by Codex protocol version, not this package version."""
	from flow.model.providers.codex import DEFAULT_CODEX_CLIENT_VERSION

	configured = os.environ.get("FLOW_CODEX_CLIENT_VERSION")
	if configured:
		return configured
	executable = shutil.which("codex")
	if executable:
		try:
			result = subprocess.run(
				[executable, "--version"],
				capture_output=True,
				check=True,
				text=True,
				timeout=5,
			)
			match = re.search(r"\b(\d+\.\d+\.\d+)\b", result.stdout)
			if match:
				return match.group(1)
		except (OSError, subprocess.SubprocessError):
			pass
	return DEFAULT_CODEX_CLIENT_VERSION


def _model_ids(data: object, provider_id: str | None = None) -> list[str]:
	rows = []
	if isinstance(data, dict):
		rows = data.get("models", data.get("data", []))
	if not isinstance(rows, list):
		return []
	return [
		_clean_id(str(row.get("slug") or row.get("id") or row.get("name")), provider_id)
		for row in rows
		if isinstance(row, dict)
		and (row.get("slug") or row.get("id") or row.get("name"))
		and _is_selectable(row, provider_id)
	]


def _is_selectable(row: dict, provider_id: str | None) -> bool:
	if provider_id != "codex":
		return True
	return row.get("visibility", "list") == "list" and row.get("supported_in_api", True)


def _clean_id(model: str, provider_id: str | None) -> str:
	return model.removeprefix("models/") if provider_id == "gemini" else model


def _qualify(prefix: str, model: str) -> str:
	return model if model.startswith(f"{prefix}/") else f"{prefix}/{model}"
