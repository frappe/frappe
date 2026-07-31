"""The agent loop: ask the model, run the tools it asks for, repeat — until it stops
calling tools, a cap trips, or a gated tool pauses the run.

`run` and `resume` only yield events and raise errors. The session saves them as they
arrive, so the transcript the loop reads for the next model call is always current.

A tool call can be intercepted two ways, and they do different jobs:
  - `before_tool_call` / `after_tool_call`: plain in-process callbacks, never saved.
    `before` can change the arguments or answer the call itself; `after` can rewrite
    the result.
  - the confirm gate: the durable pause. A gated call is not run — the loop finishes
    the turn, yields `ApprovalRequired` + `RunEnded(reason="paused")`, and returns.
    The pause is in the log, so `resume` can arrive later, from any client, even
    after a restart.

Order per call: bad arguments, before hook, confirm gate, then run it.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from typing import Any

from flow_server.agent.client_tools import call_client
from flow_server.events import (
	AnyEvent,
	ApprovalRequired,
	AssistantMessage,
	PendingCall,
	RunEnded,
	RunStarted,
	ToolCall,
	ToolResult,
	TranscriptMessage,
	Usage,
	UserMessage,
)
from flow_server.model import Model, ModelRequest, get_model
from flow_server.model.auth import resolve_model_auth
from flow_server.model.base import ModelCancelled, await_with_cancellation, iterate_with_cancellation
from flow_server.model.credentials import CredentialStore
from flow_server.session.config import SessionConfig
from flow_server.session.transcript import PendingApproval
from flow_server.tools import BUILTIN_TOOLS, Tool, ToolContext


@dataclass
class HookDecision:
	"""A `before_tool_call` hook's decision. If `result` is set the call is short-circuited
	(a policy block or a synthetic result); elif `args` is set the call's arguments are
	rewritten and it proceeds; both unset = proceed unchanged."""

	args: dict | None = None
	result: str | None = None
	is_error: bool = False


# before(call, ctx) -> HookDecision | None (sync or async); after(call, result) -> str | None
BeforeHook = Callable[[ToolCall, ToolContext], Any]
AfterHook = Callable[[ToolCall, ToolResult], Any]
# what a steering drain hands the loop: the next queued message, or None when drained
NextSteering = Callable[[], str | None]


@dataclass(frozen=True)
class LoopInputs:
	"""Everything a run needs from its session, prepared once at admission.

	``messages`` is the live provider-facing transcript the session's reducer
	maintains; the loop only reads it.
	"""

	config: SessionConfig
	messages: list[TranscriptMessage]
	credentials: CredentialStore
	abort: asyncio.Event
	allowed_roots: tuple[str, ...] = ()
	session_id: str = ""
	model: Model | None = None
	next_steering: NextSteering | None = None
	before_tool_call: BeforeHook | None = None
	after_tool_call: AfterHook | None = None


_DENIED = json.dumps({"status": "denied", "message": "User denied this tool call."})
_TRUNCATED = json.dumps(
	{
		"status": "truncated",
		"message": "Tool not executed.",
		"instruction": (
			"The response hit the output token limit, so these arguments may be "
			"incomplete. Re-issue the call with complete arguments."
		),
	}
)


async def run(message: str, inputs: LoopInputs) -> AsyncIterator[AnyEvent]:
	"""One new run: open the protocol, add the user message, then take turns."""
	yield RunStarted(run_id=uuid.uuid4().hex[:12])
	yield UserMessage(content=message)
	async for event in _loop(inputs):
		yield event


async def resume(
	approval: PendingApproval, answers: dict[str, str], inputs: LoopInputs
) -> AsyncIterator[AnyEvent]:
	"""Continue a paused run by settling its approval batch, then take turns.

	The session validates ``answers`` against the pending batch before calling this.
	Each answer maps a tool_call_id to a decision: "Approve" runs the tool, "Deny"
	halts the run, any other text redirects the model.
	"""
	tools = _server_tools(inputs.config)
	ctx = _tool_context(inputs)
	denied = False
	for pending in approval.calls:
		_raise_if_aborted(inputs.abort)
		call = ToolCall(id=pending.id, name=pending.name, arguments=pending.args)
		answer = answers[pending.id]
		if answer == "Approve":
			result = await _finished_call(call, tools, ctx, inputs)
		elif answer == "Deny":
			result = _result(call, _DENIED, is_error=True)
			denied = True
		else:
			result = _result(call, _redirect(answer))
		_raise_if_aborted(inputs.abort)
		yield result

	if denied:  # a rejected action stops the run rather than continuing
		yield RunEnded(reason="done")
		return
	async for event in _loop(inputs):
		yield event


async def _loop(inputs: LoopInputs) -> AsyncIterator[AnyEvent]:
	"""The turn core shared by `run` and `resume`."""
	config, abort = inputs.config, inputs.abort
	model = inputs.model or await _authenticated_model(config, inputs.credentials, abort)
	tools = _server_tools(config)
	schemas = [tool.to_schema() for tool in tools.values()] + config.client_tools
	ctx = _tool_context(inputs)

	output_tokens = 0
	for _ in range(config.max_turns):
		_raise_if_aborted(abort)
		for text in _drain(inputs.next_steering):
			yield UserMessage(content=text)

		assistant: AssistantMessage | None = None
		request = ModelRequest(
			messages=inputs.messages,
			tools=schemas,
			system_prompt=config.system_prompt,
			stream=config.stream,
			cancellation=abort,
		)
		async for event in iterate_with_cancellation(model.run(request), abort):
			if isinstance(event, AssistantMessage):
				assistant = event
			elif isinstance(event, Usage):
				output_tokens += event.output_tokens
			yield event
		if assistant is None:
			raise RuntimeError("model stream ended without an assistant message")
		if assistant.stop_reason == "error":
			raise RuntimeError(assistant.error_message or "model response failed")
		if assistant.stop_reason == "aborted":
			yield RunEnded(reason="aborted")
			return

		if not assistant.tool_calls:
			steered = False
			for text in _drain(inputs.next_steering):
				steered = True
				yield UserMessage(content=text)
			if steered:
				continue
			yield RunEnded(reason="length" if assistant.stop_reason == "length" else "done")
			return

		if assistant.stop_reason == "length":
			# truncated arguments can still parse, so no call in this turn is safe to run
			for call in assistant.tool_calls:
				yield _result(call, _TRUNCATED, is_error=True)
		else:
			gated: list[PendingCall] = []
			for call in assistant.tool_calls:
				_raise_if_aborted(abort)
				async for event in _settle_call(call, tools, ctx, inputs, gated):
					yield event
			if gated:  # free tools already ran; now wait for the human
				_raise_if_aborted(abort)
				yield ApprovalRequired(calls=gated)
				yield RunEnded(reason="paused")
				return

		if output_tokens >= config.max_output_tokens:
			yield RunEnded(reason="budget")
			return

	yield RunEnded(reason="max_turns")


async def _settle_call(
	call: ToolCall,
	tools: dict[str, Tool],
	ctx: ToolContext,
	inputs: LoopInputs,
	gated: list[PendingCall],
) -> AsyncIterator[AnyEvent]:
	"""Settle one tool call: bad-args feedback, before-hook, confirm gate, dispatch.
	Appends to `gated` (deferred to approval) instead of running when confirm-gated."""
	if call.error:  # model emitted malformed args — feed the error back so it can retry
		yield _result(call, call.error, is_error=True)
		return

	if inputs.before_tool_call is not None:
		decision = await _maybe_await(inputs.before_tool_call(call, ctx), inputs.abort)
		_raise_if_aborted(inputs.abort)
		if decision is not None and decision.result is not None:
			yield _result(call, decision.result, is_error=decision.is_error)
			return
		if decision is not None and decision.args is not None:
			call = call.model_copy(update={"arguments": decision.args})

	if _needs_confirmation(inputs.config, call.name, tools):
		prompt = await _confirmation_prompt(call, tools, inputs)
		_raise_if_aborted(inputs.abort)
		gated.append(PendingCall(id=call.id, name=call.name, args=call.args, prompt=prompt))
		return

	yield await _finished_call(call, tools, ctx, inputs)


async def _finished_call(
	call: ToolCall, tools: dict[str, Tool], ctx: ToolContext, inputs: LoopInputs
) -> ToolResult:
	"""Dispatch one approved call and give the after-hook its say."""
	_raise_if_aborted(inputs.abort)
	result = await await_with_cancellation(_dispatch(call, tools, ctx, inputs), inputs.abort)
	_raise_if_aborted(inputs.abort)
	if inputs.after_tool_call is not None:
		rewritten = await _maybe_await(inputs.after_tool_call(call, result), inputs.abort)
		_raise_if_aborted(inputs.abort)
		if rewritten is not None:
			result = result.model_copy(update={"content": rewritten})
	return result


async def _dispatch(
	call: ToolCall, tools: dict[str, Tool], ctx: ToolContext, inputs: LoopInputs
) -> ToolResult:
	try:
		tool = tools.get(call.name)
		if tool is not None:
			outcome = await tool(**call.args, ctx=ctx)  # Tool.__call__ validates/coerces args
			return _result(call, outcome.content, is_error=outcome.is_error, details=outcome.details)
		if inputs.config.callback_url:
			response = await call_client(inputs.config, inputs.session_id, call, mode="execute")
			return _result(call, response.get("content", ""), is_error=bool(response.get("is_error", False)))
		return _result(call, f"[unknown tool: {call.name}]", is_error=True)
	except Exception as error:  # tool errors go back to the model, not the floor
		return _result(call, f"[tool error: {error}]", is_error=True)


async def _confirmation_prompt(call: ToolCall, tools: dict[str, Tool], inputs: LoopInputs) -> str:
	"""Build the human-facing approval prompt. Server tools may define their own via
	`Tool.confirm_prompt`; client tools can supply one over the callback; else generic."""
	tool = tools.get(call.name)
	if tool is not None and tool.confirm_prompt is not None:
		try:
			return tool.confirm_prompt(call.args)
		except Exception:
			pass
	if inputs.config.callback_url and call.name not in tools:
		try:
			response = await await_with_cancellation(
				call_client(inputs.config, inputs.session_id, call, mode="confirm"), inputs.abort
			)
			if response.get("prompt"):
				return response["prompt"]
		except ModelCancelled:
			raise
		except Exception:
			pass
	return f"Approve `{call.name}`?\n\n" + json.dumps(call.args, indent=2, default=str)


def _needs_confirmation(config: SessionConfig, name: str, tools: dict[str, Tool]) -> bool:
	if config.auto_approve:
		return False
	if name in config.confirm_tools:
		return True
	tool = tools.get(name)
	return bool(tool and tool.requires_confirmation)


async def _authenticated_model(
	config: SessionConfig, credentials: CredentialStore, abort: asyncio.Event
) -> Model:
	auth = await await_with_cancellation(
		resolve_model_auth(config.model, credentials, provider_id=config.credential_id),
		abort,
	)
	_raise_if_aborted(abort)
	return get_model(
		config.model,
		api_key=auth.api_key,
		api_base=auth.base_url,
		headers=auth.headers,
		refresh_auth=auth.refresh,
	)


def _server_tools(config: SessionConfig) -> dict[str, Tool]:
	return {name: BUILTIN_TOOLS[name] for name in config.tools if name in BUILTIN_TOOLS}


def _tool_context(inputs: LoopInputs) -> ToolContext:
	return ToolContext(cwd=inputs.config.cwd, allowed_roots=inputs.allowed_roots, abort=inputs.abort)


def _drain(next_steering: NextSteering | None) -> Iterator[str]:
	if next_steering is None:
		return
	while (text := next_steering()) is not None:
		yield text


def _redirect(feedback: str) -> str:
	return json.dumps(
		{
			"status": "redirect",
			"message": "Tool not executed.",
			"user_feedback": feedback,
			"instruction": "The user wants changes before this proceeds. Adjust and try again.",
		}
	)


def _result(
	call: ToolCall, content: str, *, is_error: bool = False, details: dict | None = None
) -> ToolResult:
	return ToolResult(
		tool_call_id=call.id, name=call.name, content=content, is_error=is_error, details=details or {}
	)


async def _maybe_await(value: Any, abort: asyncio.Event) -> Any:
	return await await_with_cancellation(value, abort) if inspect.isawaitable(value) else value


def _raise_if_aborted(abort: asyncio.Event) -> None:
	if abort.is_set():
		raise ModelCancelled
