"""Tool registry for the Studio AI agent.

Every capability the agent has is a `Tool`. A tool declares its OpenAI-style
function schema and a *side* that tells the loop how to handle a call to it:

  - "client":   the operation is applied in the browser (block edits, scripts).
                The loop batches these and emits them to the frontend.
  - "server":   the loop runs `handler(ctx, args)` immediately and feeds the
                returned string back to the model as a tool result, then loops.
  - "terminal": the call ends the turn and hands control back to the user
                (e.g. ask a clarifying question, propose a plan). The loop calls
                `handler(ctx, args)` to emit the appropriate event and stops.

A tool may additionally produce a large *streamed artifact* (e.g. a full page
of JSON). Such a tool sets `artifact` + `generator`: when the conversational
model calls it, the loop hands execution to the generator, which produces the
artifact on the heavy model and streams it to the client as content (reliable),
then returns the canonical client op(s) to apply. The agent calling the tool is
the signal to generate — no out-of-band state decides it.

Adding a capability = registering one `Tool`. The loop never changes.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

ToolSide = Literal["client", "server", "terminal"]


@dataclass
class Tool:
	name: str
	side: ToolSide
	description: str
	parameters: dict
	# Required for "server" and "terminal" tools; ignored for "client" tools.
	# Signature: handler(ctx, args: dict) -> str | None
	handler: Callable | None = None
	# When set, this tool produces a streamed artifact of the given kind (e.g.
	# "page_json"). The loop runs `generator(ctx, args) -> list[dict]` instead of
	# emitting a plain client op; the generator streams the artifact as content
	# and returns the canonical client op(s) to apply. None = ordinary tool.
	artifact: str | None = None
	generator: Callable | None = None

	def schema(self) -> dict:
		return {
			"type": "function",
			"function": {
				"name": self.name,
				"description": self.description,
				"parameters": self.parameters,
			},
		}


class ToolRegistry:
	def __init__(self):
		self._tools: dict[str, Tool] = {}

	def register(self, tool: Tool) -> Tool:
		self._tools[tool.name] = tool
		return tool

	def extend(self, tools: list[Tool]) -> None:
		for tool in tools:
			self.register(tool)

	def get(self, name: str) -> Tool | None:
		return self._tools.get(name)

	def side(self, name: str) -> ToolSide:
		tool = self._tools.get(name)
		return tool.side if tool else "client"

	def schemas(self) -> list[dict]:
		return [tool.schema() for tool in self._tools.values()]

	def names(self) -> list[str]:
		return list(self._tools)


def build_default_registry() -> ToolRegistry:
	"""Assemble the registry from the tool modules. Imported lazily to avoid
	import cycles (tool handlers reference the agent context type)."""
	from studio.ai.agent.tools import blocks, conversation, generate, query

	registry = ToolRegistry()
	registry.extend(generate.TOOLS)
	registry.extend(blocks.TOOLS)
	registry.extend(query.TOOLS)
	registry.extend(conversation.TOOLS)
	return registry
