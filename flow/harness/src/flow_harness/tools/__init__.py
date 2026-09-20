from collections.abc import Iterable

from flow_harness.tools.builtins import BUILTIN_ALIASES, BUILTIN_TOOLS
from flow_harness.tools.bundled import BUNDLED_TOOLS
from flow_harness.tools.tool import SubagentOutcome, Tool, ToolContext, ToolResult, build_schema, tool


def select_tools(names: Iterable[str]) -> dict[str, Tool]:
	"""Built-in, bundled, and alias tools by name, in the order given; unknown names are skipped."""
	known = {**BUILTIN_TOOLS, **BUNDLED_TOOLS, **BUILTIN_ALIASES}
	return {name: known[name] for name in names if name in known}


__all__ = [
	"BUILTIN_ALIASES",
	"BUILTIN_TOOLS",
	"BUNDLED_TOOLS",
	"SubagentOutcome",
	"Tool",
	"ToolContext",
	"ToolResult",
	"build_schema",
	"select_tools",
	"tool",
]
