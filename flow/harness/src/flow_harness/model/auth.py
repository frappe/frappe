"""How a model run gets its credentials.

Two layers live here. The OAuth core is the provider-neutral subscription machinery:
an `AuthProvider` owns one provider's login (`authorize_url` + `exchange`), token
`refresh`, and request-time `runtime_auth` (bearer + headers + base_url), and
`resolve_oauth` turns a stored credential into runtime auth — refreshing it under a
single-flight lock when it is stale or was rejected by the provider.

On top sits `resolve_model_auth`, the request-time entry point: given a model name it
finds the credential — stored key, stored OAuth grant, or the provider's environment
variable — and returns everything `get_model` needs, including a `refresh` hook an
OAuth-backed adapter passes to `run_with_retries` for one-shot recovery from a
rejected token.
"""

from __future__ import annotations

import abc
import asyncio
import base64
import hashlib
import json
import os
import secrets
import time
import weakref
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from flow_harness.model.catalog import get_provider, provider_for_model
from flow_harness.model.credentials import (
	ApiKeyCredential,
	CredentialStore,
	CustomProviderCredential,
	OAuthCredential,
)

TOKEN_REFRESH_SKEW_MS = 60_000  # refresh this long before actual expiry


class AuthError(Exception):
	pass


class NotAuthenticated(AuthError):
	"""No stored credential for the provider — the user must log in first."""


# --- PKCE + JWT helpers ---------------------------------------------------


@dataclass
class Pkce:
	verifier: str
	challenge: str


def generate_pkce() -> Pkce:
	verifier = secrets.token_urlsafe(64)
	digest = hashlib.sha256(verifier.encode("ascii")).digest()
	challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
	return Pkce(verifier=verifier, challenge=challenge)


def new_state() -> str:
	return secrets.token_hex(16)


def decode_jwt_claims(token: str) -> dict:
	"""Read (NOT verify) a JWT's payload claims. We only pull routing metadata such as
	the account id from a token the OAuth endpoint just handed us over TLS; the API
	re-validates it against the bearer, so this is not a trust boundary."""
	try:
		payload = token.split(".")[1]
		payload += "=" * (-len(payload) % 4)
		return json.loads(base64.urlsafe_b64decode(payload))
	except (ValueError, IndexError, TypeError):
		return {}


# --- runtime auth + provider interface ------------------------------------


@dataclass
class RuntimeAuth:
	token: str
	account_id: str | None = None
	base_url: str | None = None
	headers: dict[str, str] = field(default_factory=dict)


class AuthProvider(abc.ABC):
	name: str

	@abc.abstractmethod
	def authorize_url(self, *, challenge: str, state: str) -> str:
		"""The provider's browser authorize URL for a PKCE login."""

	@abc.abstractmethod
	async def exchange(
		self,
		code: str,
		verifier: str,
		*,
		client: httpx.AsyncClient | None = None,
		now_ms: int | None = None,
	) -> OAuthCredential:
		"""Trade an authorization code for a credential."""

	@abc.abstractmethod
	async def refresh(
		self,
		credential: OAuthCredential,
		*,
		client: httpx.AsyncClient | None = None,
		now_ms: int | None = None,
	) -> OAuthCredential:
		"""Exchange the refresh token for a fresh credential."""

	@abc.abstractmethod
	def runtime_auth(self, credential: OAuthCredential) -> RuntimeAuth:
		"""Build the bearer + headers + base_url for a request."""


_PROVIDERS: dict[str, AuthProvider] = {}
_REFRESH_LOCKS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def register_auth_provider(provider: AuthProvider) -> None:
	_PROVIDERS[provider.name] = provider


def get_auth_provider(name: str) -> AuthProvider:
	try:
		return _PROVIDERS[name]
	except KeyError:
		raise AuthError(f"Unknown auth provider {name!r}") from None


async def resolve_oauth(
	store: CredentialStore,
	name: str,
	*,
	client: httpx.AsyncClient | None = None,
	now_ms: int | None = None,
	refresh_access_token: str | None = None,
) -> RuntimeAuth:
	"""Load OAuth runtime auth, refreshing a stale or provider-rejected access token.

	``refresh_access_token`` is the token rejected by the provider. If another
	concurrent request already replaced it, that newer credential is reused instead
	of consuming the refresh token twice.
	"""
	provider = get_auth_provider(name)
	credential = store.get_oauth(name)
	if credential is None:
		raise NotAuthenticated(f"Not logged in to {name!r}; run login first.")
	now = now_ms if now_ms is not None else _now_ms()
	if refresh_access_token is not None and credential.access != refresh_access_token:
		return provider.runtime_auth(credential)
	if refresh_access_token is None and now < credential.expires - TOKEN_REFRESH_SKEW_MS:
		return provider.runtime_auth(credential)

	# Several sessions can notice the same stale/rejected token at once. Re-read
	# under a provider lock so only one refresh consumes a rotating refresh token.
	async with _refresh_lock(name):
		credential = store.get_oauth(name)
		if credential is None:
			raise NotAuthenticated(f"Not logged in to {name!r}; run login first.")
		now = now_ms if now_ms is not None else _now_ms()
		if refresh_access_token is not None and credential.access != refresh_access_token:
			return provider.runtime_auth(credential)
		if refresh_access_token is not None or now >= credential.expires - TOKEN_REFRESH_SKEW_MS:
			credential = await provider.refresh(credential, client=client)
			store.set_oauth(name, credential)
	return provider.runtime_auth(credential)


def _refresh_lock(name: str) -> asyncio.Lock:
	loop = asyncio.get_running_loop()
	locks = _REFRESH_LOCKS.setdefault(loop, {})
	return locks.setdefault(name, asyncio.Lock())


# --- shared token-endpoint call -------------------------------------------


async def post_token(url: str, data: dict, client: httpx.AsyncClient | None = None) -> dict:
	"""POST a form-encoded body to an OAuth token endpoint and return the JSON."""
	owns = client is None
	client = client or httpx.AsyncClient(timeout=30)
	try:
		response = await client.post(url, data=data)
		response.raise_for_status()
		return response.json()
	finally:
		if owns:
			await client.aclose()


def account_id_from_tokens(id_token: str | None, access_token: str | None) -> str | None:
	"""Extract an OpenAI/ChatGPT account id from whichever token carries it."""
	for token in (id_token, access_token):
		if not token:
			continue
		claims = decode_jwt_claims(token)
		nested = claims.get("https://api.openai.com/auth")
		account_id = claims.get("chatgpt_account_id")
		if not account_id and isinstance(nested, dict):
			account_id = nested.get("chatgpt_account_id")
		if not account_id:
			account_id = _first_org_id(claims)
		if account_id:
			return account_id
	return None


def _first_org_id(claims: dict) -> str | None:
	orgs = claims.get("organizations")
	if isinstance(orgs, list) and orgs and isinstance(orgs[0], dict):
		return orgs[0].get("id")
	return None


def _now_ms() -> int:
	return int(time.time() * 1000)


# --- request-time resolution for one model run ----------------------------

# Trades the provider-rejected access token for fresh runtime auth.
RefreshAuth = Callable[[str], Awaitable[RuntimeAuth]]


@dataclass(frozen=True)
class ResolvedModelAuth:
	api_key: str | None = None
	base_url: str | None = None
	headers: dict[str, str] = field(default_factory=dict)
	source: str | None = None
	provider_id: str | None = None
	# Set only for an OAuth credential; the adapter runs it via `run_with_retries`.
	refresh: RefreshAuth | None = None


async def resolve_model_auth(
	model: str,
	store: CredentialStore,
	*,
	provider_id: str | None = None,
	api_key: str | None = None,
	api_base: str | None = None,
) -> ResolvedModelAuth:
	"""Inline credentials win; then a stored credential; then the provider's environment."""
	if api_key or api_base:
		return ResolvedModelAuth(api_key=api_key, base_url=api_base, source="inline credentials")
	# custom endpoints first: they have no ProviderSpec, and base_url is the only route to the model
	custom = _custom_credential_for_model(store, model, provider_id)
	if custom is not None:
		custom_id, credential = custom
		return ResolvedModelAuth(
			api_key=credential.api_key,
			base_url=credential.base_url,
			source="Custom endpoint",
			provider_id=custom_id,
		)

	spec = get_provider(provider_id) if provider_id else provider_for_model(model)
	provider_id = provider_id or (spec.id if spec else None)

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
			runtime = await resolve_oauth(store, provider_id)

			async def refresh(rejected_token: str) -> RuntimeAuth:
				return await resolve_oauth(store, provider_id, refresh_access_token=rejected_token)

			return ResolvedModelAuth(
				api_key=runtime.token,
				base_url=runtime.base_url,
				headers=runtime.headers,
				source="OAuth",
				provider_id=provider_id,
				refresh=refresh,
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
		raise AuthError(f"No {methods} credential for {spec.display_name}; run `flow login {spec.id}`.")

	return ResolvedModelAuth(provider_id=provider_id)


def _custom_credential_for_model(
	store: CredentialStore,
	model: str,
	provider_id: str | None,
) -> tuple[str, CustomProviderCredential] | None:
	"""The pinned endpoint, else the first one listing this model."""
	if provider_id:
		credential = store.get_custom(provider_id)
		return (provider_id, credential) if credential is not None else None
	for info in store.list():
		if info.type != "custom":
			continue
		credential = store.get_custom(info.provider_id)
		if credential is not None and model in credential.models:
			return info.provider_id, credential
	return None
