"""Small built-in provider catalog for credential discovery and login UX, plus the
runtime model catalog derived from litellm's cost table."""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
	from flow.model.credentials import CredentialStore

AuthMethod = Literal["api_key", "oauth"]


@dataclass(frozen=True)
class ProviderSpec:
	id: str
	display_name: str
	model_prefixes: tuple[str, ...]
	api_key_envs: tuple[str, ...] = ()
	auth_methods: tuple[AuthMethod, ...] = ("api_key",)


PROVIDERS = (
	ProviderSpec("openai", "OpenAI API", ("openai",), ("OPENAI_API_KEY",)),
	ProviderSpec("anthropic", "Anthropic", ("anthropic",), ("ANTHROPIC_API_KEY",)),
	ProviderSpec(
		"gemini",
		"Google Gemini",
		("gemini",),
		("GEMINI_API_KEY", "GOOGLE_API_KEY"),
	),
	ProviderSpec("openrouter", "OpenRouter", ("openrouter",), ("OPENROUTER_API_KEY",)),
	ProviderSpec("xai", "xAI", ("xai",), ("XAI_API_KEY",)),
	ProviderSpec("groq", "Groq", ("groq",), ("GROQ_API_KEY",)),
	ProviderSpec("deepseek", "DeepSeek", ("deepseek",), ("DEEPSEEK_API_KEY",)),
	ProviderSpec("mistral", "Mistral", ("mistral",), ("MISTRAL_API_KEY",)),
	ProviderSpec("cerebras", "Cerebras", ("cerebras",), ("CEREBRAS_API_KEY",)),
	ProviderSpec("codex", "OpenAI Codex subscription", ("codex",), auth_methods=("oauth",)),
	ProviderSpec(
		"opencode-go",
		"OpenCode Go subscription",
		("opencode-go",),
		("OPENCODE_API_KEY",),
	),
)

_PROVIDERS_BY_ID = {provider.id: provider for provider in PROVIDERS}
_PROVIDERS_BY_MODEL_PREFIX = {
	prefix: provider for provider in PROVIDERS for prefix in provider.model_prefixes
}


def get_provider(provider_id: str) -> ProviderSpec | None:
	return _PROVIDERS_BY_ID.get(provider_id)


def provider_for_model(model: str) -> ProviderSpec | None:
	return _PROVIDERS_BY_MODEL_PREFIX.get(model.split("/", 1)[0])


def configured_env(provider: ProviderSpec) -> str | None:
	"""The name of the first of the provider's API-key env vars that is set, if any."""
	return next((name for name in provider.api_key_envs if os.environ.get(name)), None)


def configured_providers(store: CredentialStore) -> list[ProviderSpec]:
	"""Providers usable right now: a stored credential or an API-key env var."""
	stored = {entry.provider_id for entry in store.list()}
	return [
		provider for provider in PROVIDERS if provider.id in stored or configured_env(provider) is not None
	]


@dataclass(frozen=True)
class ModelInfo:
	name: str  # flow model name, e.g. "anthropic/claude-sonnet-4"
	provider: str  # provider id


# Native providers never appear in litellm's cost table; their ids are listed here.
NATIVE_MODEL_IDS: dict[str, tuple[str, ...]] = {
	"codex": ("gpt-5", "gpt-5-codex"),
}


def list_models(store: CredentialStore) -> list[ModelInfo]:
	"""The model catalog for configured providers only. Derived at runtime, so there is
	no curated list to maintain; pickers must still accept free text for anything the
	filters miss."""
	configured = {provider.id for provider in configured_providers(store)}
	models: dict[str, str] = {}
	for provider_id, model_ids in NATIVE_MODEL_IDS.items():
		if provider_id in configured:
			for model_id in model_ids:
				models[f"{provider_id}/{model_id}"] = provider_id
	for name, provider_id in _litellm_chat_models():
		if provider_id in configured:
			models.setdefault(name, provider_id)
	return [ModelInfo(name=name, provider=provider) for name, provider in sorted(models.items())]


def _litellm_chat_models() -> Iterator[tuple[str, str]]:
	"""(flow model name, provider id) pairs from `litellm.model_cost`. Chat models with
	function calling only — the agent loop needs tools. `ft:` fine-tune templates are
	placeholders, not callable ids."""
	import litellm

	for key, spec in litellm.model_cost.items():
		if not isinstance(spec, dict):
			continue
		if spec.get("mode") != "chat" or not spec.get("supports_function_calling"):
			continue
		if key.startswith("ft:"):
			continue
		provider_id = spec.get("litellm_provider")
		if provider_id not in _PROVIDERS_BY_ID:
			continue
		name = key if key.split("/", 1)[0] == provider_id else f"{provider_id}/{key}"
		yield name, provider_id
