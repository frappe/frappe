"""Auth machinery: PKCE/JWT helpers, OAuth resolution with single-flight refresh,
and per-model credential resolution (stored key, OAuth grant, environment)."""

import asyncio
import base64
import hashlib
import json

import httpx
import pytest

from flow_server.model.auth import (
	AuthError,
	NotAuthenticated,
	account_id_from_tokens,
	decode_jwt_claims,
	generate_pkce,
	get_auth_provider,
	resolve_model_auth,
	resolve_oauth,
)
from flow_server.model.credentials import CredentialStore, OAuthCredential


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


def test_decode_jwt_claims_and_malformed():
	assert decode_jwt_claims(_jwt({"sub": "x"})) == {"sub": "x"}
	assert decode_jwt_claims("not-a-jwt") == {}
	assert decode_jwt_claims("") == {}


def test_account_id_extraction_variants():
	assert account_id_from_tokens(_jwt({"chatgpt_account_id": "top"}), None) == "top"
	nested = _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "nested"}})
	assert account_id_from_tokens(nested, None) == "nested"
	orgs = _jwt({"organizations": [{"id": "org1"}]})
	assert account_id_from_tokens(orgs, None) == "org1"
	# falls through id_token -> access_token
	assert account_id_from_tokens(None, _jwt({"chatgpt_account_id": "fromaccess"})) == "fromaccess"
	assert account_id_from_tokens(_jwt({}), _jwt({})) is None


# --- resolve_oauth (refresh-with-skew) ------------------------------------


async def test_resolve_oauth_requires_login(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	with pytest.raises(NotAuthenticated):
		await resolve_oauth(store, "codex")


async def test_resolve_oauth_skips_refresh_when_fresh(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set(
		"codex",
		OAuthCredential(access="fresh", refresh="r", expires=10_000_000, account_id="acc"),
	)

	def handler(request):  # must not be called
		raise AssertionError("refresh should not run for a fresh credential")

	async with _mock_client(handler) as client:
		auth = await resolve_oauth(store, "codex", client=client, now_ms=1_000)
	assert auth.token == "fresh"


async def test_resolve_oauth_refreshes_within_skew(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set("codex", OAuthCredential(access="stale", refresh="r0", expires=50_000))

	def handler(request):
		return httpx.Response(
			200,
			json={
				"access_token": _jwt({"chatgpt_account_id": "a"}),
				"refresh_token": "r1",
				"expires_in": 3600,
			},
		)

	# now_ms is within TOKEN_REFRESH_SKEW_MS (60_000) of expiry -> refresh
	async with _mock_client(handler) as client:
		auth = await resolve_oauth(store, "codex", client=client, now_ms=50_000)

	assert auth.token != "stale"
	assert store.get("codex").refresh == "r1"  # rotation persisted


async def test_concurrent_resolves_refresh_once(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set("codex", OAuthCredential(access="stale", refresh="r0", expires=1))
	refreshes = 0

	def handler(request):
		nonlocal refreshes
		refreshes += 1
		return httpx.Response(
			200,
			json={
				"access_token": _jwt({"chatgpt_account_id": "a"}),
				"refresh_token": "r1",
				"expires_in": 3600,
			},
		)

	async with _mock_client(handler) as client:
		await asyncio.gather(
			resolve_oauth(store, "codex", client=client, now_ms=50_000),
			resolve_oauth(store, "codex", client=client, now_ms=50_000),
		)
	assert refreshes == 1


async def test_provider_rejected_token_forces_one_refresh(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set(
		"codex",
		OAuthCredential(access="rejected", refresh="r0", expires=10_000_000, account_id="acc"),
	)
	provider = get_auth_provider("codex")
	refreshes = 0

	async def refresh(credential, **kwargs):
		nonlocal refreshes
		refreshes += 1
		return OAuthCredential(
			access="replacement",
			refresh="r1",
			expires=20_000_000,
			account_id="acc",
		)

	monkeypatch.setattr(provider, "refresh", refresh)

	auth = await resolve_oauth(store, "codex", now_ms=1_000, refresh_access_token="rejected")

	assert auth.token == "replacement"
	assert refreshes == 1
	assert store.get_oauth("codex").access == "replacement"


async def test_rejected_token_refresh_reuses_concurrently_replaced_token(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set(
		"codex",
		OAuthCredential(access="replacement", refresh="r1", expires=20_000_000, account_id="acc"),
	)
	provider = get_auth_provider("codex")

	async def refresh(credential, **kwargs):
		raise AssertionError("a token replaced by another request must not refresh again")

	monkeypatch.setattr(provider, "refresh", refresh)

	auth = await resolve_oauth(store, "codex", now_ms=1_000, refresh_access_token="rejected")

	assert auth.token == "replacement"


# --- model auth resolution ------------------------------------------------


async def test_model_auth_prefers_stored_key_over_environment(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set_api_key("anthropic", "stored")
	monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient")

	stored = await resolve_model_auth("anthropic/claude-sonnet", store)
	store.delete("anthropic")
	ambient = await resolve_model_auth("anthropic/claude-sonnet", store)

	assert (stored.api_key, stored.source) == ("stored", "stored API key")
	assert (ambient.api_key, ambient.source) == ("ambient", "ANTHROPIC_API_KEY")
	assert stored.refresh is None  # a static key has nothing to refresh


async def test_model_auth_missing_known_provider_has_clear_error(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	monkeypatch.delenv("OPENAI_API_KEY", raising=False)

	with pytest.raises(AuthError, match=r"flowd login openai"):
		await resolve_model_auth("openai/gpt-4.1", store)


async def test_model_auth_refuses_a_stored_key_for_an_oauth_only_provider(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set_api_key("codex", "not-a-bearer")

	with pytest.raises(AuthError, match="does not support stored API keys"):
		await resolve_model_auth("codex/gpt-test", store)


async def test_opencode_go_resolves_from_stored_key_and_env(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	monkeypatch.setenv("OPENCODE_API_KEY", "ambient-go")

	store.set_api_key("opencode-go", "stored-go")
	stored = await resolve_model_auth("opencode-go/grok-4.5", store)
	store.delete("opencode-go")
	ambient = await resolve_model_auth("opencode-go/grok-4.5", store)

	assert (stored.api_key, stored.provider_id) == ("stored-go", "opencode-go")
	assert (ambient.api_key, ambient.source) == ("ambient-go", "OPENCODE_API_KEY")


async def test_explicit_provider_id_supports_custom_key(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set_api_key("my-proxy", "proxy-key")

	resolved = await resolve_model_auth("openai-compatible/custom", store, provider_id="my-proxy")
	assert resolved.api_key == "proxy-key"
	assert resolved.provider_id == "my-proxy"


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
