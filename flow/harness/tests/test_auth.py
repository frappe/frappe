"""Auth machinery: PKCE/JWT helpers, OAuth resolution with single-flight refresh,
and per-model credential resolution (stored key, OAuth grant, environment)."""

import asyncio
import base64
import hashlib
import json

import httpx
import pytest

from flow_harness.model.auth import (
	AuthError,
	NotAuthenticated,
	account_id_from_tokens,
	decode_jwt_claims,
	generate_pkce,
	get_auth_provider,
	resolve_model_auth,
	resolve_oauth,
)
from flow_harness.model.credentials import CredentialStore, OAuthCredential


def _jwt(payload: dict) -> str:
	def seg(obj):
		raw = json.dumps(obj).encode()
		return base64.urlsafe_b64encode(raw).decode().rstrip("=")

	return f"{seg({'alg': 'none'})}.{seg(payload)}.sig"


def _mock_client(handler):
	return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- pkce + jwt -----------------------------------------------------------


def test_generate_pkce_is_s256():
	pkce = generate_pkce()
	expected = base64.urlsafe_b64encode(hashlib.sha256(pkce.verifier.encode()).digest())
	assert pkce.challenge == expected.decode().rstrip("=")
	assert "=" not in pkce.challenge


def test_account_id_from_jwt_claims():
	assert decode_jwt_claims(_jwt({"sub": "x"})) == {"sub": "x"}
	assert decode_jwt_claims("not-a-jwt") == {}
	assert decode_jwt_claims("") == {}

	assert account_id_from_tokens(_jwt({"chatgpt_account_id": "top"}), None) == "top"
	nested = _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "nested"}})
	assert account_id_from_tokens(nested, None) == "nested"
	orgs = _jwt({"organizations": [{"id": "org1"}]})
	assert account_id_from_tokens(orgs, None) == "org1"
	# falls through id_token -> access_token
	assert account_id_from_tokens(None, _jwt({"chatgpt_account_id": "fromaccess"})) == "fromaccess"
	assert account_id_from_tokens(_jwt({}), _jwt({})) is None


# --- resolve_oauth (refresh-with-skew) ------------------------------------


async def test_resolve_oauth_refreshes_a_stale_or_rejected_token_once(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	with pytest.raises(NotAuthenticated):
		await resolve_oauth(store, "codex")

	store.set("codex", OAuthCredential(access="fresh", refresh="r0", expires=10_000_000, account_id="acc"))
	refreshes = 0

	def handler(request):
		nonlocal refreshes
		refreshes += 1
		return httpx.Response(
			200,
			json={
				"access_token": _jwt({"chatgpt_account_id": "a", "n": refreshes}),
				"refresh_token": f"r{refreshes}",
				"expires_in": 3600,
			},
		)

	async with _mock_client(handler) as client:
		assert (await resolve_oauth(store, "codex", client=client, now_ms=1_000)).token == "fresh"
		assert refreshes == 0

		# within TOKEN_REFRESH_SKEW_MS (60_000) of expiry; concurrent callers share one refresh
		stale = await asyncio.gather(
			resolve_oauth(store, "codex", client=client, now_ms=9_950_000),
			resolve_oauth(store, "codex", client=client, now_ms=9_950_000),
		)
		assert refreshes == 1
		assert stale[0].token == stale[1].token != "fresh"
		assert store.get("codex").refresh == "r1"  # rotation persisted

		# a token the provider rejected is refreshed before it expires
		rejected = stale[0].token
		auth = await resolve_oauth(store, "codex", client=client, now_ms=1_000, refresh_access_token=rejected)
		assert refreshes == 2
		assert store.get_oauth("codex").access == auth.token != rejected

		# once another request replaced it, the newer token is reused
		again = await resolve_oauth(
			store, "codex", client=client, now_ms=1_000, refresh_access_token=rejected
		)
		assert (again.token, refreshes) == (auth.token, 2)


# --- model auth resolution ------------------------------------------------


async def test_model_auth_prefers_a_stored_key_over_the_environment(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	for model, provider, env in (
		("anthropic/claude-sonnet", "anthropic", "ANTHROPIC_API_KEY"),
		("opencode-go/grok-4.5", "opencode-go", "OPENCODE_API_KEY"),
	):
		monkeypatch.setenv(env, "ambient")
		store.set_api_key(provider, "stored")
		stored = await resolve_model_auth(model, store)
		store.delete(provider)
		ambient = await resolve_model_auth(model, store)

		assert (stored.api_key, stored.source, stored.provider_id) == ("stored", "stored API key", provider)
		assert (ambient.api_key, ambient.source, ambient.provider_id) == ("ambient", env, provider)
		assert stored.refresh is None  # a static key has nothing to refresh

	# an explicit provider id finds a key stored under a custom id
	store.set_api_key("my-proxy", "proxy-key")
	resolved = await resolve_model_auth("openai-compatible/custom", store, provider_id="my-proxy")
	assert (resolved.api_key, resolved.provider_id) == ("proxy-key", "my-proxy")


async def test_model_auth_refuses_missing_or_unsupported_credentials(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	monkeypatch.delenv("OPENAI_API_KEY", raising=False)
	store.set_api_key("codex", "not-a-bearer")

	for model, match in (
		("openai/gpt-4.1", r"flow login openai"),
		("codex/gpt-test", "does not support stored API keys"),  # OAuth only
	):
		with pytest.raises(AuthError, match=match):
			await resolve_model_auth(model, store)


async def test_model_auth_for_oauth_carries_runtime_auth_and_a_refresh_hook(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set(
		"codex",
		OAuthCredential(access="live", refresh="r0", expires=10_000_000_000_000, account_id="acc"),
	)

	resolved = await resolve_model_auth("codex/gpt-test", store)

	assert (resolved.api_key, resolved.source) == ("live", "OAuth")
	assert resolved.base_url == "https://chatgpt.com/backend-api"
	assert resolved.headers["chatgpt-account-id"] == "acc"
	assert resolved.refresh is not None

	async def refresh(credential, **kwargs):
		return OAuthCredential(access="fresh", refresh="r1", expires=20_000_000_000_000, account_id="acc")

	monkeypatch.setattr(get_auth_provider("codex"), "refresh", refresh)
	auth = await resolved.refresh("live")  # the provider rejected the live token

	assert auth.token == "fresh"
	assert store.get_oauth("codex").access == "fresh"
