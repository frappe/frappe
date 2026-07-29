import asyncio
import base64
import hashlib
import json
import os

import httpx
import pytest

from flow_server.model.auth import (
	AuthError,
	NotAuthenticated,
	account_id_from_tokens,
	decode_jwt_claims,
	generate_pkce,
	get_auth_provider,
	resolve_auth,
)
from flow_server.model.credentials import ApiKeyCredential, CredentialStore, OAuthCredential
from flow_server.model.providers.codex import CLIENT_ID
from flow_server.model.resolver import resolve_model_auth


def _jwt(payload: dict) -> str:
	def seg(obj):
		raw = json.dumps(obj).encode()
		return base64.urlsafe_b64encode(raw).decode().rstrip("=")

	return f"{seg({'alg': 'none'})}.{seg(payload)}.sig"


def _mock_client(handler):
	return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- credential store -----------------------------------------------------


def test_credential_store_roundtrip(tmp_path):
	store = CredentialStore(str(tmp_path / "creds.json"))
	assert store.get("codex") is None
	store.set("codex", OAuthCredential(access="a", refresh="r", expires=123, account_id="acc"))
	got = store.get("codex")
	assert got == OAuthCredential(access="a", refresh="r", expires=123, account_id="acc")
	store.delete("codex")
	assert store.get("codex") is None


def test_credential_store_api_key_and_metadata(tmp_path):
	store = CredentialStore(str(tmp_path / "creds.json"))
	store.set_api_key("anthropic", " sk-test ")

	assert store.get("anthropic") == ApiKeyCredential(key="sk-test")
	assert store.get_api_key("anthropic").key == "sk-test"
	assert store.get_oauth("anthropic") is None
	assert store.list()[0].provider_id == "anthropic"
	assert store.list()[0].type == "api_key"


def test_credential_store_file_is_0600(tmp_path):
	path = tmp_path / "sub" / "creds.json"
	store = CredentialStore(str(path))
	store.set("codex", OAuthCredential(access="a", refresh="r", expires=1))
	assert oct(os.stat(path).st_mode & 0o777) == "0o600"
	assert oct(os.stat(path.parent).st_mode & 0o777) == "0o700"


def test_credential_store_repairs_file_permissions(tmp_path):
	path = tmp_path / "creds.json"
	path.write_text('{"openai":{"type":"api_key","key":"secret"}}')
	path.chmod(0o644)

	assert CredentialStore(str(path)).get_api_key("openai").key == "secret"
	assert oct(os.stat(path).st_mode & 0o777) == "0o600"


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


# --- codex auth provider --------------------------------------------------


def test_codex_authorize_url():
	url = get_auth_provider("codex").authorize_url(challenge="CH", state="ST")
	assert url.startswith("https://auth.openai.com/oauth/authorize?")
	for fragment in (
		f"client_id={CLIENT_ID}",
		"code_challenge=CH",
		"code_challenge_method=S256",
		"state=ST",
		"code_challenge_method=S256",
		"id_token_add_organizations=true",
	):
		assert fragment in url


async def test_codex_exchange_builds_credential():
	captured = {}

	def handler(request):
		captured["body"] = request.content.decode()
		return httpx.Response(
			200,
			json={
				"access_token": _jwt({"chatgpt_account_id": "acc-1"}),
				"refresh_token": "refresh-1",
				"expires_in": 3600,
			},
		)

	async with _mock_client(handler) as client:
		cred = await get_auth_provider("codex").exchange(
			"the-code", "the-verifier", client=client, now_ms=1_000
		)

	assert "grant_type=authorization_code" in captured["body"]
	assert "code=the-code" in captured["body"]
	assert "code_verifier=the-verifier" in captured["body"]
	assert cred.refresh == "refresh-1"
	assert cred.account_id == "acc-1"
	assert cred.expires == 1_000 + 3600 * 1000


async def test_codex_refresh_keeps_old_refresh_when_absent():
	def handler(request):
		assert "grant_type=refresh_token" in request.content.decode()
		return httpx.Response(200, json={"access_token": _jwt({}), "expires_in": 100})

	old = OAuthCredential(access="old", refresh="keep-me", expires=0, account_id="acc")
	async with _mock_client(handler) as client:
		cred = await get_auth_provider("codex").refresh(old, client=client, now_ms=0)
	assert cred.refresh == "keep-me"


def test_codex_runtime_auth_headers():
	auth = get_auth_provider("codex").runtime_auth(
		OAuthCredential(access="tok", refresh="r", expires=0, account_id="acc-9")
	)
	assert auth.token == "tok"
	assert auth.base_url == "https://chatgpt.com/backend-api"
	assert auth.headers["chatgpt-account-id"] == "acc-9"
	assert auth.headers["originator"] == "flow_server"


# --- resolver (refresh-with-skew) -----------------------------------------


async def test_resolve_auth_requires_login(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	with pytest.raises(NotAuthenticated):
		await resolve_auth(store, "codex")


async def test_resolve_auth_skips_refresh_when_fresh(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set(
		"codex",
		OAuthCredential(access="fresh", refresh="r", expires=10_000_000, account_id="acc"),
	)

	def handler(request):  # must not be called
		raise AssertionError("refresh should not run for a fresh credential")

	async with _mock_client(handler) as client:
		auth = await resolve_auth(store, "codex", client=client, now_ms=1_000)
	assert auth.token == "fresh"


async def test_resolve_auth_refreshes_within_skew(tmp_path):
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
		auth = await resolve_auth(store, "codex", client=client, now_ms=50_000)

	assert auth.token != "stale"
	assert store.get("codex").refresh == "r1"  # rotation persisted


async def test_concurrent_resolve_refreshes_once(tmp_path):
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
			resolve_auth(store, "codex", client=client, now_ms=50_000),
			resolve_auth(store, "codex", client=client, now_ms=50_000),
		)
	assert refreshes == 1


async def test_provider_rejected_oauth_token_forces_one_refresh(tmp_path, monkeypatch):
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

	auth = await resolve_auth(
		store,
		"codex",
		now_ms=1_000,
		refresh_access_token="rejected",
	)

	assert auth.token == "replacement"
	assert refreshes == 1
	assert store.get_oauth("codex").access == "replacement"


async def test_rejected_oauth_refresh_reuses_concurrently_replaced_token(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set(
		"codex",
		OAuthCredential(access="replacement", refresh="r1", expires=20_000_000, account_id="acc"),
	)
	provider = get_auth_provider("codex")

	async def refresh(credential, **kwargs):
		raise AssertionError("a token replaced by another request must not refresh again")

	monkeypatch.setattr(provider, "refresh", refresh)

	auth = await resolve_auth(
		store,
		"codex",
		now_ms=1_000,
		refresh_access_token="rejected",
	)

	assert auth.token == "replacement"


def test_codex_runtime_auth_requires_account_id():
	with pytest.raises(AuthError, match="account id"):
		get_auth_provider("codex").runtime_auth(OAuthCredential(access="tok", refresh="r", expires=1))


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


async def test_model_auth_missing_known_provider_has_clear_error(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	monkeypatch.delenv("OPENAI_API_KEY", raising=False)

	with pytest.raises(AuthError, match=r"flowd login openai"):
		await resolve_model_auth("openai/gpt-4.1", store)


async def test_opencode_go_resolves_from_stored_key_and_env(tmp_path, monkeypatch):
	store = CredentialStore(str(tmp_path / "c.json"))
	monkeypatch.setenv("OPENCODE_API_KEY", "ambient-go")

	store.set_api_key("opencode-go", "stored-go")
	stored = await resolve_model_auth("opencode-go/grok-4.5", store)
	store.delete("opencode-go")
	ambient = await resolve_model_auth("opencode-go/grok-4.5", store)

	assert (stored.api_key, stored.provider_id) == ("stored-go", "opencode-go")
	assert (ambient.api_key, ambient.source) == ("ambient-go", "OPENCODE_API_KEY")


async def test_explicit_credential_id_supports_custom_key(tmp_path):
	store = CredentialStore(str(tmp_path / "c.json"))
	store.set_api_key("my-proxy", "proxy-key")

	resolved = await resolve_model_auth("openai-compatible/custom", store, credential_id="my-proxy")
	assert resolved.api_key == "proxy-key"
	assert resolved.provider_id == "my-proxy"
