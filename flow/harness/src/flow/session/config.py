"""Session configuration — its own module so the agent loop can read it without
importing the session lifecycle (which imports the loop)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from flow.events import ReasoningEffort


class SessionConfig(BaseModel):
	"""Configuration for an agent session.

	Attributes:
		session_id: Client-provided id (else generated); lets a client keep one identity
			across its own store and the daemon (e.g. Flow Session name).
		model: The model to use.
		reasoning_effort: How hard the model should think, on pi's ladder
			(off/minimal/low/medium/high/xhigh/max). None = provider default (no
			reasoning parameter is sent); "off" disables thinking where the provider
			has a switch.
		system_preamble: Replaces the default body (intro, tools list, guidelines) of
			the composed prompt.
		system_suffix: Appended after the body, before the project context (the
			client-injection point).
		system_prompt: Verbatim system prompt; when set, composition is skipped. When
			None (default), `SessionStore.create` composes the prompt from the preamble,
			AGENTS.md files, and suffix, and stores the result here.
		system_append: Appended to the end of the resolved prompt, composed or verbatim
			(the `--append-system-prompt` flag of the TUI and the web command).
		tools: Built-in tools available to the agent.
		client_tools: Schemas registered by a client.
		callback_url: Where client tools are dispatched.
		callback_token: Bearer sent to the client on callbacks (shared secret).
		user_context: Opaque context passed back on callbacks.
		credential_id: Named user-global credential; inferred from model prefix when absent.
		confirm_tools: Extra tools that pause for approval, on top of each tool's own
			default. `auto_approve` is the only way to switch approval off.
		auto_approve: Unattended runs (triggers) skip approval.
		skills_enabled: Discover harness-neutral skills for this session.
		skill_paths: Additional skill files or directories, resolved from `cwd`.
		auto_compact: Compact near the model's window; recover from overflow once per run.
		compact_threshold_tokens: Compact past this estimate; default derives from the window.
		cwd: Current working directory.
		max_turns: Maximum allowed turns.
		max_output_tokens: Simple spend cap on output tokens.
		stream: Consume the model as a token stream (vs a single response).
	"""

	model_config = ConfigDict(extra="forbid")

	session_id: str | None = None
	model: str = "mock"
	reasoning_effort: ReasoningEffort | None = None
	system_preamble: str | None = None
	system_suffix: str | None = None
	system_prompt: str | None = None
	system_append: str | None = None
	tools: list[str] = Field(default_factory=lambda: ["bash", "read_file", "write", "edit", "grep"])
	client_tools: list[dict] = Field(default_factory=list)
	callback_url: str | None = None
	callback_token: str | None = None
	user_context: dict = Field(default_factory=dict)
	credential_id: str | None = None
	confirm_tools: list[str] = Field(default_factory=list)
	auto_approve: bool = False
	skills_enabled: bool = True
	skill_paths: list[str] = Field(default_factory=list, max_length=32)
	auto_compact: bool = True
	compact_threshold_tokens: int | None = Field(default=None, gt=0)
	cwd: str = "."
	max_turns: int = 500
	max_output_tokens: int = 200_000
	stream: bool = True

	def redacted(self) -> dict:
		data = self.model_dump()
		for secret in ("callback_token",):
			if data.get(secret):
				data[secret] = "***"
		return data
