from __future__ import annotations

import os

from flow.tools.builtins.common import resolve
from flow.tools.tool import ToolContext, ToolResult, tool


@tool(
	requires_confirmation=True,
	prompt_snippet="Create or overwrite files",
	prompt_guidelines=("Use write only for new files or complete rewrites.",),
)
async def write(path: str, content: str, *, ctx: ToolContext) -> ToolResult:
	"""Create or overwrite a file with the given text content."""
	full = resolve(ctx, path)
	os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
	with open(full, "w", encoding="utf-8", newline="") as f:
		f.write(content)
	return ToolResult(
		content=f"[wrote {path} ({len(content)} chars)]",
		details={"path": full, "chars": len(content)},
	)
