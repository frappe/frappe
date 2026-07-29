"""OAuth/subscription auth core — the provider-neutral machinery a native provider
uses when its credential is not a static API key.

An `AuthProvider` owns one provider's login (`authorize_url` + `exchange`), token
`refresh`, and request-time `runtime_auth` (bearer + headers + base_url). Providers
register by name; `resolve_auth` is the request-time entry point a native
model calls — it loads the stored credential, refreshes it if within the expiry skew,
persists any rotation, and returns the `RuntimeAuth` for the call. The interactive login
UX supplies the authorization code; this module owns the provider protocol.
"""

from __future__ import annotations

import abc
import asyncio
import base64
import hashlib
import json
import secrets
import time
import weakref
from dataclasses import dataclass, field

import httpx

from flow_server.model.credentials import CredentialStore, OAuthCredential

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


async def resolve_auth(
	store: CredentialStore,
	name: str,
	*,
	client: httpx.AsyncClient | None = None,
	now_ms: int | None = None,
	refresh_access_token: str | None = None,
) -> RuntimeAuth:
	"""Load runtime auth, refreshing a stale or provider-rejected access token.

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
