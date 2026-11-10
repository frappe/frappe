"""Minimal Flow extension: one custom tool.

Run with:

    flow -e examples/extensions/hello_tool.py
"""

from flow_harness.extensions import ExtensionAPI
from flow_harness.tools import ToolContext, ToolResult, tool


@tool(prompt_snippet="Greet someone by name.", display_template="Greeting {{ who }}")
async def hello(who: str = "world", *, ctx: ToolContext) -> ToolResult:
	"""Greet someone by name."""
	del ctx
	return ToolResult(content=f"Hello, {who}!")


def setup(flow: ExtensionAPI) -> None:
	flow.register_tool(hello)
