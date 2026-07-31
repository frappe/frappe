"""Session configuration — its own module so the agent loop can read it without
importing the session lifecycle (which imports the loop)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SessionConfig(BaseModel):
	"""Configuration for an agent session.

	Attributes:
		session_id: Client-provided id (else generated); lets a client keep one identity
			across its own store and the daemon (e.g. Flow Session name).
		model: The model to use.
		system_prompt: System prompt for the agent.
		tools: Built-in tools available to the agent.
		client_tools: Schemas registered by a client.
		callback_url: Where client tools are dispatched.
		callback_token: Bearer sent to the client on callbacks (shared secret).
		user_context: Opaque context passed back on callbacks.
		credential_id: Named user-global credential; inferred from model prefix when absent.
		confirm_tools: Extra tools that pause for approval, on top of each tool's own
			default. `auto_approve` is the only way to switch approval off.
		auto_approve: Unattended runs (triggers) skip approval.
		cwd: Current working directory.
		max_turns: Maximum allowed turns.
		max_output_tokens: Simple spend cap on output tokens.
		stream: Consume the model as a token stream (vs a single response).
	"""

	model_config = ConfigDict(extra="forbid")

	session_id: str | None = None
	model: str = "mock"
	system_prompt: str = "You are a helpful agent."
	tools: list[str] = Field(default_factory=lambda: ["bash", "read_file", "write", "edit", "grep"])
	client_tools: list[dict] = Field(default_factory=list)
	callback_url: str | None = None
	callback_token: str | None = None
	user_context: dict = Field(default_factory=dict)
	credential_id: str | None = None
	confirm_tools: list[str] = Field(default_factory=list)
	auto_approve: bool = False
	cwd: str = "."
	max_turns: int = 30
	max_output_tokens: int = 200_000
	stream: bool = True

	def redacted(self) -> dict:
		data = self.model_dump()
		for secret in ("callback_token",):
			if data.get(secret):
				data[secret] = "***"
		return data
