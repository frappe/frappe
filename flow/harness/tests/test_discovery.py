"""Live model discovery: per-provider endpoints, fallback, and codex versioning."""

import httpx
import litellm
import pytest

from flow_harness.model.catalog import PROVIDERS, ModelInfo
from flow_harness.model.credentials import CredentialStore, OAuthCredential
from flow_harness.model.discovery import available_models


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


async def test_each_provider_is_queried_its_own_way(tmp_path, bare_env, monkeypatch):
	"""Each provider's endpoint, auth headers, id cleanup and display names; a provider whose
	query fails falls back to its static catalog entries and reports the failure."""
	monkeypatch.setenv("OPENCODE_API_KEY", "sk-go")
	monkeypatch.setenv("OPENAI_API_KEY", "sk-oai")
	monkeypatch.setenv("FLOW_CODEX_CLIENT_VERSION", "9.9.9")
	monkeypatch.setattr(
		litellm,
		"model_cost",
		{
			"gpt-4o": {
				"mode": "chat",
				"supports_function_calling": True,
				"supports_vision": True,
				"litellm_provider": "openai",
			}
		},
	)
	store = _store(tmp_path)
	store.set_api_key("anthropic", "sk-ant")
	store.set_api_key("gemini", "sk-gem")
	store.set_oauth(
		"codex",
		OAuthCredential(access="tok", refresh="r", expires=2**62, account_id="acc"),
	)

	def handler(request):
		url, headers = request.url, request.headers
		if url.host == "api.openai.com":
			return httpx.Response(500, text="boom")
		if "anthropic" in url.host:
			assert headers["x-api-key"] == "sk-ant"
			return httpx.Response(
				200, json={"data": [{"id": "claude-sonnet-4", "display_name": "Claude Sonnet 4"}]}
			)
		if "googleapis" in url.host:
			assert headers["x-goog-api-key"] == "sk-gem"
			return httpx.Response(
				200,
				json={"models": [{"name": "models/gemini-2.0-flash", "displayName": "Gemini 2.0 Flash"}]},
			)
		if url.path.endswith("/codex/models"):
			assert url.params["client_version"] == "9.9.9"
			assert headers["Authorization"] == "Bearer tok"
			assert headers["chatgpt-account-id"] == "acc"
			return httpx.Response(
				200,
				json={
					"models": [
						# a name that only repeats the id is no name
						{"slug": "gpt-5-codex", "display_name": "gpt-5-codex"},
						{"slug": "gpt-5-internal", "visibility": "hidden"},
						{"slug": "gpt-5-web", "supported_in_api": False},
					]
				},
			)
		assert str(url) == "https://opencode.ai/zen/go/v1/models"
		assert headers["Authorization"] == "Bearer sk-go"
		return httpx.Response(
			200,
			# nor is one that is only another id, as Mistral's dated one for a "-latest" alias
			json={"data": [{"id": "kimi-k3", "name": "kimi-k3-0905"}, {"id": "grok-4.5"}]},
		)

	catalog = await available_models(store, client=_client(handler))

	assert catalog.models == [
		ModelInfo(name="anthropic/claude-sonnet-4", provider="anthropic", display_name="Claude Sonnet 4"),
		ModelInfo(name="codex/gpt-5-codex", provider="codex", supports_images=True),
		ModelInfo(name="gemini/gemini-2.0-flash", provider="gemini", display_name="Gemini 2.0 Flash"),
		ModelInfo(name="openai/gpt-4o", provider="openai", supports_images=True),
		ModelInfo(name="opencode-go/grok-4.5", provider="opencode-go", supports_images=True),
		ModelInfo(name="opencode-go/kimi-k3", provider="opencode-go", supports_images=True),
	]
	assert len(catalog.errors) == 1 and catalog.errors[0].startswith("openai:")
