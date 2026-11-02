"""The runtime model catalog: configured-provider filtering and litellm derivation."""

import litellm
import pytest

from flow_harness.model.catalog import PROVIDERS, configured_providers, list_models
from flow_harness.model.credentials import CredentialStore, OAuthCredential

COST_TABLE = {
	"sample_spec": {"mode": "one of: chat, embedding", "litellm_provider": "one of: openai, ..."},
	"gpt-4o": {"mode": "chat", "supports_function_calling": True, "litellm_provider": "openai"},
	"ft:gpt-4o": {"mode": "chat", "supports_function_calling": True, "litellm_provider": "openai"},
	"text-embedding-3-small": {"mode": "embedding", "litellm_provider": "openai"},
	"claude-sonnet-4": {"mode": "chat", "supports_function_calling": True, "litellm_provider": "anthropic"},
	"claude-instant-1": {"mode": "chat", "supports_function_calling": False, "litellm_provider": "anthropic"},
	"gemini/gemini-2.0-flash": {
		"mode": "chat",
		"supports_function_calling": True,
		"litellm_provider": "gemini",
	},
	"bedrock-thing": {"mode": "chat", "supports_function_calling": True, "litellm_provider": "bedrock"},
}


@pytest.fixture
def bare_env(monkeypatch):
	"""No provider API key leaks in from the developer's environment."""
	for provider in PROVIDERS:
		for name in provider.api_key_envs:
			monkeypatch.delenv(name, raising=False)
	monkeypatch.setattr(litellm, "model_cost", COST_TABLE)


def _store(tmp_path) -> CredentialStore:
	return CredentialStore(str(tmp_path / "credentials.json"))


def test_only_configured_providers_contribute_models(tmp_path, bare_env, monkeypatch):
	store = _store(tmp_path)
	assert configured_providers(store) == []
	assert list_models(store) == []

	# native providers are covered only by live discovery, not the static catalog
	store.set_oauth("codex", OAuthCredential(access="a", refresh="r", expires=1))
	assert [provider.id for provider in configured_providers(store)] == ["codex"]
	assert list_models(store) == []

	monkeypatch.setenv("OPENAI_API_KEY", "k")
	assert [provider.id for provider in configured_providers(store)] == ["openai", "codex"]
	names = [model.name for model in list_models(store)]
	# prefixed, chat-only, tool-capable, no ft: templates, no other providers
	assert names == ["openai/gpt-4o"]

	# stored keys count too, and an already prefixed id is not prefixed again
	store.set_api_key("anthropic", "k")
	store.set_api_key("gemini", "k")
	assert [(model.name, model.provider) for model in list_models(store)] == [
		("anthropic/claude-sonnet-4", "anthropic"),
		("gemini/gemini-2.0-flash", "gemini"),
		("openai/gpt-4o", "openai"),
	]
