"""Artifact generators — produce a large streamed artifact for a tool.

An *artifact tool* (one that sets `artifact=` on its `Tool`) delegates its
execution to a generator here. The generator runs on the user's selected *heavy*
model and streams the artifact to the client as plain content — reliable, unlike
tool-call argument streaming, which providers buffer (the canvas would stay blank
for the whole completion). After streaming, it returns the canonical client op for
the loop to emit so the frontend applies the authoritative, fully-parsed result.

The agent calling the tool is the only trigger: when the fast conversational model
decides to build the page, it calls `generate_page(brief=…)` and the loop hands off
here. No DB status or out-of-band heuristic gates generation.
"""

import logging

import frappe

from studio.ai import llm
from studio.ai.block_codec import BlockCodec
from studio.ai.prompts import GENERATION
from studio.ai.session import AISession

logger = frappe.logger("studio.ai.agent.artifact")
logger.setLevel(logging.INFO)


def generate_page_json(ctx, args: dict) -> list[dict]:
	"""Stream a complete page of block JSON on the heavy model, then return a
	`generate_page` client op carrying the authoritative parsed block tree.

	`ctx` is the AgentRunner. `args["brief"]` is the concise spec the conversational
	model assembled from the approved plan / conversation. Streams `kind="page_json"`
	chunks to the canvas as the model writes them. Returns [] if the model produced
	nothing.
	"""
	brief = (args.get("brief") or "").strip()

	messages: list[dict] = [
		{"role": "system", "content": GENERATION, "cache_control": {"type": "ephemeral"}},
	]
	# Prior conversation (incl. the approved plan) as proper role-tagged turns.
	messages.extend(AISession.build_context_messages_from_id(ctx.session_id))
	messages.append(
		{"role": "user", "content": f"Build this page now:\n{brief}" if brief else "Build the page now."}
	)

	ctx.emit("progress", message="Building the page…")

	content = ""
	finish_reason = None
	stream = llm.complete(ctx.model, messages, llm.TASK_PARAMS["complex"], stream=True, api_key=ctx.api_key)
	for chunk in stream:
		if ctx.is_cancelled():
			try:
				stream.close()
			except Exception:
				pass
			from studio.ai.agent.loop import CancelledError

			raise CancelledError
		if not chunk.choices:
			continue
		if fr := chunk.choices[0].finish_reason:
			finish_reason = fr
		delta = chunk.choices[0].delta.content
		if delta:
			content += delta
			ctx.emit("stream", chunk=delta, kind="page_json")

	if finish_reason == "length":
		logger.warning("generate_page hit max_tokens — the page may be truncated")
	try:
		block = BlockCodec.parse_blocks(content)
	except Exception as e:
		logger.warning("generate_page_json: could not parse model output (model=%s): %s", ctx.model, e)
		return []

	return [{"tool_name": "generate_page", "args": {"block": block}}]
