"""The effort-to-provider-params mapping."""

from flow_harness.model import reasoning
from flow_harness.model.reasoning import reasoning_params


def _catalog(monkeypatch, info):
	"""Pin what litellm claims about every model; None = unknown to litellm."""
	monkeypatch.setattr(reasoning, "_model_info", lambda model: info)


def test_no_effort_sends_nothing():
	assert reasoning_params("anthropic/claude-sonnet-4-5", None) is None
	assert reasoning_params("openai/gpt-5", None) is None


def test_anthropic_effort_becomes_a_thinking_budget_with_max_tokens_headroom():
	for effort, budget in (("minimal", 1024), ("low", 2048), ("medium", 8192), ("high", 16384)):
		params = reasoning_params("anthropic/claude-sonnet-4-5", effort)
		assert params is not None
		assert params["thinking"] == {"type": "enabled", "budget_tokens": budget}
		assert params["max_tokens"] > budget


def test_anthropic_xhigh_and_max_clamp_down_to_high():
	high = reasoning_params("anthropic/claude-sonnet-4-5", "high")
	assert reasoning_params("anthropic/claude-sonnet-4-5", "xhigh") == high
	assert reasoning_params("anthropic/claude-sonnet-4-5", "max") == high


def test_anthropic_off_disables_thinking():
	assert reasoning_params("anthropic/claude-sonnet-4-5", "off") == {"thinking": {"type": "disabled"}}


def test_anthropic_budget_is_clamped_under_a_small_output_ceiling():
	# claude-3-haiku can only emit 4096 tokens; a high budget must shrink below that
	params = reasoning_params("anthropic/claude-3-haiku-20240307", "high")
	assert params is not None
	assert params["max_tokens"] == 4096
	assert params["thinking"]["budget_tokens"] == 4096 - 1024


def test_anthropic_unknown_model_gets_budget_plus_answer_allowance():
	params = reasoning_params("anthropic/not-a-real-model", "medium")
	assert params is not None
	assert params["thinking"]["budget_tokens"] == 8192
	assert params["max_tokens"] == 8192 + 4096


def test_codex_effort_goes_into_the_responses_reasoning_object():
	for effort in ("minimal", "high", "xhigh"):
		assert reasoning_params("codex/gpt-5", effort) == {"reasoning": {"effort": effort, "summary": "auto"}}


def test_codex_max_clamps_to_xhigh():
	assert reasoning_params("codex/gpt-5", "max") == {"reasoning": {"effort": "xhigh", "summary": "auto"}}


def test_litellm_known_reasoning_model_gets_the_unified_param(monkeypatch):
	_catalog(monkeypatch, {"supports_reasoning": True})
	for effort in ("minimal", "low", "medium", "high"):
		assert reasoning_params("openai/gpt-5", effort) == {"reasoning_effort": effort}


def test_litellm_non_reasoning_model_drops_the_param(monkeypatch):
	_catalog(monkeypatch, {"supports_reasoning": None})
	assert reasoning_params("openai/gpt-4o", "high") is None


def test_litellm_xhigh_and_max_clamp_down_unless_the_model_opts_in(monkeypatch):
	_catalog(monkeypatch, {"supports_reasoning": True})
	assert reasoning_params("gemini/gemini-2.5-pro", "xhigh") == {"reasoning_effort": "high"}
	assert reasoning_params("gemini/gemini-2.5-pro", "max") == {"reasoning_effort": "high"}
	_catalog(monkeypatch, {"supports_reasoning": True, "supports_xhigh_reasoning_effort": True})
	assert reasoning_params("openai/gpt-5.5", "xhigh") == {"reasoning_effort": "xhigh"}
	assert reasoning_params("openai/gpt-5.5", "max") == {"reasoning_effort": "xhigh"}
	_catalog(
		monkeypatch,
		{"supports_reasoning": True, "supports_max_reasoning_effort": True},
	)
	assert reasoning_params("openai/gpt-6", "max") == {"reasoning_effort": "max"}


def test_litellm_minimal_and_low_clamp_up_only_when_explicitly_disabled(monkeypatch):
	_catalog(monkeypatch, {"supports_reasoning": True, "supports_minimal_reasoning_effort": False})
	assert reasoning_params("openai/o1", "minimal") == {"reasoning_effort": "low"}
	_catalog(
		monkeypatch,
		{
			"supports_reasoning": True,
			"supports_minimal_reasoning_effort": False,
			"supports_low_reasoning_effort": False,
		},
	)
	assert reasoning_params("openai/gpt-5.5-pro", "minimal") == {"reasoning_effort": "medium"}
	assert reasoning_params("openai/gpt-5.5-pro", "low") == {"reasoning_effort": "medium"}


def test_litellm_unknown_model_passes_through_and_bypasses_the_guard(monkeypatch):
	_catalog(monkeypatch, None)
	assert reasoning_params("custom-gateway/new-model", "max") == {
		"reasoning_effort": "max",
		"allowed_openai_params": ["reasoning_effort"],
	}


def test_opencode_go_clamps_minimal_to_low_without_changing_openrouter(monkeypatch):
	_catalog(monkeypatch, None)
	assert reasoning_params("opencode-go/kimi-k2.5", "minimal") == {
		"reasoning_effort": "low",
		"allowed_openai_params": ["reasoning_effort"],
	}
	assert reasoning_params("openrouter/moonshotai/kimi-k2.5", "minimal") == {
		"reasoning_effort": "minimal",
		"allowed_openai_params": ["reasoning_effort"],
	}


def test_off_omits_the_param_where_no_switch_exists():
	assert reasoning_params("codex/gpt-5", "off") is None
	assert reasoning_params("openai/gpt-5", "off") is None
