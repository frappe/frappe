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

from flow.agent.client_tools import call_client
from flow.agent.compaction import (
	KEEP_RECENT_TOKENS,
	CompactionPlan,
	calculate_compaction_input_limit,
	compact_events,
	estimate_context_tokens,
	estimate_message_tokens,
	plan_all,
	plan_keep_recent,
)
from flow.events import (
	AnyEvent,
	ApprovalRequired,
	AssistantMessage,
	Compaction,
	CompactionReason,
	PendingCall,
	ReasoningEffort,
	Retry,
	RunEnded,
	RunStarted,
	ToolCall,
	ToolResult,
	TranscriptMessage,
	Usage,
	UserMessage,
)
from flow.model import Model, ModelRequest, ProviderError, get_model
from flow.model.auth import resolve_model_auth
from flow.model.base import ModelCancelled, await_with_cancellation, iterate_with_cancellation
from flow.model.credentials import CredentialStore
from flow.model.reasoning import reasoning_params
from flow.session.config import SessionConfig
from flow.session.transcript import PendingApproval
from flow.tools import Tool, ToolContext


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
NextSteering = Callable[[], UserMessage | None]


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
	model_name: str  # the session's effective selection at admission, not config
	credential_id: str | None = None
	reasoning_effort: ReasoningEffort | None = None
	allowed_roots: tuple[str, ...] = ()
	read_only_roots: tuple[str, ...] = ()
	session_id: str = ""
	model: Model | None = None
	context_tokens: int | None = None
	context_message_count: int = 0
	next_steering: NextSteering | None = None
	before_tool_call: BeforeHook | None = None
	after_tool_call: AfterHook | None = None
	resolve_attachment: Callable[[str], bytes] | None = None
	server_tools: dict[str, Tool] | None = None


_DENIED = json.dumps({"status": "denied", "message": "User denied this tool call."})
_ABORTED = json.dumps(
	{"status": "aborted", "message": "Tool not executed. The run was aborted before this call ran."}
)
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


async def run(message: UserMessage, inputs: LoopInputs) -> AsyncIterator[AnyEvent]:
	"""One new run: open the protocol, add the user message, then take turns."""
	yield RunStarted(run_id=uuid.uuid4().hex[:12])
	yield message
	async for event in _loop(inputs):
		yield event


async def compact(instructions: str | None, inputs: LoopInputs) -> AsyncIterator[AnyEvent]:
	"""One manual compaction as a full operation: summarize everything, fold, end."""
	yield RunStarted(run_id=uuid.uuid4().hex[:12])
	model = inputs.model or await _authenticated_model(inputs)
	await model.load_model_limits(inputs.abort)
	plan = plan_all(inputs.messages)
	if plan is None:
		raise RuntimeError("nothing to compact")
	async for event in compact_events(
		model,
		plan,
		compaction_reason="manual",
		cancellation=inputs.abort,
		summary_instructions=instructions,
		resolve_attachment=inputs.resolve_attachment,
	):
		yield event
	yield RunEnded(reason="done")


async def resume(
	approval: PendingApproval, answers: dict[str, str], inputs: LoopInputs
) -> AsyncIterator[AnyEvent]:
	"""Continue a paused run by settling its approval batch, then take turns.

	The session validates ``answers`` against the pending batch before calling this.
	Each answer maps a tool_call_id to a decision: "Approve" runs the tool, "Deny"
	halts the run, any other text redirects the model.
	"""
	tools = inputs.server_tools or {}
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
		yield RunEnded(reason="denied")
		return
	async for event in _loop(inputs):
		yield event


async def _loop(inputs: LoopInputs) -> AsyncIterator[AnyEvent]:
	"""The turn core shared by `run` and `resume`."""
	config, abort = inputs.config, inputs.abort
	model = inputs.model or await _authenticated_model(inputs)
	if config.auto_compact:
		await model.load_model_limits(abort)
	tools = inputs.server_tools or {}
	schemas = [tool.to_schema() for tool in tools.values()] + config.client_tools
	tool_display_templates = {
		tool.name: tool.display_template for tool in tools.values() if tool.display_template is not None
	}
	ctx = _tool_context(inputs)

	output_tokens = 0
	context = _ContextTracker(
		usage_tokens=inputs.context_tokens,
		usage_message_count=inputs.context_message_count,
	)
	for _ in range(config.max_turns):
		_raise_if_aborted(abort)
		for message in _drain(inputs.next_steering):
			yield message

		async for event in _auto_compact(model, inputs, schemas, context):
			yield event

		assistant: AssistantMessage | None = None
		request = ModelRequest(
			messages=inputs.messages,
			tools=schemas,
			tool_display_templates=tool_display_templates,
			system_prompt=config.system_prompt or "",
			stream=config.stream,
			cancellation=abort,
			resolve_attachment=inputs.resolve_attachment,
		)
		async for event in _model_turn(model, request, inputs, context):
			if isinstance(event, AssistantMessage):
				assistant = event
			elif isinstance(event, Usage):
				output_tokens += event.output_tokens
				context.observe_usage(event, len(inputs.messages))
				event = event.model_copy(update={"context_window": model.context_window})
			yield event
		if assistant is None:
			raise RuntimeError("model stream ended without an assistant message")
		if assistant.stop_reason == "error":
			raise RuntimeError(assistant.error_message or "model response failed")
		if assistant.stop_reason == "aborted":
			for call in assistant.tool_calls:  # close any calls the aborted turn carries
				yield _result(call, _ABORTED, is_error=True)
			yield RunEnded(reason="aborted")
			return

		if not assistant.tool_calls:
			steered = False
			for message in _drain(inputs.next_steering):
				steered = True
				yield message
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


async def _auto_compact(
	model: Model, inputs: LoopInputs, schemas: list[dict], context: _ContextTracker
) -> AsyncIterator[AnyEvent]:
	"""Compact before a model call when the active context crosses its threshold."""
	config = inputs.config
	if not config.auto_compact or context.just_compacted:
		return
	system_prompt = config.system_prompt or ""
	compaction_threshold_tokens = _compact_threshold(config, model)
	if context.tokens(system_prompt, schemas, inputs.messages) <= compaction_threshold_tokens:
		return
	plan = _plan_compaction_preserving_recent_messages(
		inputs,
		model,
		system_prompt=system_prompt,
		tools=schemas,
	)
	if plan is None:
		return
	try:
		async for event in _compact_once(model, inputs, plan, "threshold", context):
			yield event
	except ModelCancelled:
		raise
	except Exception:
		return


async def _model_turn(
	model: Model, request: ModelRequest, inputs: LoopInputs, context: _ContextTracker
) -> AsyncIterator[AnyEvent]:
	"""One model turn. The first context overflow in a run compacts once and retries;
	every other failure propagates untouched."""
	terminal_seen = False
	try:
		async for event in iterate_with_cancellation(model.run(request), inputs.abort):
			terminal_seen = terminal_seen or isinstance(event, AssistantMessage)
			yield event
		return
	except ProviderError as error:
		if not (
			inputs.config.auto_compact
			and error.kind == "context_overflow"
			and not terminal_seen
			and not context.overflow_used
		):
			raise
		context.overflow_used = True
		plan = _plan_compaction_preserving_recent_messages(
			inputs,
			model,
			system_prompt=request.system_prompt,
			tools=request.tools,
		)
		if plan is None:
			raise
		try:
			async for event in _compact_once(model, inputs, plan, "overflow", context):
				yield event
		except ModelCancelled:
			raise
		except Exception:
			raise error from None
	# The failed request may already have streamed deltas. This is the existing UI
	# boundary that tells consumers to discard them before rendering the retry.
	yield Retry(status="started", attempt=2, max_attempts=2, kind="context_overflow")
	# the fold already shrank request.messages in place
	try:
		async for event in iterate_with_cancellation(model.run(request), inputs.abort):
			yield event
	except ProviderError as error:
		yield Retry(status="exhausted", attempt=2, kind=error.kind)
		raise


def _plan_compaction_preserving_recent_messages(
	inputs: LoopInputs,
	model: Model,
	*,
	system_prompt: str,
	tools: list[dict] | None,
) -> CompactionPlan | None:
	"""Keep the normal 20k tail, scaled to the room messages actually have."""
	compaction_threshold_tokens = min(
		_compact_threshold(inputs.config, model),
		calculate_compaction_input_limit(model),
	)
	non_message_tokens = estimate_context_tokens(system_prompt, tools, ())
	message_threshold_tokens = max(1, compaction_threshold_tokens - non_message_tokens)
	# Small windows need a smaller tail and room for the summary itself.
	keep_recent_tokens = min(
		KEEP_RECENT_TOKENS,
		max(1, message_threshold_tokens // 4),
	)
	return plan_keep_recent(inputs.messages, keep_recent_tokens=keep_recent_tokens)


def _compact_threshold(config: SessionConfig, model: Model) -> int:
	if config.compact_threshold_tokens is not None:
		return config.compact_threshold_tokens
	if model.auto_compact_threshold_tokens is not None:
		return model.auto_compact_threshold_tokens
	return calculate_compaction_input_limit(model)


async def _compact_once(
	model: Model,
	inputs: LoopInputs,
	plan: CompactionPlan,
	reason: CompactionReason,
	context: _ContextTracker,
) -> AsyncIterator[AnyEvent]:
	"""Run one compaction and update context after its durable event."""
	async for event in compact_events(
		model,
		plan,
		compaction_reason=reason,
		cancellation=inputs.abort,
		resolve_attachment=inputs.resolve_attachment,
	):
		if isinstance(event, Compaction):
			context.mark_compacted()
		yield event


@dataclass
class _ContextTracker:
	"""Provider context usage plus guards that prevent compaction loops."""

	usage_tokens: int | None = None
	usage_message_count: int = 0
	just_compacted: bool = False
	overflow_used: bool = False

	def observe_usage(self, usage: Usage, message_count: int) -> None:
		# A completed model turn is enough to permit a later compaction even when the
		# provider omits token counts and yields an empty Usage event.
		self.just_compacted = False
		reported = usage.input_tokens + usage.output_tokens
		if reported > 0:
			self.usage_tokens = reported
			self.usage_message_count = message_count

	def mark_compacted(self) -> None:
		self.usage_tokens = None
		self.just_compacted = True

	def tokens(self, system_prompt: str, tools: list[dict], messages: list[TranscriptMessage]) -> int:
		if self.usage_tokens is None:
			return estimate_context_tokens(system_prompt, tools, messages)
		trailing = sum(estimate_message_tokens(m) for m in messages[self.usage_message_count :])
		return self.usage_tokens + trailing


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


async def _authenticated_model(inputs: LoopInputs) -> Model:
	auth = await await_with_cancellation(
		resolve_model_auth(inputs.model_name, inputs.credentials, provider_id=inputs.credential_id),
		inputs.abort,
	)
	_raise_if_aborted(inputs.abort)
	return get_model(
		inputs.model_name,
		api_key=auth.api_key,
		api_base=auth.base_url,
		headers=auth.headers,
		params=reasoning_params(inputs.model_name, inputs.reasoning_effort),
		refresh_auth=auth.refresh,
	)


def _tool_context(inputs: LoopInputs) -> ToolContext:
	return ToolContext(
		cwd=inputs.config.cwd,
		allowed_roots=inputs.allowed_roots,
		read_only_roots=inputs.read_only_roots,
		abort=inputs.abort,
	)


def _drain(next_steering: NextSteering | None) -> Iterator[UserMessage]:
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
