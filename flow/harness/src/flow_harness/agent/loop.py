"""The agent loop: ask the model, run the tools it asks for, repeat — until it stops
calling tools or calls only tools that end the run, a cap trips, or a gated tool pauses the run.

`run` and `resume` only yield events and raise errors. The session saves them as they
arrive, so the transcript the loop reads for the next model call is always current.

A tool call can be intercepted three ways, and they do different jobs:
  - `before_tool_call` / `after_tool_call`: plain in-process callbacks, never saved.
    `before` can change the arguments or answer the call itself; `after` can rewrite
    the result.
  - extension tool hooks (`inputs.extension_runtime`): block a call or rewrite its arguments
    before the confirm gate — so an approval prompt always shows what will actually
    run — and rewrite its result after it ran. A resumed approval re-checks blocking
    only: the approved arguments are never rewritten behind the approval.
  - the confirm gate: the durable pause. A gated call is not run — the loop finishes
    the turn, yields `ApprovalRequired` + `RunEnded(reason="paused")`, and returns.
    The pause is in the log, so `resume` can arrive later, from any client, even
    after a restart.

Order per call: bad arguments, before hook, extension hooks, confirm gate, then run it,
before the next call is looked at. Consecutive calls of tools marked `concurrent` are the
exception: they are held and run together once a call of another kind, or the end of the
turn's calls, follows.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, replace
from functools import partial
from typing import TYPE_CHECKING, Any

from flow_harness.agent.client_tools import call_client
from flow_harness.agent.compaction import (
	KEEP_RECENT_TOKENS,
	CompactionPlan,
	calculate_compaction_input_limit,
	compact_events,
	estimate_context_tokens,
	estimate_message_tokens,
	plan_all,
	plan_keep_recent,
)
from flow_harness.events import (
	AnyEvent,
	ApprovalRequired,
	AssistantMessage,
	AttachmentContent,
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
from flow_harness.extensions.hooks import PreToolUseDecision
from flow_harness.model import Model, ModelRequest, ProviderError, get_model
from flow_harness.model.auth import resolve_model_auth
from flow_harness.model.cancellation import ModelCancelled, await_with_cancellation, iterate_with_cancellation
from flow_harness.model.credentials import CredentialStore
from flow_harness.model.reasoning import reasoning_params
from flow_harness.session.config import SessionConfig
from flow_harness.session.transcript import PendingApproval
from flow_harness.tools import SubagentOutcome, Tool, ToolContext
from flow_harness.tools.builtins.common import DEFAULT_MAX_BYTES, DEFAULT_MAX_LINES, truncate
from flow_harness.tools.tool import display_template_variables

if TYPE_CHECKING:
	from flow_harness.extensions import ExtensionRuntime


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


@dataclass
class TokenBudget:
	"""What a run may spend, shared by a session and the sub-agents inside it.

	Attributes:
		limit: Ceiling on the running total; None for no ceiling.
		spent: Fresh input and output tokens so far. Adapters report cache reads
			within the input count, and providers discount them heavily, so they
			are taken back out; cache creation stays in, since it is charged.
	"""

	limit: int | None
	spent: int = 0

	def add(self, usage: Usage) -> None:
		self.spent += max(usage.input_tokens - usage.cache_read_tokens, 0) + usage.output_tokens

	@property
	def exhausted(self) -> bool:
		return self.limit is not None and self.spent >= self.limit


@dataclass(frozen=True)
class LoopInputs:
	"""Everything a run needs from its session, prepared once at admission.

	``messages`` is the live provider-facing transcript the session's reducer
	maintains; the loop only reads it. A child has its own config copy, but its
	approval gate reads the session's live approval mode through ``approval_config``.
	"""

	config: SessionConfig
	messages: list[TranscriptMessage]
	credential_store: CredentialStore
	abort: asyncio.Event
	model_name: str  # the session's effective selection at admission, not config
	credential_id: str | None = None
	reasoning_effort: ReasoningEffort | None = None
	approval_config: SessionConfig | None = None
	allowed_roots: tuple[str, ...] = ()
	ignore_hidden_files: bool = False
	read_only_roots: tuple[str, ...] = ()
	session_id: str = ""
	model: Model | None = None
	context_tokens: int | None = None
	context_message_count: int = 0
	next_steering: NextSteering | None = None
	before_tool_call: BeforeHook | None = None
	after_tool_call: AfterHook | None = None
	resolve_attachment: Callable[[str], bytes] | None = None
	store_image: Callable[[str, bytes], Awaitable[AttachmentContent]] | None = None
	run_subagent: (
		Callable[[LoopInputs, str, str, str | None, str | None], Awaitable[SubagentOutcome]] | None
	) = None
	server_tools: dict[str, Tool] | None = None
	extension_runtime: ExtensionRuntime | None = None
	budget: TokenBudget | None = None


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
		params=reasoning_params(inputs.model_name, inputs.reasoning_effort),
	):
		yield event
	yield RunEnded(reason="done")


async def resume(
	approval: PendingApproval, answers: dict[str, str], inputs: LoopInputs
) -> AsyncIterator[AnyEvent]:
	"""Continue a paused run by settling its approval batch, then take turns unless that
	turn ends the run.

	The session validates ``answers`` against the pending batch before calling this.
	Each answer maps a tool_call_id to a decision: "Approve" runs the tool, "Deny"
	halts the run, any other text redirects the model.
	"""
	yield RunStarted(run_id=uuid.uuid4().hex[:12])
	tools = inputs.server_tools or {}
	ctx = _tool_context(inputs)
	denied = redirected = False
	for pending in approval.calls:
		_raise_if_aborted(inputs.abort)
		call = ToolCall(id=pending.id, name=pending.name, arguments=pending.args)
		answer = answers[pending.id]
		if answer == "Approve":
			# A gate added since the pause still gets its veto; the approved arguments
			# run exactly as approved, so a resume-time rewrite is ignored.
			verdict = await _hook_verdict(call, ctx, inputs)
			if verdict.block:
				result = _result(call, _blocked(verdict.reason), is_error=True)
			else:
				result = await _finished_call(call, tools, ctx, inputs)
		elif answer == "Deny":
			result = _result(call, _DENIED, is_error=True)
			denied = True
		else:
			result = _result(call, _redirect(answer))
			redirected = True
		_raise_if_aborted(inputs.abort)
		yield result

	if denied:  # a rejected action stops the run rather than continuing
		yield RunEnded(reason="denied")
		return
	if not redirected and _turn_ends_run(inputs.messages, tools):
		steered = False
		for message in _drain(inputs.next_steering):
			steered = True
			yield message
		if not steered:
			yield RunEnded(reason="done")
			return
	async for event in _loop(inputs):
		yield event


async def _loop(inputs: LoopInputs) -> AsyncIterator[AnyEvent]:
	"""The turn core shared by `run` and `resume`."""
	config, abort = inputs.config, inputs.abort
	model = inputs.model or await _authenticated_model(inputs)
	params = reasoning_params(inputs.model_name, inputs.reasoning_effort)
	if config.auto_compact:
		await model.load_model_limits(abort)
	tools = inputs.server_tools or {}
	schemas = [tool.to_schema() for tool in tools.values()]
	tool_display_templates = {
		tool.name: tool.display_template for tool in tools.values() if tool.display_template is not None
	}
	for client_tool in config.client_tools:  # its display template is for the UI, not the model
		schemas.append({key: value for key, value in client_tool.items() if key != "display_template"})
		if template := client_tool.get("display_template"):
			try:
				display_template_variables(template)
			except (TypeError, ValueError):
				continue  # a malformed one would end the run when rendered
			tool_display_templates[client_tool["function"]["name"]] = template
	ctx = _tool_context(inputs)

	budget = inputs.budget or TokenBudget(config.token_budget)
	context = _ContextTracker(
		usage_tokens=inputs.context_tokens,
		usage_message_count=inputs.context_message_count,
	)
	for _ in range(config.max_turns):
		_raise_if_aborted(abort)
		for message in _drain(inputs.next_steering):
			yield message

		async for event in _auto_compact(model, inputs, schemas, context):
			if isinstance(event, Usage):
				budget.add(event)
			yield event
		if budget.exhausted:
			yield RunEnded(reason="budget")
			return

		assistant: AssistantMessage | None = None
		request = ModelRequest(
			messages=inputs.messages,
			tools=schemas,
			tool_display_templates=tool_display_templates,
			system_prompt=config.system_prompt or "",
			stream=config.stream,
			cancellation=abort,
			resolve_attachment=inputs.resolve_attachment,
			params=params,
		)
		async for event in _model_turn(model, request, inputs, context):
			if isinstance(event, AssistantMessage):
				assistant = event
			elif isinstance(event, Usage):
				budget.add(event)
				if not event.standalone:
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

		ends_run = not assistant.tool_calls
		if assistant.tool_calls and assistant.stop_reason == "length":
			# truncated arguments can still parse, so no call in this turn is safe to run
			for call in assistant.tool_calls:
				yield _result(call, _TRUNCATED, is_error=True)
		elif assistant.tool_calls:
			gated: list[PendingCall] = []
			async for event in _settle_calls(assistant.tool_calls, tools, ctx, inputs, gated):
				yield event
			if gated:  # free tools already ran; now wait for the human
				_raise_if_aborted(abort)
				yield ApprovalRequired(calls=gated)
				yield RunEnded(reason="paused")
				return
			ends_run = _turn_ends_run(inputs.messages, tools)

		if ends_run:
			steered = False
			for message in _drain(inputs.next_steering):
				steered = True
				yield message
			if steered:
				continue
			yield RunEnded(reason="length" if assistant.stop_reason == "length" else "done")
			return

		if budget.exhausted:
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
		params=reasoning_params(inputs.model_name, inputs.reasoning_effort),
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


async def _settle_calls(
	calls: tuple[ToolCall, ...],
	tools: dict[str, Tool],
	ctx: ToolContext,
	inputs: LoopInputs,
	gated: list[PendingCall],
) -> AsyncIterator[AnyEvent]:
	"""Settle one turn's tool calls in order: hooks, the gate, then the run. Consecutive
	`concurrent` tools are held and run together; a gated call lands in `gated` for the
	approval pause instead of running."""
	batch: list[tuple[ToolCall, bool]] = []
	for call in calls:
		_raise_if_aborted(inputs.abort)
		if batch and not _concurrent(call, tools):  # a plain call waits for the held batch to finish
			async for result in _run_batch(batch, tools, ctx, inputs):
				yield result
			batch = []
		runnable: list[tuple[ToolCall, bool]] = []
		async for event in _settle_call(call, tools, ctx, inputs, gated, runnable):
			yield event
		if not runnable:
			continue
		if _concurrent(call, tools):
			batch.append(runnable[0])
		else:
			yield await _run_call(*runnable[0], tools, ctx, inputs)
	if batch:
		async for result in _run_batch(batch, tools, ctx, inputs):
			yield result


def _concurrent(call: ToolCall, tools: dict[str, Tool]) -> bool:
	tool = tools.get(call.name)
	return tool is not None and tool.concurrent


async def _run_batch(
	batch: list[tuple[ToolCall, bool]], tools: dict[str, Tool], ctx: ToolContext, inputs: LoopInputs
) -> AsyncIterator[ToolResult]:
	"""Run a batch together, yielding each result as it lands; leaving early cancels the rest."""
	tasks = [asyncio.create_task(_run_call(call, rewritten, tools, ctx, inputs)) for call, rewritten in batch]
	try:
		for finished in asyncio.as_completed(tasks):
			yield await finished
	finally:
		for task in tasks:
			task.cancel()
		await asyncio.gather(*tasks, return_exceptions=True)


async def _run_call(
	call: ToolCall, rewritten: bool, tools: dict[str, Tool], ctx: ToolContext, inputs: LoopInputs
) -> ToolResult:
	result = await _finished_call(call, tools, ctx, inputs)
	if rewritten:  # the durable ToolCall keeps the model's arguments; record what ran
		result = result.model_copy(
			update={"details": {**result.details, "effective_arguments": dict(call.args)}}
		)
	return result


async def _settle_call(
	call: ToolCall,
	tools: dict[str, Tool],
	ctx: ToolContext,
	inputs: LoopInputs,
	gated: list[PendingCall],
	runnable: list[tuple[ToolCall, bool]],
) -> AsyncIterator[AnyEvent]:
	"""Take one tool call up to its run: bad-args feedback, before-hook, extension hooks,
	confirm gate. A call that may run lands in `runnable` with its rewritten flag; a
	confirm-gated one in `gated`."""
	if call.error:  # model emitted malformed args — feed the error back so it can retry
		yield _result(call, call.error, is_error=True)
		return

	if inputs.before_tool_call is not None:
		decision = await _maybe_await(inputs.before_tool_call(call, ctx), inputs.abort)
		_raise_if_aborted(inputs.abort)
		if decision is not None and decision.result is not None:
			yield _capped(_result(call, decision.result, is_error=decision.is_error))
			return
		if decision is not None and decision.args is not None:
			call = call.model_copy(update={"arguments": decision.args})

	# Extension hooks run before the gate so an approval prompt (and the durable
	# PendingCall) always shows the arguments that will actually run.
	rewritten = False
	verdict = await _hook_verdict(call, ctx, inputs)
	if verdict.block:
		yield _result(call, _blocked(verdict.reason), is_error=True)
		return
	if verdict.arguments is not None:
		call = call.model_copy(update={"arguments": dict(verdict.arguments)})
		rewritten = True

	if _needs_confirmation(inputs, call.name, tools):
		prompt = await _confirmation_prompt(call, tools, inputs)
		_raise_if_aborted(inputs.abort)
		gated.append(PendingCall(id=call.id, name=call.name, args=call.args, prompt=prompt))
		return
	runnable.append((call, rewritten))


async def _hook_verdict(call: ToolCall, ctx: ToolContext, inputs: LoopInputs) -> PreToolUseDecision:
	"""One extension `tool_call` dispatch; an empty verdict when no extension hooks exist."""
	if inputs.extension_runtime is None or not inputs.extension_runtime.has_tool_hooks:
		return PreToolUseDecision()
	verdict = await await_with_cancellation(
		inputs.extension_runtime.run_tool_call_hooks(call, ctx), inputs.abort
	)
	_raise_if_aborted(inputs.abort)
	return verdict


async def _finished_call(
	call: ToolCall, tools: dict[str, Tool], ctx: ToolContext, inputs: LoopInputs
) -> ToolResult:
	"""Dispatch one approved call, run extension result hooks, give the after-hook its say."""
	_raise_if_aborted(inputs.abort)
	result = await await_with_cancellation(_dispatch(call, tools, ctx, inputs), inputs.abort)
	_raise_if_aborted(inputs.abort)
	dispatched = result.content
	if inputs.extension_runtime is not None and inputs.extension_runtime.has_tool_hooks:
		result = await await_with_cancellation(
			inputs.extension_runtime.run_tool_result_hooks(call, result), inputs.abort
		)
		_raise_if_aborted(inputs.abort)
	if inputs.after_tool_call is not None:
		rewritten = await _maybe_await(inputs.after_tool_call(call, result), inputs.abort)
		_raise_if_aborted(inputs.abort)
		if rewritten is not None:
			result = result.model_copy(update={"content": rewritten})
	return _capped(result, changed=result.content != dispatched)


async def _dispatch(
	call: ToolCall, tools: dict[str, Tool], ctx: ToolContext, inputs: LoopInputs
) -> ToolResult:
	try:
		tool = tools.get(call.name)
		if tool is not None:
			# Tool.__call__ validates/coerces args; the context names the call for tools that need it
			outcome = await tool(**call.args, ctx=replace(ctx, tool_call_id=call.id))
			return _result(
				call,
				outcome.content,
				is_error=outcome.is_error,
				details=outcome.details,
				attachments=outcome.attachments,
			)
		if inputs.config.callback_url:
			response = await call_client(inputs.config, inputs.session_id, call, mode="execute")
			return _result(call, response.get("content", ""), is_error=bool(response.get("is_error", False)))
		return _result(call, f"[unknown tool: {call.name}]", is_error=True)
	except Exception as error:  # tool errors go back to the model, not the floor
		return _result(call, f"[tool error: {error}]", is_error=True)


def _capped(result: ToolResult, *, changed: bool = False) -> ToolResult:
	"""Cut an oversized result to its start and end, unless its tool already cut it and
	no hook changed it."""
	if "truncation" in result.details and not changed:
		return result
	_, truncation = truncate(result.content, keep="head")
	if not truncation["truncated"]:
		return result
	lines, size = DEFAULT_MAX_LINES // 5, DEFAULT_MAX_BYTES // 5  # the end gets a fifth of the budget
	head, head_cut = truncate(result.content, keep="head", max_lines=lines * 4, max_bytes=size * 4)
	tail, tail_cut = truncate(result.content, keep="tail", max_lines=lines, max_bytes=size)
	note = (
		f"[Cut the middle: showing the first {_size(len(head.encode()))} and the last "
		f"{_size(len(tail.encode()))} of {_size(truncation['total_bytes'])}. "
		"To see more, call again asking for less: fewer fields, filters, a limit or a count. "
		"Don't repeat a call that changed data.]"
	)
	shown = head_cut["output_lines"] + tail_cut["output_lines"]
	truncation["output_lines"] = min(shown, truncation["total_lines"])  # both ends may hold part of one line
	return result.model_copy(
		update={
			"content": f"{head}\n\n{note}\n\n{tail}",
			"details": {**result.details, "truncation": truncation},
		}
	)


def _size(n: int) -> str:
	return f"{n / 1024**2:.1f} MB" if n >= 1024**2 else f"{max(1, round(n / 1024))} KB"


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


def _needs_confirmation(inputs: LoopInputs, name: str, tools: dict[str, Tool]) -> bool:
	"""Approval mode is the session's live setting; the confirm list is the run's own."""
	if (inputs.approval_config or inputs.config).auto_approve:
		return False
	if name in inputs.config.confirm_tools:
		return True
	tool = tools.get(name)
	return bool(tool and tool.requires_confirmation)


async def _authenticated_model(inputs: LoopInputs) -> Model:
	auth = await await_with_cancellation(
		resolve_model_auth(
			inputs.model_name,
			inputs.credential_store,
			provider_id=inputs.credential_id,
			api_key=inputs.config.api_key,
			api_base=inputs.config.api_base,
		),
		inputs.abort,
	)
	_raise_if_aborted(inputs.abort)
	return get_model(
		inputs.model_name,
		api_key=auth.api_key,
		api_base=auth.base_url,
		headers=auth.headers,
		params=inputs.config.model_params,
		refresh_auth=auth.refresh,
	)


def _tool_context(inputs: LoopInputs) -> ToolContext:
	return ToolContext(
		cwd=inputs.config.cwd,
		allowed_roots=inputs.allowed_roots,
		ignore_hidden_files=inputs.ignore_hidden_files,
		read_only_roots=inputs.read_only_roots,
		abort=inputs.abort,
		store_image=inputs.store_image,
		# the runner needs this run's inputs; a tool only names the call, task, agent and child
		run_subagent=partial(inputs.run_subagent, inputs) if inputs.run_subagent is not None else None,
	)


def _turn_ends_run(messages: list[TranscriptMessage], tools: dict[str, Tool]) -> bool:
	"""Whether the newest turn called only tools that end the run, none of them failing."""
	for message in reversed(messages):
		if isinstance(message, ToolResult) and message.is_error:
			return False
		if isinstance(message, AssistantMessage):
			return all(call.name in tools and tools[call.name].ends_run for call in message.tool_calls)
	return False


def _drain(next_steering: NextSteering | None) -> Iterator[UserMessage]:
	if next_steering is None:
		return
	while (text := next_steering()) is not None:
		yield text


def _blocked(reason: str | None) -> str:
	return json.dumps({"status": "blocked", "message": reason or "Blocked by an extension."})


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
	call: ToolCall,
	content: str,
	*,
	is_error: bool = False,
	details: dict | None = None,
	attachments: list[AttachmentContent] | None = None,
) -> ToolResult:
	return ToolResult(
		tool_call_id=call.id,
		name=call.name,
		content=content,
		is_error=is_error,
		details=details or {},
		attachments=attachments or [],
	)


async def _maybe_await(value: Any, abort: asyncio.Event) -> Any:
	return await await_with_cancellation(value, abort) if inspect.isawaitable(value) else value


def _raise_if_aborted(abort: asyncio.Event) -> None:
	if abort.is_set():
		raise ModelCancelled
