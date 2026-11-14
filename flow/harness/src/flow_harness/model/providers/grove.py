"""Grove, Frappe's AI gateway: one key, the OpenAI API under `/openai/v1` and Anthropic's
under `/anthropic`. Grove serves Claude on Anthropic's alone, so `grove_route` sends `claude-*`
there and every other model to OpenAI's; both run through `LiteLLMModel`, errors named Grove's."""

from __future__ import annotations

from typing import Any

from flow_harness.model.base import Model
from flow_harness.model.catalog import model_supports_images
from flow_harness.model.litellm import LiteLLMModel

PREFIX = "grove"


def grove_route(name: str, api_base: str | None) -> tuple[str, str]:
	"""The LiteLLM model and base for `grove/<model-id>` at the gateway `api_base`."""
	model_id = name.split("/", 1)[1] if "/" in name else ""
	if not model_id or not api_base:
		raise ValueError("Grove models are named `grove/<model-id>` and need the gateway's URL as api_base")
	base = api_base.rstrip("/")
	if model_id.startswith("claude"):
		return f"anthropic/{model_id}", f"{base}/anthropic"
	return f"openai/{model_id}", f"{base}/openai/v1"


def grove_model(
	name: str,
	*,
	api_key: str | None = None,
	api_base: str | None = None,
	headers: dict[str, str] | None = None,
	params: dict[str, Any] | None = None,
) -> Model:
	route, base = grove_route(name, api_base)
	return LiteLLMModel(
		route,
		api_key=api_key,
		api_base=base,
		headers=headers,
		params=params,
		provider=PREFIX,
		model=name,
		# Grove passes the vendor's model through, so its capabilities are the vendor's
		supports_images=model_supports_images(route),
	)
