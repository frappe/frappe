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


def _build_shared_registry() -> ToolRegistry:
	"""Tools common to every app: generation, block/UI wiring, data sources, bindings, interactivity.
	These act on the block tree the shared renderer consumes, identical in both modes. Imported lazily
	to avoid import cycles (tool handlers reference the agent context type)."""
	from studio.ai.agent.tools import (
		bindings,
		blocks,
		conversation,
		data,
		generate,
		interactivity,
		introspect,
		query,
	)

	registry = ToolRegistry()
	registry.extend(generate.TOOLS)
	registry.extend(blocks.TOOLS)
	registry.extend(query.TOOLS)
	registry.extend(conversation.TOOLS)
	registry.extend(introspect.TOOLS)
	registry.extend(data.TOOLS)
	registry.extend(bindings.TOOLS)
	registry.extend(interactivity.TOOLS)
	return registry


def build_custom_page_registry() -> ToolRegistry:
	"""Non-exported (visual/DB) app: reactive state as Studio Page variables, page logic as a bare
	interpreted script. No file surface — the app lives in the DB."""
	from studio.ai.agent.tools import scripts, variables

	registry = _build_shared_registry()
	registry.extend(variables.TOOLS)
	registry.extend(scripts.build_tools(is_standard=False))
	return registry


def build_standard_page_registry() -> ToolRegistry:
	"""Standard (exported) app: a real TypeScript codebase. State/logic live in setup() modules,
	stores and composables edited as files — so it gets the file tools and the module script form, and
	NO variable-doctype tools (state is declared in code instead)."""
	from studio.ai.agent.tools import files, scripts

	registry = _build_shared_registry()
	registry.extend(files.TOOLS)
	registry.extend(scripts.build_tools(is_standard=True))
	return registry


def get_tool_registry_for_mode(is_standard: bool) -> ToolRegistry:
	return build_standard_page_registry() if is_standard else build_custom_page_registry()
