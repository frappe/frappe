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

import inspect
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

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
from flow_server.session.store import Session
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


async def run(
	session: Session,
	user_message: str,
	*,
	model: Model | None = None,
	before_tool_call: BeforeHook | None = None,
	after_tool_call: AfterHook | None = None,
) -> None:
	"""Start a new turn."""
	session.abort.clear()
	session.publish(RunStarted(run_id=uuid.uuid4().hex[:12]))
	_add_user(session, user_message)
	await _loop(session, model, before_tool_call, after_tool_call)


async def resume(
	session: Session,
	answers: dict[str, str],
	*,
	model: Model | None = None,
	before_tool_call: BeforeHook | None = None,
	after_tool_call: AfterHook | None = None,
) -> None:
	"""Continue a paused run. `answers` maps a pending tool_call_id to a decision:
	"Approve" runs the tool, "Deny" halts the run, any other text redirects the model."""
	session.abort.clear()
	pending = _pending_calls(session)
	if not pending:
		session.publish(RunError(message="No tool calls are awaiting approval."))
		session.publish(RunEnded(reason="error"))
		return

	server_tools = _server_tools(session)
	ctx = _make_ctx(session)
	denied = False
	for call in pending:
		answer = answers.get(call.id, "Deny")
		tc = ToolCall(id=call.id, name=call.name, args=call.args)
		if answer == "Approve":
			result = await _run_one_tool(session, tc, server_tools, ctx, after_tool_call)
		elif answer == "Deny":
			result = _result(tc, _DENIED, is_error=True)
			denied = True
		else:
			result = _result(tc, _redirect(answer))
		_emit_result(session, result)

	if denied:  # a rejected action stops the run rather than continuing
		session.publish(RunEnded(reason="done"))
		return
	await _loop(session, model, before_tool_call, after_tool_call)


async def _loop(
	session: Session,
	model: Model | None,
	before_tool_call: BeforeHook | None,
	after_tool_call: AfterHook | None,
) -> None:
	cfg = session.config
	if model is None:
		auth = await resolve_model_auth(
			cfg.model,
			session.credentials,
			explicit_api_key=cfg.api_key,
			credential_id=cfg.credential_id,
		)
		# OAuth providers own their endpoint. Allowing a session-level api_base to
		# override it could send a bearer token to an attacker-controlled host.
		api_base = auth.base_url if auth.is_oauth else cfg.api_base or auth.base_url
		model = get_model(
			cfg.model,
			api_key=auth.api_key,
			api_base=api_base,
			headers=auth.headers,
		)
	server_tools = _server_tools(session)
	tool_schemas = [t.to_schema() for t in server_tools.values()] + cfg.client_tools
	ctx = _make_ctx(session)

	output_tokens = 0
	reason = "max_turns"
	try:
		for _ in range(cfg.max_turns):
			_drain_steering(session)
			if session.abort.is_set():
				reason = "aborted"
				break

			assistant, used = await _model_call(session, model, tool_schemas)
			if assistant is None:
				reason = "error"
				break
			session.messages.append(_assistant_msg(assistant))
			output_tokens += used
			if not assistant.tool_calls:
				reason = "done"
				break

			pending: list[PendingCall] = []
			for tc in assistant.tool_calls:
				await _handle_call(
					session, tc, server_tools, ctx, before_tool_call, after_tool_call, pending
				)
			if pending:  # non-gated tools already ran; now wait for approval
				session.publish(ApprovalRequired(calls=pending))
				reason = "paused"
				break

			if output_tokens >= cfg.max_output_tokens:
				reason = "budget"
				break
			if session.abort.is_set():
				reason = "aborted"
				break
	except Exception as e:  # noqa: BLE001 — surface any loop failure as an event, never crash the daemon
		session.publish(RunError(message=f"{type(e).__name__}: {e}"))
		session.publish(RunEnded(reason="error"))
		return

	session.publish(RunEnded(reason=reason))


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
			tc = tc.model_copy(update={"args": decision.args})

	if _needs_confirm(session.config, tc.name, server_tools):
		prompt = await _confirm_prompt(session, tc, server_tools)
		pending.append(PendingCall(id=tc.id, name=tc.name, args=tc.args, prompt=prompt))
		return

	_emit_result(session, await _run_one_tool(session, tc, server_tools, ctx, after))


async def _model_call(
	session: Session, model: Model, tool_schemas: list[dict]
) -> tuple[AssistantMessage | None, int]:
	cfg = session.config
	messages = [{"role": "system", "content": cfg.system_prompt}] + session.messages
	assistant: AssistantMessage | None = None
	output_tokens = 0
	async for ev in model.run(messages, tool_schemas, stream=cfg.stream):
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


def _result(
	tc: ToolCall, content: str, *, is_error: bool = False, details: dict | None = None
) -> ToolResult:
	return ToolResult(
		tool_call_id=tc.id, name=tc.name, content=content, is_error=is_error, details=details or {}
	)


def _server_tools(session: Session) -> dict[str, Tool]:
	return {n: BUILTIN_TOOLS[n] for n in session.config.tools if n in BUILTIN_TOOLS}


def _make_ctx(session: Session) -> ToolContext:
	return ToolContext(cwd=session.config.cwd, abort=session.abort)


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
	except Exception as e:  # noqa: BLE001 — tool errors go back to the model, not the floor
		return _result(tc, f"[tool error: {e}]", is_error=True)


async def _confirm_prompt(session: Session, tc: ToolCall, server_tools: dict[str, Tool]) -> str:
	"""Build the human-facing approval prompt. Server tools may define their own via
	`Tool.confirm_prompt`; client tools can supply one over the callback; else generic."""
	tool = server_tools.get(tc.name)
	if tool is not None and tool.confirm_prompt is not None:
		try:
			return tool.confirm_prompt(tc.args)
		except Exception:  # noqa: BLE001
			pass
	if session.config.callback_url and tc.name not in server_tools:
		try:
			resp = await _call_client(session, tc, "confirm")
			if resp.get("prompt"):
				return resp["prompt"]
		except Exception:  # noqa: BLE001
			pass
	return f"Approve `{tc.name}`?\n\n" + json.dumps(tc.args, indent=2, default=str)


async def _call_client(session: Session, tc: ToolCall, mode: str) -> dict:
	"""Dispatch to the client callback. mode="execute" runs a client-side tool;
	mode="confirm" asks the client for its approval prompt without running it."""
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
		resp = await client.post(session.config.callback_url, json=payload, headers=headers)
		resp.raise_for_status()
		body = resp.json()
		# a client may wrap its return in an envelope (Frappe uses {"message": ...})
		if isinstance(body, dict) and isinstance(body.get("message"), dict):
			return body["message"]
		return body if isinstance(body, dict) else {}


# --- transcript / helpers -------------------------------------------------

def _pending_calls(session: Session) -> list[PendingCall]:
	"""The current unresolved approval batch, read from the durable log (survives restart,
	honors any before-hook arg rewrite baked into the ApprovalRequired event)."""
	resolved: set[str] = set()
	pending: list[PendingCall] = []
	for raw in session.log.read_since(0):
		t = raw.get("type")
		if t == "approval_required":
			pending = ApprovalRequired.model_validate(raw).calls
		elif t == "tool_result":
			resolved.add(raw.get("tool_call_id"))
	return [c for c in pending if c.id not in resolved]


def _emit_result(session: Session, result: ToolResult) -> None:
	session.publish(result)
	session.messages.append(_tool_msg(result))


def _add_user(session: Session, content: str) -> None:
	session.publish(UserMessage(content=content))
	session.messages.append({"role": "user", "content": content})


def _drain_steering(session: Session) -> None:
	while not session.steer_queue.empty():
		_add_user(session, session.steer_queue.get_nowait())


def _assistant_msg(msg: AssistantMessage) -> dict:
	out: dict = {"role": "assistant", "content": msg.text or None}
	if msg.provider_data:
		out["provider_data"] = msg.provider_data
	if msg.tool_calls:
		out["tool_calls"] = [
			{
				"id": tc.id,
				"type": "function",
				"function": {"name": tc.name, "arguments": json.dumps(tc.args)},
			}
			for tc in msg.tool_calls
		]
	return out


def _tool_msg(result: ToolResult) -> dict:
	return {"role": "tool", "tool_call_id": result.tool_call_id, "content": result.content}


async def _maybe_await(value: Any) -> Any:
	return await value if inspect.isawaitable(value) else value
