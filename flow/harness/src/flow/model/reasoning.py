"""Maps the neutral reasoning-effort setting onto each provider's own parameter.

The ladder is pi's: off / minimal / low / medium / high / xhigh / max. One session-level
knob has to reach providers that speak different dialects: Anthropic wants a thinking
token budget, the OpenAI family wants a named effort level, and Codex wants it inside a
`reasoning` object. None means "send nothing" — the provider's default behavior. "off"
disables thinking where the provider has a switch (Anthropic); elsewhere the parameter
is omitted, like pi does, because those APIs have no portable off switch.
"""

from __future__ import annotations

from typing import Any

from flow.events import ReasoningEffort

# pi's budgets for Anthropic's budget-based thinking. The map has no xhigh/max rungs:
# pi clamps both down to high on this path, and so does flow.
_ANTHROPIC_BUDGETS: dict[str, int] = {"minimal": 1024, "low": 2048, "medium": 8192, "high": 16384}
# Anthropic requires budget_tokens < max_tokens; keep at least this much for the answer.
_MIN_ANSWER_TOKENS = 1024


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
		# summary: "auto" asks for the reasoning summaries the codex provider streams.
		return {"reasoning": {"effort": effort, "summary": "auto"}}
	# LiteLLM translates its unified param for openai, gemini, xai, and the rest.
	return {"reasoning_effort": effort}


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
