"""Maps the neutral reasoning-effort setting onto each provider's own parameter.

The ladder is pi's: off / minimal / low / medium / high / xhigh / max. One session-level
knob has to reach providers that speak different dialects: Anthropic wants a thinking
token budget, the OpenAI family wants a named effort level, and Codex wants it inside a
`reasoning` object. None means "send nothing" — the provider's default behavior. "off"
disables thinking where the provider has a switch (Anthropic); elsewhere the parameter
is omitted, like pi does, because those APIs have no portable off switch.

On the LiteLLM path the effort is clamped to the nearest level the model supports (per
litellm's capability flags), dropped for models that cannot reason, and passed through
for models litellm does not know after applying any serving-surface constraints known to
Flow. Gateways behind a custom base otherwise clamp or ignore what they don't support,
while litellm's client-side guard would refuse the request outright.
"""

from __future__ import annotations

from typing import Any

from flow_harness.events import ReasoningEffort

# pi's budgets for Anthropic's budget-based thinking. The map has no xhigh/max rungs:
# pi clamps both down to high on this path, and so does flow.
_ANTHROPIC_BUDGETS: dict[str, int] = {"minimal": 1024, "low": 2048, "medium": 8192, "high": 16384}
# Anthropic requires budget_tokens < max_tokens; keep at least this much for the answer.
_MIN_ANSWER_TOKENS = 1024
# OpenCode Go validates reasoning_effort at its gateway and does not accept `minimal`.
_PROVIDER_EFFORT_ALIASES: dict[str, dict[ReasoningEffort, ReasoningEffort]] = {
	"opencode-go": {"minimal": "low"},
}


def reasoning_params(model: str, effort: ReasoningEffort | None) -> dict[str, Any] | None:
	"""Provider-shaped request params for the given effort, or None to send nothing."""
	if effort is None:
		return None
	provider = model.split("/", 1)[0]
	if provider == "anthropic":
		return _anthropic_params(model, effort)
	if effort == "off":
		return None
	if provider == "codex":
		effort = "xhigh" if effort == "max" else effort
		return {"reasoning": {"effort": effort, "summary": "auto"}}
	return _litellm_params(model, effort)


def _litellm_params(model: str, effort: ReasoningEffort) -> dict[str, Any] | None:
	"""LiteLLM's unified param, clamped to what the model supports.

	Models litellm does not know (gateway ids behind a custom base), or whose
	provider it lists without the param (custom_openai/openai/gpt-x), skip its
	client-side support guard via allowed_openai_params; the provider decides.
	"""
	provider = model.split("/", 1)[0]
	effort = _PROVIDER_EFFORT_ALIASES.get(provider, {}).get(effort, effort)
	info = _model_info(model)
	if info is None:
		return {"reasoning_effort": effort, "allowed_openai_params": ["reasoning_effort"]}
	if not info.get("supports_reasoning"):
		return None
	# litellm's own policy: xhigh/max are opt-in per model, minimal/low opt-out.
	if effort == "max" and not info.get("supports_max_reasoning_effort"):
		effort = "xhigh"
	if effort == "xhigh" and not info.get("supports_xhigh_reasoning_effort"):
		effort = "high"
	if effort == "minimal" and info.get("supports_minimal_reasoning_effort") is False:
		effort = "low"
	if effort == "low" and info.get("supports_low_reasoning_effort") is False:
		effort = "medium"
	supported = info.get("supported_openai_params")
	if supported is not None and "reasoning_effort" not in supported:
		return {"reasoning_effort": effort, "allowed_openai_params": ["reasoning_effort"]}
	return {"reasoning_effort": effort}


def _model_info(model: str) -> dict[str, Any] | None:
	import litellm

	try:
		return dict(litellm.get_model_info(model))
	except Exception:
		return None


def _anthropic_params(model: str, effort: ReasoningEffort) -> dict[str, Any]:
	"""A thinking budget plus an explicit max_tokens that leaves room for the answer.

	max_tokens is the model's own output ceiling when known (what LiteLLM would default
	to anyway), else the budget plus a base answer allowance; the budget is clamped
	under it so small-output models still get a valid request.
	"""
	if effort == "off":
		return {"thinking": {"type": "disabled"}}
	budget = _ANTHROPIC_BUDGETS.get(effort, _ANTHROPIC_BUDGETS["high"])
	max_tokens = _max_output_tokens(model) or budget + 4096
	budget = min(budget, max_tokens - _MIN_ANSWER_TOKENS)
	return {
		"thinking": {"type": "enabled", "budget_tokens": budget},
		"max_tokens": max_tokens,
	}


def _max_output_tokens(model: str) -> int | None:
	import litellm

	try:
		return litellm.get_max_tokens(model)
	except Exception:
		return None
