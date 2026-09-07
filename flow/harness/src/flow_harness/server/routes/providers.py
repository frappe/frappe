"""Model catalog and provider credential routes: API keys, custom endpoints, OAuth."""

from __future__ import annotations

from dataclasses import asdict
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from flow_harness.model.auth import AuthError
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.discovery import available_models
from flow_harness.server.policy import ServerPolicy, gate
from flow_harness.server.utils.provider_auth import (
	OAuthCoordinator,
	create_custom_provider,
	provider_catalog,
	require_provider,
	update_custom_provider,
)


class ApiKeyRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	key: str = Field(min_length=1)


class CustomProviderRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	name: str = Field(min_length=1, max_length=60)
	base_url: str = Field(min_length=1, max_length=300)
	models: list[str] = Field(min_length=1, max_length=50)
	api_key: str | None = None


class OAuthCompleteRequest(BaseModel):
	model_config = ConfigDict(extra="forbid")

	callback_url: str = Field(min_length=1)


def create_providers_router(
	credential_store: CredentialStore, oauth: OAuthCoordinator, *, policy: ServerPolicy | None = None
) -> APIRouter:
	policy = policy or ServerPolicy()
	# one gate for the whole group: a deployed client brings its own models and keys
	router = APIRouter(dependencies=gate(policy.providers_api))

	@router.get("/models")
	async def models():
		catalog = await available_models(credential_store)
		return {"models": [asdict(model) for model in catalog.models], "errors": catalog.errors}

	@router.get("/providers")
	async def providers():
		return {"providers": provider_catalog(credential_store)}

	@router.post("/providers/custom")
	async def save_custom_provider(req: CustomProviderRequest):
		"""Register an OpenAI-compatible endpoint (Ollama, LM Studio, a gateway)."""
		name, base_url, models, api_key = _normalized_custom_provider_request(req)
		row = create_custom_provider(
			credential_store,
			name=name,
			base_url=base_url,
			models=models,
			api_key=api_key,
		)
		return {"provider": row}

	@router.put("/providers/custom/{provider_id}")
	async def edit_custom_provider(provider_id: str, req: CustomProviderRequest):
		"""Rewrite a stored endpoint in place; a blank api_key keeps the saved one."""
		name, base_url, models, api_key = _normalized_custom_provider_request(req)
		row = update_custom_provider(
			credential_store,
			provider_id,
			name=name,
			base_url=base_url,
			models=models,
			api_key=api_key,
		)
		if row is None:
			raise HTTPException(status_code=404, detail="no such custom endpoint")
		return {"provider": row}

	@router.post("/providers/{provider_id}/api-key")
	async def save_provider_api_key(provider_id: str, req: ApiKeyRequest):
		provider = require_provider(provider_id)
		if "api_key" not in provider.auth_methods:
			raise AuthError(f"{provider.display_name} does not take an API key")
		credential_store.set_api_key(provider_id, req.key)
		return {"status": "saved"}

	@router.delete("/providers/{provider_id}")
	async def remove_provider_credential(provider_id: str):
		# custom endpoints have no ProviderSpec; a stored credential proves the id
		if credential_store.get(provider_id) is None:
			require_provider(provider_id)  # unknown id → 400, known-but-unset → 404
			raise HTTPException(status_code=404, detail="no stored credential")
		credential_store.delete(provider_id)
		return {"status": "removed"}

	@router.post("/providers/{provider_id}/oauth/start")
	async def start_provider_oauth(provider_id: str):
		return await oauth.start(provider_id)

	@router.get("/providers/{provider_id}/oauth/status")
	async def provider_oauth_status(provider_id: str):
		require_provider(provider_id)
		return oauth.status(provider_id)

	@router.post("/providers/{provider_id}/oauth/complete")
	async def complete_provider_oauth(provider_id: str, req: OAuthCompleteRequest):
		return await oauth.complete(provider_id, req.callback_url)

	return router


def _normalized_custom_provider_request(
	req: CustomProviderRequest,
) -> tuple[str, str, tuple[str, ...], str | None]:
	base_url = req.base_url.strip().rstrip("/")
	parsed = urlsplit(base_url)
	if parsed.scheme not in ("http", "https") or not parsed.netloc:
		raise HTTPException(status_code=422, detail="Base URL must be an absolute http(s) URL")
	if parsed.username or parsed.password:
		raise HTTPException(status_code=422, detail="Base URL must not contain credentials")
	models = tuple(dict.fromkeys(m.strip() for m in req.models if m.strip()))
	if not models:
		raise HTTPException(status_code=422, detail="Add at least one model id")
	# the prefix is what routes a model back to this endpoint later
	if any("/" not in m for m in models):
		raise HTTPException(
			status_code=422,
			detail="Model ids need a provider prefix, for example ollama/llama3.2",
		)
	name = req.name.strip()
	if not name:
		raise HTTPException(status_code=422, detail="Name must not be empty")
	return name, base_url, models, (req.api_key or "").strip() or None
