"""OpenCode Go (https://opencode.ai/go) - an API-key subscription gateway.

One key fronts two wire protocols: most models are served over OpenAI
`/chat/completions`, while the MiniMax and Qwen families are served over Anthropic
`/v1/messages`. `opencode_go_model` picks the route from the model id so callers only
ever say `opencode-go/<model-id>`; both routes then run through `LiteLLMModel`.
"""

from __future__ import annotations

from typing import Any

from flow_harness.model.base import Model
from flow_harness.model.litellm import LiteLLMModel

PREFIX = "opencode-go"
BASE_URL = "https://opencode.ai/zen/go/v1"

# Model families the gateway serves on its Anthropic-compatible endpoint.
ANTHROPIC_FAMILIES = ("minimax", "qwen")
# Input modalities from OpenCode Go's catalog. Unknown additions stay text-only
# until the serving surface advertises them, avoiding invalid image requests.
_IMAGE_MODELS = {
	"gpt-5.6-luna",
	"grok-4.5",
	"kimi-k2.5",
	"kimi-k2.6",
	"kimi-k2.7-code",
	"kimi-k3",
	"mimo-v2-omni",
	"mimo-v2.5",
	"minimax-m3",
	"qwen3.5-plus",
	"qwen3.6-plus",
	"qwen3.7-plus",
	"qwen3.8-max",
}


def opencode_go_model(
	name: str,
	*,
	api_key: str | None = None,
	api_base: str | None = None,
	headers: dict[str, str] | None = None,
	params: dict[str, Any] | None = None,
) -> Model:
	model_id = name.split("/", 1)[1] if "/" in name else ""
	if not model_id:
		raise ValueError("OpenCode Go models are named `opencode-go/<model-id>`")
	base = (api_base or BASE_URL).rstrip("/")
	if _is_anthropic(model_id):
		return LiteLLMModel(
			f"anthropic/{model_id}",
			api_key=api_key,
			api_base=_anthropic_base(base),
			headers=headers,
			params=params,
			provider=PREFIX,
			model=name,
			supports_images=opencode_go_supports_images(model_id),
		)
	return LiteLLMModel(
		f"openai/{model_id}",
		api_key=api_key,
		api_base=base,
		headers=headers,
		params=params,
		provider=PREFIX,
		model=name,
		supports_images=opencode_go_supports_images(model_id),
	)


def opencode_go_supports_images(model_id: str) -> bool:
	return model_id in _IMAGE_MODELS


def _is_anthropic(model_id: str) -> bool:
	family = model_id.split("-", 1)[0].rstrip("0123456789.")
	return family in ANTHROPIC_FAMILIES


def _anthropic_base(base: str) -> str:
	"""litellm appends `/v1/messages` unless the base already ends with it, so only
	pre-join when the base is the gateway's versioned root."""
	return f"{base}/messages" if base.endswith("/v1") else base
