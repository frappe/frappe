"""Session configuration — its own module so the agent loop can read it without
importing the session lifecycle (which imports the loop)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from flow_harness.events import ReasoningEffort

# the sub-agent every session has: a copy of the caller with a fresh context
GENERAL_AGENT = "general"


class SessionConfig(BaseModel):
	"""Configuration for an agent session.

	Attributes:
		session_id: Client-provided id (else generated); lets a client keep one identity
			across its own store and the daemon (e.g. Flow Session name).
		title: Display title. Generated in the background from the first user message;
			a client-set value suppresses generation.
		preset: The client's agent preset the session was made from, kept for the
			client to show; the daemon never reads it.
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
		tools: Built-in and bundled tools available to the agent, by name.
		subagents: Sub-agents the `subagent` tool can run, beside `general`.
		max_concurrent_subagents: How many sub-agents may run at once; later ones wait.
		extension_tools: Extension tools available to the agent; None means every loaded one.
		client_tools: Schemas registered by a client.
		callback_url: Where client tools and opted-in run terminals are dispatched.
		callback_token: Shared secret sent as X-Harness-Token on callbacks.
		callback_headers: Extra headers sent on every callback, for a host that routes by one.
		callback_timeout: Seconds to wait for a callback to answer.
		notify_run_ended: Report durable run terminals through callback_url.
		user_context: Opaque context passed back on callbacks.
		credential_id: Named user-global credential; inferred from model prefix when absent.
		api_key: Client-supplied model API key, used instead of the daemon's credential
			store. Redacted in API responses.
		api_base: Endpoint override that travels with `api_key`.
		model_params: Extra provider params sent with every model call.
		confirm_tools: Extra tools that pause for approval, on top of each tool's own
			default. `auto_approve` is the only way to switch approval off.
		auto_approve: Unattended runs (triggers) skip approval.
		skills_enabled: Discover harness-neutral skills for this session.
		skill_paths: Additional skill files or directories, resolved from `cwd`.
		auto_compact: Compact near the model's window; recover from overflow once per run.
		compact_threshold_tokens: Compact past this estimate; default derives from the window.
		cwd: Current working directory.
		max_turns: Maximum allowed turns.
		token_budget: Spend cap on a run's fresh tokens, shared with the sub-agents
			inside it; None means no cap. Cache reads are discounted by the providers,
			so they are left out.
		stream: Consume the model as a token stream (vs a single response).
	"""

	model_config = ConfigDict(extra="forbid")

	session_id: str | None = None
	title: str | None = None
	preset: str | None = None
	model: str = "mock"
	reasoning_effort: ReasoningEffort | None = None
	system_preamble: str | None = None
	system_suffix: str | None = None
	system_prompt: str | None = None
	system_append: str | None = None
	tools: list[str] = Field(default_factory=lambda: ["bash", "read", "write", "edit", "subagent"])
	subagents: list[SubagentConfig] = Field(default_factory=list)
	max_concurrent_subagents: int = Field(default=5, ge=1)
	extension_tools: list[str] | None = None
	client_tools: list[dict] = Field(default_factory=list)
	callback_url: str | None = None
	callback_token: str | None = None
	callback_headers: dict[str, str] = Field(default_factory=dict)
	callback_timeout: float = Field(default=120, gt=0)
	notify_run_ended: bool = False
	user_context: dict = Field(default_factory=dict)
	credential_id: str | None = None
	api_key: str | None = None
	api_base: str | None = None
	model_params: dict[str, Any] = Field(default_factory=dict)
	confirm_tools: list[str] = Field(default_factory=list)
	auto_approve: bool = False
	skills_enabled: bool = True
	skill_paths: list[str] = Field(default_factory=list, max_length=32)
	auto_compact: bool = True
	compact_threshold_tokens: int | None = Field(default=None, gt=0)
	cwd: str = "."
	max_turns: int = 500
	token_budget: int | None = Field(default=None, gt=0)
	stream: bool = True

	@model_validator(mode="after")
	def _check_agents(self) -> SessionConfig:
		names = [agent.name for agent in self.subagents]
		if GENERAL_AGENT in names:
			raise ValueError(f"agent name {GENERAL_AGENT!r} is reserved")
		if len(set(names)) != len(names):
			raise ValueError("agent names must be unique")
		return self

	def redacted(self) -> dict:
		data = self.model_dump()
		for secret in ("callback_token", "api_key"):
			if data.get(secret):
				data[secret] = "***"
		for agent in data["subagents"]:
			if agent.get("api_key"):
				agent["api_key"] = "***"
		return data


class SubagentConfig(BaseModel):
	"""An agent the `subagent` tool can run; an unset field inherits the session's value.

	Attributes:
		name: What the model passes as `agent`; unique per session, and never `general`.
		description: What the agent is for, listed in the tool's description.
		model: The model to use.
		api_key: Client-supplied model API key that replaces the daemon's credential
			store. Redacted in API responses.
		api_base: Endpoint override that travels with `api_key`.
		model_params: Extra provider params for the child's model calls; like `api_key`,
			never inherited once the child sets its own model.
		reasoning_effort: How hard the model should think.
		system_prompt: Verbatim system prompt.
		tools: Built-in and bundled tools, by name; `subagent` is never one of them.
		extension_tools: Extension tools available to the child; None means the session's.
		client_tools: Schemas registered by a client, for the child.
		confirm_tools: Extra tools that pause for approval inside the child.
		max_turns: Maximum allowed turns for the child.
		user_context: Opaque context passed back on the child's callbacks.
	"""

	model_config = ConfigDict(extra="forbid")

	name: str = Field(min_length=1, max_length=64)
	description: str = ""
	model: str | None = None
	api_key: str | None = None
	api_base: str | None = None
	model_params: dict[str, Any] | None = None
	reasoning_effort: ReasoningEffort | None = None
	system_prompt: str | None = None
	tools: list[str] | None = None
	extension_tools: list[str] | None = None
	client_tools: list[dict] | None = None
	confirm_tools: list[str] | None = None
	max_turns: int | None = Field(default=None, ge=1)
	user_context: dict | None = None


GENERAL_SUBAGENT = SubagentConfig(name=GENERAL_AGENT, description="a copy of you with a fresh context")


def known_agents(subagents: Iterable[SubagentConfig]) -> dict[str, SubagentConfig]:
	"""The agents a session offers, by name, the general one first."""
	return {item.name: item for item in (GENERAL_SUBAGENT, *subagents)}
