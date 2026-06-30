"""The single agentic loop for Studio AI.

`AgentRunner` holds the per-request state, builds the message list, and drives
one tool-calling loop until the model stops requesting server/terminal tools.
Tool *behaviour* lives in the registry; this file only orchestrates.

Realtime event contract (consumed by the frontend). Every event name is
suffixed with the page id, e.g. `ai_chat_stream_<page_id>`:

    ai_chat_progress    {message}
    ai_chat_stream      {chunk}      append to the chat reply text
    ai_chat_tool_batch  {operations: [{tool_name, args}]}   apply to the canvas
    ai_chat_complete    {message}
    ai_chat_error       {message}

All events also carry {page_id}.
"""

import json
import logging
import time

import frappe

from studio.ai import llm
from studio.ai.agent.registry import ToolRegistry, build_default_registry
from studio.ai.agent.tree import WorkingTree
from studio.ai.block_codec import BlockCodec
from studio.ai.models import ModelRegistry
from studio.ai.prompts import AGENT_SYSTEM
from studio.ai.session import AISession

logger = frappe.logger("studio.ai.agent.loop")
logger.setLevel(logging.INFO)

# One turn may span several rounds: server-tool reads plus a model that applies a
# change in batches. High enough to finish a big multi-block edit, bounded so a runaway
# loop can't spin.
MAX_ROUNDS = 40
EVENT_PREFIX = "ai_chat"

# A streaming round is retried on transient failure (litellm can't fall back mid-stream).
# Backoff is STREAM_BACKOFF_BASE * 2**attempt → ~1s, 2s before the final give-up.
STREAM_MAX_ATTEMPTS = 3
STREAM_BACKOFF_BASE = 1.0


class CancelledError(Exception):
	"""Raised inside the stream loop when the user cancels the turn."""


class AgentRunner:
	def __init__(
		self,
		prompt: str,
		page_context_json: str,
		model: str,
		api_key: str,
		*,
		user: str | None = None,
		page_id: str | None = None,
		session_id: str | None = None,
		selected_block_ids: list[str] | None = None,
		registry: ToolRegistry | None = None,
		system_prompt: str | None = None,
	):
		self.prompt = prompt
		self.page_context_json = page_context_json
		self.model = model
		self.api_key = api_key
		self.user = user or frappe.session.user
		self.page_id = page_id
		self.session_id = session_id
		self.selected_block_ids = selected_block_ids or []
		self.registry = registry or build_default_registry()
		self.system_prompt = system_prompt or AGENT_SYSTEM
		self.tree: WorkingTree | None = None

	# --- cancellation -----------------------------------------------------

	def _cancel_key(self) -> str | None:
		return f"studio_ai_cancel:{self.session_id}" if self.session_id else None

	def is_cancelled(self) -> bool:
		key = self._cancel_key()
		# use_local_cache=False is critical: the cancel is set by a DIFFERENT web worker,
		# and Frappe's per-request local cache would otherwise pin the first (miss) result.
		return bool(frappe.cache.get_value(key, use_local_cache=False)) if key else False

	def clear_cancel_flag(self) -> None:
		if key := self._cancel_key():
			frappe.cache.delete_value(key)

	def interruptible_sleep(self, seconds: float) -> None:
		"""Sleep in small steps so a cancel during retry backoff is honored within ~0.25s."""
		waited = 0.0
		while waited < seconds:
			if self.is_cancelled():
				raise CancelledError
			step = min(0.25, seconds - waited)
			time.sleep(step)
			waited += step

	# --- realtime ---------------------------------------------------------

	def emit(self, suffix: str, **kwargs):
		event = f"{EVENT_PREFIX}_{suffix}"
		if self.page_id:
			event = f"{event}_{self.page_id}"
		frappe.publish_realtime(event, {"page_id": self.page_id, **kwargs}, user=self.user)

	# --- message construction --------------------------------------------

	def _page_root(self) -> dict | None:
		"""Parse page_context_json into the root block dict, or None if empty/invalid."""
		try:
			data = json.loads(self.page_context_json)
		except (json.JSONDecodeError, TypeError):
			return None
		if isinstance(data, list):
			data = data[0] if data else None
		return data if isinstance(data, dict) else None

	def build_page_context(self) -> str:
		root = self._page_root()
		if root is None:
			return ""
		structure = BlockCodec.to_json(BlockCodec.compress(root))
		return f"Current page structure (JSON — pass a block's 'id' value as component_id to edit it):\n{structure}"

	def build_messages(self) -> list[dict]:
		messages: list[dict] = [
			{"role": "system", "content": self.system_prompt, "cache_control": {"type": "ephemeral"}},
		]
		if page_context_message := self.build_page_context():
			# Cache the page structure too (the system prompt is the other breakpoint): it's
			# the largest stable block, resent every round of a multi-round edit, so caching
			# it cuts both latency and input cost across the loop.
			messages.append(
				{"role": "user", "content": page_context_message, "cache_control": {"type": "ephemeral"}}
			)
			messages.append(
				{
					"role": "assistant",
					"content": "Understood. I have the current page structure. What would you like me to change?",
				}
			)
		# Prior conversation as proper role-tagged turns (the model handles dialogue better
		# and we save the "User:"/"Assistant:" prefix tokens on every call).
		messages.extend(AISession.build_context_messages_from_id(self.session_id))
		user_text = self.prompt
		if self.selected_block_ids:
			user_text += f"\n\n(User has selected: {', '.join(self.selected_block_ids)})"
		messages.append({"role": "user", "content": user_text})
		return messages

	# --- LLM call ---------------------------------------------------------

	def call_tool_llm(self, messages: list[dict]) -> tuple[list[dict], str, list[dict]]:
		"""Stream one tool-calling round, retrying the WHOLE round on a transient stream
		failure. Safe because a round applies nothing until it returns — ops are emitted and
		`messages` mutated by the caller only after this returns, so a failed attempt leaves
		no partial state; we just re-issue the identical completion (the cached prefix makes
		the retry cheap). litellm can't fall back mid-stream, so this is the retry layer."""
		for attempt in range(STREAM_MAX_ATTEMPTS):
			try:
				return self.stream_tool_round(messages)
			except CancelledError:
				raise
			except Exception as exc:
				if attempt == STREAM_MAX_ATTEMPTS - 1 or not llm.is_retryable(exc):
					raise
				backoff = STREAM_BACKOFF_BASE * (2**attempt)
				logger.warning(
					"Stream round failed (attempt %d/%d): %s — retrying in %.1fs",
					attempt + 1,
					STREAM_MAX_ATTEMPTS,
					exc,
					backoff,
				)
				self.interruptible_sleep(backoff)

	def stream_tool_round(self, messages: list[dict]) -> tuple[list[dict], str, list[dict]]:
		"""Stream one tool-calling completion. Returns (tool_operations, text_content,
		raw_tool_calls). Side-effect-free until it returns (see call_tool_llm) — accumulates
		into locals only, so it is safe to re-run. Tool-call arguments are accumulated by
		index across chunks."""
		stream = llm.complete_with_tools(
			self.model,
			messages,
			self.registry.schemas(),
			llm.TASK_PARAMS["agent"],
			api_key=self.api_key,
			stream=True,
		)

		content_parts: list[str] = []
		# index -> {"id", "name", "args"}; preserves call order across chunks.
		acc: dict[int, dict] = {}
		finish_reason = None

		for chunk in stream:
			if self.is_cancelled():
				try:
					stream.close()
				except Exception:
					pass
				raise CancelledError
			# The final include_usage chunk carries usage but no choices.
			if not chunk.choices:
				continue
			if fr := chunk.choices[0].finish_reason:
				finish_reason = fr
			delta = chunk.choices[0].delta
			if getattr(delta, "content", None):
				content_parts.append(delta.content)
			for tc in getattr(delta, "tool_calls", None) or []:
				idx = tc.index if tc.index is not None else 0
				entry = acc.setdefault(idx, {"id": None, "name": None, "args": ""})
				if tc.id:
					entry["id"] = tc.id
				fn = getattr(tc, "function", None)
				if fn and fn.name:
					entry["name"] = fn.name
				if fn and fn.arguments:
					entry["args"] += fn.arguments

		tool_operations: list[dict] = []
		raw_tool_calls: list[dict] = []
		for idx in sorted(acc):
			entry = acc[idx]
			if not entry["name"]:
				continue
			raw_arguments = entry["args"] or ""
			parsed, repaired = llm.loads_tolerant(raw_arguments)
			args = parsed if isinstance(parsed, dict) else {}
			if parsed is None:
				logger.warning("AI tool args UNPARSEABLE (tool=%s): %s", entry["name"], raw_arguments[:2000])
			elif repaired:
				logger.warning("AI tool args recovered via json_repair (tool=%s)", entry["name"])
			tool_operations.append({"tool_name": entry["name"], "args": args})
			raw_tool_calls.append(
				{
					"id": entry["id"],
					"type": "function",
					"function": {"name": entry["name"], "arguments": raw_arguments},
				}
			)

		content = "".join(content_parts)
		if finish_reason == "length":
			logger.warning("Agent LLM hit max_tokens (finish_reason=length) — tool args may be truncated")
		logger.info(
			"Agent LLM responded: tool_calls=%d, has_text=%s, finish_reason=%s",
			len(tool_operations),
			bool(content),
			finish_reason,
		)
		return tool_operations, content, raw_tool_calls

	@staticmethod
	def describe_operations(operations: list[dict]) -> str:
		"""A deterministic one-line summary of applied ops — used when the model didn't
		return its own summary text, so we avoid a second LLM round trip."""
		from collections import Counter

		counts = Counter(op.get("tool_name") for op in operations)

		def blk(n: int) -> str:
			return "block" if n == 1 else "blocks"

		parts: list[str] = []
		if n := counts.get("update_block"):
			parts.append(f"updated {n} {blk(n)}")
		if n := counts.get("add_block"):
			parts.append(f"added {n} {blk(n)}")
		if n := counts.get("remove_block"):
			parts.append(f"removed {n} {blk(n)}")
		if n := counts.get("move_block"):
			parts.append(f"moved {n} {blk(n)}")

		if not parts:
			n = len(operations)
			return f"Applied {n} change{'s' if n != 1 else ''} to the page."
		sentence = parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"
		return sentence[0].upper() + sentence[1:] + "."

	# --- orchestration ----------------------------------------------------

	def run(self):
		# Clear any stale cancel flag from a previous turn before starting.
		self.clear_cancel_flag()
		label = ModelRegistry.get_label(self.model)
		self.emit("progress", message=f"Thinking with {label}…" if label else "Thinking…")

		if self.session_id and AISession.is_session_running(self.session_id):
			logger.warning("AgentRunner.run: session %s already running, rejecting", self.session_id)
			self.emit(
				"error", message="Another AI request is still processing. Please wait for it to finish."
			)
			return
		self._set_running(True)

		messages = self.build_messages()
		# Mirror of the page tree this turn. Client ops are validated against it so the tool
		# result fed back is the truth, not a blanket "Applied." (see WorkingTree).
		self.tree = WorkingTree(self._page_root())
		client_operations: list[dict] = []
		summary_text = ""

		try:
			for _round in range(MAX_ROUNDS):
				tool_operations, summary_text, raw_tool_calls = self.call_tool_llm(messages)
				terminal_ops, server_ops, client_ops = self._classify(tool_operations)

				# A terminal tool ends the turn and hands control back to the user. If the
				# model emits more than one, the first wins (the turn is over).
				if terminal_ops:
					self.handle_terminal(terminal_ops[0])
					return

				# Apply this round's edits immediately so the canvas updates live and the user
				# sees progress during a long multi-block change. Server ops are NOT emitted —
				# they run via their handler below.
				if client_ops:
					client_operations.extend(client_ops)
					self.emit("tool_batch", operations=client_ops)

				# Live narration: surface what the model said / did THIS round.
				if tool_operations:
					note = (summary_text or "").strip() or (
						self.describe_operations(client_ops) if client_ops else ""
					)
					if note:
						self.emit("progress", message=note)

				# The model ENDS the turn by replying with a final summary and NO tool calls.
				if not tool_operations:
					break

				# Feed each tool's result back so the model can continue or self-correct.
				messages.append(
					{"role": "assistant", "content": summary_text or None, "tool_calls": raw_tool_calls}
				)
				for tc_dict, op in zip(raw_tool_calls, tool_operations, strict=True):
					tool = self.registry.get(op["tool_name"])
					if tool and tool.side == "server" and tool.handler:
						content = tool.handler(self, op["args"])
					else:
						content = self.tree.apply(op["tool_name"], op["args"])
						# "FAILED" (hard miss) or "NOT FOUND" (partial bulk miss) — a correction
						# the model is now being asked to make. Log so it's not invisible.
						if "FAILED" in content or "NOT FOUND" in content:
							logger.warning("Client op rejected — %s: %s", op["tool_name"], content)
					messages.append({"role": "tool", "tool_call_id": tc_dict["id"], "content": content})

		except CancelledError:
			self._emit_cancelled()
			return
		except Exception as e:
			logger.error(f"Agent LLM call failed: {e!s}", exc_info=True)
			frappe.log_error(f"Agent LLM call failed: {e}", "AgentRunner.run")
			# Show a generic message — raw provider/exception strings can leak internals.
			user_msg = "Something went wrong while building your changes. Please try again."
			AISession.try_append_message(
				self.session_id, "assistant", user_msg, message_type="status", metadata={"status": "error"}
			)
			frappe.db.commit()  # commit before emit so the client's reload sees it
			self.emit("error", message=user_msg)
			return
		finally:
			self.clear_cancel_flag()
			self._set_running(False)

		if not client_operations and not summary_text:
			logger.warning("Agent returned empty response (no tools, no text)")
			self.emit("error", message="The AI returned an empty response. Please try rephrasing.")
			return

		# The block edits were already emitted incrementally inside the loop. If the model
		# wrote no summary, synthesise one from the ops rather than making a second LLM call.
		if not summary_text:
			summary_text = self.describe_operations(client_operations)
		self.emit("stream", chunk=summary_text)

		AISession.try_append_message(
			self.session_id,
			"assistant",
			summary_text or "Done",
			message_type="chat",
			task_type="agent",
			metadata={"status": "complete", "model": self.model, "operations": len(client_operations)},
		)
		frappe.db.commit()  # commit before emit so the client's reload sees the final turn
		self.emit("complete", message=summary_text or "Done")

	def _classify(self, tool_operations: list[dict]) -> tuple[list, list, list]:
		"""Split this round's calls by tool side. Client ops are emitted to the canvas;
		server ops run via their handler; a terminal op ends the turn."""
		terminal_ops, server_ops, client_ops = [], [], []
		for op in tool_operations:
			side = self.registry.side(op["tool_name"])
			if side == "terminal":
				terminal_ops.append(op)
			elif side == "server":
				server_ops.append(op)
			else:
				client_ops.append(op)
		return terminal_ops, server_ops, client_ops

	def _set_running(self, running: bool) -> None:
		if not self.session_id:
			return
		try:
			session = AISession(frappe.get_doc(AISession.DOCTYPE, self.session_id))
			session.set_running() if running else session.clear_running()
			frappe.db.commit()  # visible to other workers' concurrency guard
		except Exception:
			pass

	def _emit_cancelled(self) -> None:
		msg = "Cancelled."
		AISession.try_append_message(
			self.session_id, "assistant", msg, message_type="status", metadata={"status": "cancelled"}
		)
		frappe.db.commit()
		self.emit("complete", message=msg)

	def handle_terminal(self, op: dict):
		"""Run a terminal tool's handler (which emits the appropriate event and persists
		the message). Terminal tools register a handler."""
		tool = self.registry.get(op["tool_name"])
		if tool and tool.handler:
			tool.handler(self, op["args"])


def run_agent_job(prompt: str, page_context_json: str, model: str, api_key: str, **kwargs):
	AgentRunner(prompt, page_context_json, model, api_key, **kwargs).run()
