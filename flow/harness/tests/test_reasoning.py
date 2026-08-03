"""The effort-to-provider-params mapping."""

from flow.model.reasoning import reasoning_params


def test_no_effort_sends_nothing():
	assert reasoning_params("anthropic/claude-sonnet-4-5", None) is None
	assert reasoning_params("openai/gpt-5", None) is None


def test_anthropic_effort_becomes_a_thinking_budget_with_max_tokens_headroom():
	for effort, budget in (("low", 4096), ("medium", 12288), ("high", 32768)):
		params = reasoning_params("anthropic/claude-sonnet-4-5", effort)
		assert params is not None
		assert params["thinking"] == {"type": "enabled", "budget_tokens": budget}
		assert params["max_tokens"] > budget


def test_anthropic_budget_is_clamped_under_a_small_output_ceiling():
	# claude-3-haiku can only emit 4096 tokens; a high budget must shrink below that
	params = reasoning_params("anthropic/claude-3-haiku-20240307", "high")
	assert params is not None
	assert params["max_tokens"] == 4096
	assert params["thinking"]["budget_tokens"] == 4096 - 1024


def test_anthropic_unknown_model_gets_budget_plus_answer_allowance():
	params = reasoning_params("anthropic/not-a-real-model", "medium")
	assert params is not None
	assert params["thinking"]["budget_tokens"] == 12288
	assert params["max_tokens"] == 12288 + 4096


def test_codex_effort_goes_into_the_responses_reasoning_object():
	assert reasoning_params("codex/gpt-5", "high") == {"reasoning": {"effort": "high", "summary": "auto"}}


def test_other_providers_get_the_litellm_unified_param():
	for model in ("openai/gpt-5", "gemini/gemini-2.5-pro", "xai/grok-4"):
		assert reasoning_params(model, "medium") == {"reasoning_effort": "medium"}
