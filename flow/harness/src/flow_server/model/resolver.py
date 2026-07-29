"""Resolve stored, explicit, or ambient credentials for one model run."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from flow_server.model.auth import AuthError, resolve_auth
from flow_server.model.catalog import get_provider, provider_for_model
from flow_server.model.credentials import ApiKeyCredential, CredentialStore, OAuthCredential


@dataclass(frozen=True)
class ResolvedModelAuth:
	api_key: str | None = None
	base_url: str | None = None
	headers: dict[str, str] = field(default_factory=dict)
	source: str | None = None
	provider_id: str | None = None


async def resolve_model_auth(
	model: str,
	store: CredentialStore,
	*,
	credential_id: str | None = None,
	refresh_access_token: str | None = None,
) -> ResolvedModelAuth:
	"""Resolve a stored credential first, then the provider's environment."""
	spec = get_provider(credential_id) if credential_id else provider_for_model(model)
	provider_id = credential_id or (spec.id if spec else None)

	if provider_id:
		credential = store.get(provider_id)
		if isinstance(credential, ApiKeyCredential):
			if spec and "api_key" not in spec.auth_methods:
				raise AuthError(f"Provider {provider_id!r} does not support stored API keys")
			return ResolvedModelAuth(
				api_key=credential.key,
				source="stored API key",
				provider_id=provider_id,
			)
		if isinstance(credential, OAuthCredential):
			if spec and "oauth" not in spec.auth_methods:
				raise AuthError(f"Provider {provider_id!r} does not support OAuth")
			runtime = await resolve_auth(
				store,
				provider_id,
				refresh_access_token=refresh_access_token,
			)
			return ResolvedModelAuth(
				api_key=runtime.token,
				base_url=runtime.base_url,
				headers=runtime.headers,
				source="OAuth",
				provider_id=provider_id,
			)

	if spec:
		for name in spec.api_key_envs:
			value = os.environ.get(name)
			if value:
				return ResolvedModelAuth(
					api_key=value,
					source=name,
					provider_id=spec.id,
				)
		methods = " or ".join(spec.auth_methods)
		raise AuthError(f"No {methods} credential for {spec.display_name}; run `flowd login {spec.id}`.")

	return ResolvedModelAuth(provider_id=provider_id)
