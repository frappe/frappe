"""The effort-to-provider-params mapping."""

from flow_harness.model import reasoning
from flow_harness.model.reasoning import reasoning_params


def _catalog(monkeypatch, info):
	"""Pin what litellm claims about every model; None = unknown to litellm."""
	monkeypatch.setattr(reasoning, "_model_info", lambda model: info)


def test_anthropic_effort_becomes_a_thinking_budget_with_max_tokens_headroom():
	model = "anthropic/claude-sonnet-4-5"
	assert reasoning_params(model, None) is None
	for effort, budget in (("minimal", 1024), ("low", 2048), ("medium", 8192), ("high", 16384)):
		params = reasoning_params(model, effort)
		assert params is not None
		assert params["thinking"] == {"type": "enabled", "budget_tokens": budget}, effort
		assert params["max_tokens"] > budget, effort

	# no xhigh or max rungs: both clamp down to high
	assert reasoning_params(model, "xhigh") == reasoning_params(model, "high")
	assert reasoning_params(model, "max") == reasoning_params(model, "high")
	assert reasoning_params(model, "off") == {"thinking": {"type": "disabled"}}

	# claude-3-haiku can only emit 4096 tokens; a high budget must shrink below that
	assert reasoning_params("anthropic/claude-3-haiku-20240307", "high") == {
		"thinking": {"type": "enabled", "budget_tokens": 4096 - 1024},
		"max_tokens": 4096,
	}
	# an unknown model gets the budget plus an answer allowance
	assert reasoning_params("anthropic/not-a-real-model", "medium") == {
		"thinking": {"type": "enabled", "budget_tokens": 8192},
		"max_tokens": 8192 + 4096,
	}


def test_codex_effort_goes_into_the_responses_reasoning_object():
	for effort in ("minimal", "high", "xhigh"):
		assert reasoning_params("codex/gpt-5", effort) == {"reasoning": {"effort": effort, "summary": "auto"}}
	assert reasoning_params("codex/gpt-5", "max") == {"reasoning": {"effort": "xhigh", "summary": "auto"}}
	# no off switch, so nothing is sent
	assert reasoning_params("codex/gpt-5", "off") is None


def test_litellm_effort_is_clamped_to_what_the_model_supports(monkeypatch):
	reasons = {"supports_reasoning": True}
	no_minimal = {**reasons, "supports_minimal_reasoning_effort": False}
	no_low = {**no_minimal, "supports_low_reasoning_effort": False}
	xhigh = {**reasons, "supports_xhigh_reasoning_effort": True}
	unguarded = ["reasoning_effort"]
	cases = [
		# (litellm's model info, model, effort, params)
		(reasons, "openai/gpt-5", None, None),
		(reasons, "openai/gpt-5", "off", None),
		(reasons, "openai/gpt-5", "minimal", {"reasoning_effort": "minimal"}),
		(reasons, "openai/gpt-5", "low", {"reasoning_effort": "low"}),
		(reasons, "openai/gpt-5", "medium", {"reasoning_effort": "medium"}),
		(reasons, "openai/gpt-5", "high", {"reasoning_effort": "high"}),
		({"supports_reasoning": None}, "openai/gpt-4o", "high", None),
		# xhigh and max are opt-in per model
		(reasons, "gemini/gemini-2.5-pro", "xhigh", {"reasoning_effort": "high"}),
		(reasons, "gemini/gemini-2.5-pro", "max", {"reasoning_effort": "high"}),
		(xhigh, "openai/gpt-5.5", "xhigh", {"reasoning_effort": "xhigh"}),
		(xhigh, "openai/gpt-5.5", "max", {"reasoning_effort": "xhigh"}),
		(
			{**reasons, "supports_max_reasoning_effort": True},
			"openai/gpt-6",
			"max",
			{"reasoning_effort": "max"},
		),
		# minimal and low clamp up only when explicitly disabled
		(no_minimal, "openai/o1", "minimal", {"reasoning_effort": "low"}),
		(no_low, "openai/gpt-5.5-pro", "minimal", {"reasoning_effort": "medium"}),
		(no_low, "openai/gpt-5.5-pro", "low", {"reasoning_effort": "medium"}),
		# unknown to litellm, or a provider listed without the param: bypass its guard
		(
			None,
			"custom-gateway/new-model",
			"max",
			{"reasoning_effort": "max", "allowed_openai_params": unguarded},
		),
		(
			# litellm's entry for custom_openai/openai/gpt-6-*
			{**reasons, "supported_openai_params": ["temperature"]},
			"custom_openai/openai/gpt-x",
			"high",
			{"reasoning_effort": "high", "allowed_openai_params": unguarded},
		),
		(
			{**reasons, "supported_openai_params": ["reasoning_effort"]},
			"openai/gpt-x",
			"high",
			{"reasoning_effort": "high"},
		),
		# OpenCode Go rejects minimal; OpenRouter does not
		(
			None,
			"opencode-go/kimi-k2.5",
			"minimal",
			{"reasoning_effort": "low", "allowed_openai_params": unguarded},
		),
		(
			None,
			"openrouter/moonshotai/kimi-k2.5",
			"minimal",
			{"reasoning_effort": "minimal", "allowed_openai_params": unguarded},
		),
	]
	for info, model, effort, params in cases:
		_catalog(monkeypatch, info)
		assert reasoning_params(model, effort) == params, (model, effort)
