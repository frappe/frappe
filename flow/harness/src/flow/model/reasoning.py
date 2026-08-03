"""Maps the neutral reasoning-effort setting onto each provider's own parameter.

One session-level knob (`low` / `medium` / `high` / None) has to reach providers that
speak different dialects: Anthropic wants a thinking token budget, the OpenAI family
wants a named effort level, and Codex wants it inside a `reasoning` object. None means
"send nothing" — the provider's default behavior, whatever that is.
"""

from __future__ import annotations

from typing import Any

from flow.events import ReasoningEffort

_ANTHROPIC_BUDGETS: dict[str, int] = {"low": 4096, "medium": 12288, "high": 32768}
# Anthropic requires budget_tokens < max_tokens; keep at least this much for the answer.
_MIN_ANSWER_TOKENS = 1024


def reasoning_params(model: str, effort: ReasoningEffort | None) -> dict[str, Any] | None:
	"""Provider-shaped request params for the given effort, or None to send nothing."""
	if effort is None:
		return None
	provider = model.split("/", 1)[0]
	if provider == "anthropic":
		return _anthropic_params(model, effort)
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
	budget = _ANTHROPIC_BUDGETS[effort]
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
