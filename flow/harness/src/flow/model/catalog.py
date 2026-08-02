"""Small built-in provider catalog for credential discovery and login UX."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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
