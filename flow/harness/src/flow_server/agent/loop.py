"""The agent loop: model call -> tool calls -> observe -> repeat, until the model
stops calling tools, a cap trips, or a confirmation-gated tool pauses the run.

Two independent, deliberately separate interception layers (see the hooks-vs-resume
design note — neither substitutes for the other):
  - `before_tool_call` / `after_tool_call`: optional in-process Python callables passed
    straight into run()/resume(). Fire on every tool call, never serialized over the
    wire, resolve synchronously (no durability). `before` can rewrite args or
    short-circuit with a synthetic result (a `HookDecision`); `after` can rewrite the
    result content (post-processing/redaction). The daemon may install its own defaults;
    an embedded caller (the TUI) can supply its own.
  - `confirm_tools` + `ApprovalRequired` + `resume`: the durable pause. A gated call is
    NOT executed; the loop finishes the rest of the turn, emits `ApprovalRequired`, and
    stops with reason "paused". The pause is a fact in the durable log, so
    `resume(answers)` can arrive much later, from any client, after a disconnect or a
    daemon restart.

Dispatch order per call: `before_tool_call` runs first (may block/rewrite/short-circuit);
if it lets the call through and the tool is confirm-gated, the durable pause takes over.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from flow_server.events import (
	ApprovalRequired,
	AssistantMessage,
	PendingCall,
	RunEnded,
	RunError,
	RunStarted,
	ToolCall,
	ToolResult,
	Usage,
	UserMessage,
)
from flow_server.model import Model, get_model
from flow_server.model.resolver import resolve_model_auth
from flow_server.session.store import PendingApproval, Session, pending_approval
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
RunReason = Literal["done", "length", "max_turns", "budget", "aborted", "error", "paused"]


class ResumeError(ValueError):
	"""The requested continuation does not match the current approval batch."""


async def run(
	session: Session,
	user_message: str,
	*,
	model: Model | None = None,
	before_tool_call: BeforeHook | None = None,
	after_tool_call: AfterHook | None = None,
) -> None:
	"""Start a new turn."""

	async def operation() -> RunReason:
		session.abort.clear()
		session.publish(RunStarted(run_id=uuid.uuid4().hex[:12]))
		_add_user(session, user_message)
		return await _loop(session, model, before_tool_call, after_tool_call)

	await _run_with_lifecycle(session, operation())


async def resume(
	session: Session,
	answers: dict[str, str],
	*,
	approval_seq: int | None = None,
	model: Model | None = None,
	before_tool_call: BeforeHook | None = None,
	after_tool_call: AfterHook | None = None,
) -> None:
	"""Continue a paused run. `answers` maps a pending tool_call_id to a decision:
	"Approve" runs the tool, "Deny" halts the run, any other text redirects the model."""
	approval = pending_approval(session.log)
	validate_resume(approval, approval_seq, answers)
	assert approval is not None  # narrowed by validate_resume
	pending = approval.calls

	async def operation() -> RunReason:
		session.abort.clear()
		server_tools = _server_tools(session)
		ctx = _make_ctx(session)
		denied = False
		for call in pending:
			answer = answers[call.id]
			tc = ToolCall(id=call.id, name=call.name, arguments=call.args)
			if answer == "Approve":
				result = await _run_one_tool(session, tc, server_tools, ctx, after_tool_call)
			elif answer == "Deny":
				result = _result(tc, _DENIED, is_error=True)
				denied = True
			else:
				result = _result(tc, _redirect(answer))
			_emit_result(session, result)

		if denied:  # a rejected action stops the run rather than continuing
			return "done"
		return await _loop(session, model, before_tool_call, after_tool_call)

	await _run_with_lifecycle(session, operation())


async def _run_with_lifecycle(session: Session, operation: Awaitable[RunReason]) -> None:
	"""Convert operation failures into one terminal protocol sequence.

	Runtime state cleanup belongs to ``Session._run_operation``. This layer owns
	durable transcript repair plus ``RunError``/``RunEnded`` publication so setup,
	hooks, model iteration, and continuation failures settle like normal runs.
	"""
	reason: RunReason = "error"
	failures: list[BaseException] = []
	cancelled: asyncio.CancelledError | None = None
	try:
		reason = await operation
	except asyncio.CancelledError as exc:
		reason = "aborted"
		cancelled = exc
	except Exception as exc:
		failures.append(exc)

	if reason != "paused":
		try:
			session.repair_interrupted_transcript()
		except Exception as exc:
			failures.append(exc)

	if failures:
		reason = "error"
		message = "; ".join(f"{type(exc).__name__}: {exc}" for exc in failures)
		try:
			session.publish(RunError(message=message))
		finally:
			session.publish(RunEnded(reason=reason))
	else:
		session.publish(RunEnded(reason=reason))

	if cancelled is not None:
		raise cancelled


async def _loop(
	session: Session,
	model: Model | None,
	before_tool_call: BeforeHook | None,
	after_tool_call: AfterHook | None,
) -> RunReason:
	cfg = session.config
	if model is None:
		auth = await resolve_model_auth(
			cfg.model,
			session.credentials,
			credential_id=cfg.credential_id,
		)
		model = get_model(
			cfg.model,
			api_key=auth.api_key,
			api_base=auth.base_url,
			headers=auth.headers,
		)
	server_tools = _server_tools(session)
	tool_schemas = [t.to_schema() for t in server_tools.values()] + cfg.client_tools
	ctx = _make_ctx(session)

	output_tokens = 0
	for _ in range(cfg.max_turns):
		_drain_steering(session)
		if session.abort.is_set():
			return "aborted"

		assistant, used = await _model_call(session, model, tool_schemas)
		if assistant is None:
			raise RuntimeError("model stream ended without an assistant message")
		session.messages.append(assistant)
		output_tokens += used
		if assistant.stop_reason == "error":
			raise RuntimeError(assistant.error_message or "model response failed")
		if assistant.stop_reason == "aborted":
			return "aborted"
		if not assistant.tool_calls:
			if _drain_steering(session):
				continue
			return "length" if assistant.stop_reason == "length" else "done"

		pending: list[PendingCall] = []
		for tc in assistant.tool_calls:
			await _handle_call(session, tc, server_tools, ctx, before_tool_call, after_tool_call, pending)
		if pending:  # non-gated tools already ran; now wait for approval
			session.publish(ApprovalRequired(calls=pending))
			return "paused"

		if output_tokens >= cfg.max_output_tokens:
			return "budget"
		if session.abort.is_set():
			return "aborted"

	return "max_turns"


async def _handle_call(
	session: Session,
	tc: ToolCall,
	server_tools: dict[str, Tool],
	ctx: ToolContext,
	before: BeforeHook | None,
	after: AfterHook | None,
	pending: list[PendingCall],
) -> None:
	"""Process one tool call: bad-args feedback, before-hook, confirm gate, then dispatch.
	Appends to `pending` (deferred to approval) instead of running when confirm-gated."""
	if tc.error:  # model emitted malformed args — feed the error back so it can retry
		_emit_result(session, _result(tc, tc.error, is_error=True))
		return

	if before is not None:
		# `before` hook must return `HookDecision | None` (sync or async), not a raw dict/string
		decision = await _maybe_await(before(tc, ctx))
		if decision is not None and decision.result is not None:
			_emit_result(session, _result(tc, decision.result, is_error=decision.is_error))
			return
		if decision is not None and decision.args is not None:
			tc = tc.model_copy(update={"arguments": decision.args})

	if _needs_confirm(session.config, tc.name, server_tools):
		prompt = await _confirm_prompt(session, tc, server_tools)
		pending.append(PendingCall(id=tc.id, name=tc.name, args=tc.args, prompt=prompt))
		return

	_emit_result(session, await _run_one_tool(session, tc, server_tools, ctx, after))


async def _model_call(
	session: Session, model: Model, tool_schemas: list[dict]
) -> tuple[AssistantMessage | None, int]:
	cfg = session.config
	assistant: AssistantMessage | None = None
	output_tokens = 0
	async for ev in model.run(
		session.messages,
		tool_schemas,
		system_prompt=cfg.system_prompt,
		stream=cfg.stream,
	):
		if isinstance(ev, AssistantMessage):
			assistant = ev
		elif isinstance(ev, Usage):
			output_tokens = ev.output_tokens
		session.publish(ev)  # assistant/usage are durable; text/tool-call deltas are live-only
	return assistant, output_tokens


# --- tool dispatch & confirmation ----------------------------------------

_DENIED = json.dumps({"status": "denied", "message": "User denied this tool call."})


def _redirect(feedback: str) -> str:
	return json.dumps(
		{
			"status": "redirect",
			"message": "Tool not executed.",
			"user_feedback": feedback,
			"instruction": "The user wants changes before this proceeds. Adjust and try again.",
		}
	)


def _result(tc: ToolCall, content: str, *, is_error: bool = False, details: dict | None = None) -> ToolResult:
	return ToolResult(
		tool_call_id=tc.id, name=tc.name, content=content, is_error=is_error, details=details or {}
	)


def _server_tools(session: Session) -> dict[str, Tool]:
	return {n: BUILTIN_TOOLS[n] for n in session.config.tools if n in BUILTIN_TOOLS}


def _make_ctx(session: Session) -> ToolContext:
	return ToolContext(
		cwd=session.config.cwd,
		allowed_roots=session.allowed_roots,
		abort=session.abort,
	)


def _needs_confirm(cfg, name: str, server_tools: dict[str, Tool]) -> bool:
	if cfg.auto_approve:
		return False
	if cfg.confirm_tools:  # explicit session list overrides per-tool defaults
		return name in cfg.confirm_tools
	tool = server_tools.get(name)  # else fall back to the tool's own default
	return bool(tool and tool.requires_confirmation)


async def _run_one_tool(
	session: Session,
	tc: ToolCall,
	server_tools: dict[str, Tool],
	ctx: ToolContext,
	after: AfterHook | None,
) -> ToolResult:
	result = await _dispatch(session, tc, server_tools, ctx)
	if after is not None:
		new_content = await _maybe_await(after(tc, result))
		if new_content is not None:
			result = result.model_copy(update={"content": new_content})
	return result


async def _dispatch(
	session: Session, tc: ToolCall, server_tools: dict[str, Tool], ctx: ToolContext
) -> ToolResult:
	try:
		tool = server_tools.get(tc.name)
		if tool is not None:
			out = await tool(**tc.args, ctx=ctx)  # Tool.__call__ validates/coerces args
			return _result(tc, out.content, is_error=out.is_error, details=out.details)
		if session.config.callback_url:
			resp = await _call_client(session, tc, "execute")  # mode can be "execute" or "confirm"
			return _result(tc, resp.get("content", ""), is_error=bool(resp.get("is_error", False)))
		return _result(tc, f"[unknown tool: {tc.name}]", is_error=True)
	except Exception as e:  # tool errors go back to the model, not the floor
		return _result(tc, f"[tool error: {e}]", is_error=True)


async def _confirm_prompt(session: Session, tc: ToolCall, server_tools: dict[str, Tool]) -> str:
	"""Build the human-facing approval prompt. Server tools may define their own via
	`Tool.confirm_prompt`; client tools can supply one over the callback; else generic."""
	tool = server_tools.get(tc.name)
	if tool is not None and tool.confirm_prompt is not None:
		try:
			return tool.confirm_prompt(tc.args)
		except Exception:
			pass
	if session.config.callback_url and tc.name not in server_tools:
		try:
			resp = await _call_client(session, tc, "confirm")
			if resp.get("prompt"):
				return resp["prompt"]
		except Exception:
			pass
	return f"Approve `{tc.name}`?\n\n" + json.dumps(tc.args, indent=2, default=str)


async def _call_client(session: Session, tc: ToolCall, mode: str) -> dict:
	"""Dispatch to the client callback. mode="execute" runs a client-side tool;
	mode="confirm" asks the client for its approval prompt without running it."""
	url = session.config.callback_url
	if not url:
		raise RuntimeError(f"no callback_url configured; cannot dispatch client tool {tc.name!r}")
	payload = {
		"session_id": session.id,
		"tool": tc.name,
		"args": tc.args,
		"user_context": session.config.user_context,
		"mode": mode,
	}
	headers = {}
	if session.config.callback_token:
		headers["X-Harness-Token"] = session.config.callback_token
	async with httpx.AsyncClient(timeout=120) as client:
		resp = await client.post(url, json=payload, headers=headers)
		resp.raise_for_status()
		body = resp.json()
		# a client may wrap its return in an envelope (Frappe uses {"message": ...})
		if isinstance(body, dict) and isinstance(body.get("message"), dict):
			return body["message"]
		return body if isinstance(body, dict) else {}


# --- transcript / helpers -------------------------------------------------


def validate_resume(
	approval: PendingApproval | None,
	approval_seq: int | None,
	answers: dict[str, str],
) -> None:
	if approval is None:
		raise ResumeError("No tool calls are awaiting approval.")
	if approval_seq is not None and approval_seq != approval.seq:
		raise ResumeError(f"Approval batch {approval_seq} is stale; current batch is {approval.seq}.")

	expected = {call.id for call in approval.calls}
	if len(expected) != len(approval.calls):
		raise ResumeError("The pending approval batch contains duplicate tool-call ids.")
	supplied = set(answers)
	if supplied == expected:
		return

	missing = sorted(expected - supplied)
	extra = sorted(supplied - expected)
	details = []
	if missing:
		details.append(f"missing answers for: {', '.join(missing)}")
	if extra:
		details.append(f"unexpected answers for: {', '.join(extra)}")
	raise ResumeError("Answers must exactly match the pending tool calls (" + "; ".join(details) + ").")


def _emit_result(session: Session, result: ToolResult) -> None:
	session.publish(result)
	session.messages.append(result)


def _add_user(session: Session, content: str) -> None:
	message = UserMessage(content=content)
	session.publish(message)
	session.messages.append(message)


def _drain_steering(session: Session) -> bool:
	drained = False
	while not session.steer_queue.empty():
		_add_user(session, session.steer_queue.get_nowait())
		drained = True
	return drained


async def _maybe_await(value: Any) -> Any:
	return await value if inspect.isawaitable(value) else value
