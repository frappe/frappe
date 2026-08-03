"""Live model discovery: per-provider endpoints, fallback, and codex versioning."""

import httpx
import litellm
import pytest

from flow.model.catalog import PROVIDERS, ModelInfo
from flow.model.credentials import CredentialStore, OAuthCredential
from flow.model.discovery import (
	DEFAULT_CODEX_CLIENT_VERSION,
	_codex_client_version,
	available_models,
)


@pytest.fixture
def bare_env(monkeypatch):
	"""No provider API key leaks in from the developer's environment."""
	for provider in PROVIDERS:
		for name in provider.api_key_envs:
			monkeypatch.delenv(name, raising=False)
	monkeypatch.setattr(litellm, "model_cost", {})


def _store(tmp_path) -> CredentialStore:
	return CredentialStore(str(tmp_path / "credentials.json"))


def _client(handler) -> httpx.AsyncClient:
	return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_nothing_configured_discovers_nothing(tmp_path, bare_env):
	def handler(request):
		raise AssertionError("no provider is configured; nothing may be queried")

	catalog = await available_models(_store(tmp_path), client=_client(handler))
	assert catalog == type(catalog)(models=[], errors=[])


async def test_opencode_go_models_come_from_the_gateway(tmp_path, bare_env, monkeypatch):
	monkeypatch.setenv("OPENCODE_API_KEY", "sk-go")
	seen = {}

	def handler(request):
		seen["url"] = str(request.url)
		seen["auth"] = request.headers.get("Authorization")
		return httpx.Response(200, json={"data": [{"id": "kimi-k3"}, {"id": "grok-4.5"}]})

	catalog = await available_models(_store(tmp_path), client=_client(handler))
	assert seen["url"] == "https://opencode.ai/zen/go/v1/models"
	assert seen["auth"] == "Bearer sk-go"
	assert catalog.models == [
		ModelInfo(name="opencode-go/grok-4.5", provider="opencode-go"),
		ModelInfo(name="opencode-go/kimi-k3", provider="opencode-go"),
	]
	assert catalog.errors == []


async def test_provider_specific_headers_and_id_cleaning(tmp_path, bare_env):
	store = _store(tmp_path)
	store.set_api_key("anthropic", "sk-ant")
	store.set_api_key("gemini", "sk-gem")

	def handler(request):
		if "anthropic" in request.url.host:
			assert request.headers["x-api-key"] == "sk-ant"
			return httpx.Response(200, json={"data": [{"id": "claude-sonnet-4"}]})
		assert request.headers["x-goog-api-key"] == "sk-gem"
		return httpx.Response(200, json={"models": [{"name": "models/gemini-2.0-flash"}]})

	catalog = await available_models(store, client=_client(handler))
	assert catalog.models == [
		ModelInfo(name="anthropic/claude-sonnet-4", provider="anthropic"),
		ModelInfo(name="gemini/gemini-2.0-flash", provider="gemini"),
	]


async def test_codex_queries_with_client_version_and_filters_unlisted(tmp_path, bare_env, monkeypatch):
	monkeypatch.setenv("FLOW_CODEX_CLIENT_VERSION", "9.9.9")
	store = _store(tmp_path)
	store.set_oauth(
		"codex",
		OAuthCredential(access="tok", refresh="r", expires=2**62, account_id="acc"),
	)

	def handler(request):
		assert request.url.path.endswith("/codex/models")
		assert request.url.params["client_version"] == "9.9.9"
		assert request.headers["Authorization"] == "Bearer tok"
		assert request.headers["chatgpt-account-id"] == "acc"
		return httpx.Response(
			200,
			json={
				"models": [
					{"slug": "gpt-5-codex"},
					{"slug": "gpt-5-internal", "visibility": "hidden"},
					{"slug": "gpt-5-web", "supported_in_api": False},
				]
			},
		)

	catalog = await available_models(store, client=_client(handler))
	assert catalog.models == [ModelInfo(name="codex/gpt-5-codex", provider="codex")]


async def test_failed_provider_falls_back_to_static_catalog(tmp_path, bare_env, monkeypatch):
	monkeypatch.setenv("OPENCODE_API_KEY", "sk-go")
	monkeypatch.setenv("OPENAI_API_KEY", "sk-oai")
	monkeypatch.setattr(
		litellm,
		"model_cost",
		{"gpt-4o": {"mode": "chat", "supports_function_calling": True, "litellm_provider": "openai"}},
	)

	def handler(request):
		if request.url.host == "api.openai.com":
			return httpx.Response(500, text="boom")
		return httpx.Response(200, json={"data": [{"id": "kimi-k3"}]})

	catalog = await available_models(_store(tmp_path), client=_client(handler))
	assert catalog.models == [
		ModelInfo(name="openai/gpt-4o", provider="openai"),
		ModelInfo(name="opencode-go/kimi-k3", provider="opencode-go"),
	]
	assert len(catalog.errors) == 1 and catalog.errors[0].startswith("openai:")


def test_codex_client_version_prefers_env_then_binary_then_default(monkeypatch):
	monkeypatch.setenv("FLOW_CODEX_CLIENT_VERSION", "1.2.3")
	assert _codex_client_version() == "1.2.3"

	monkeypatch.delenv("FLOW_CODEX_CLIENT_VERSION")
	monkeypatch.setattr("shutil.which", lambda name: None)
	assert _codex_client_version() == DEFAULT_CODEX_CLIENT_VERSION
