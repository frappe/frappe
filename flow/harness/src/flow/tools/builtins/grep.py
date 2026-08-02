from __future__ import annotations

import asyncio
import shutil

from flow.tools.builtins.common import resolve, truncate
from flow.tools.tool import ToolContext, ToolResult, tool


@tool
async def grep(pattern: str, path: str = ".", *, ctx: ToolContext) -> ToolResult:
	"""Search files for a regex pattern (uses ripgrep if available) and return matches."""
	target = resolve(ctx, path)
	rg = shutil.which("rg")
	# `--` ends the option list: without it a pattern like "-L" is read as a flag, which
	# shifts `target` out of its slot and searches the daemon's cwd instead of the root.
	if rg:
		cmd = [rg, "--line-number", "--no-heading", "--color=never", "--", pattern, target]
	else:
		cmd = ["grep", "-rn", "--", pattern, target]
	proc = await asyncio.create_subprocess_exec(
		*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
	)
	try:
		stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=ctx.timeout)
	except TimeoutError:
		proc.kill()
		return ToolResult(content="[grep timed out]", is_error=True)
	out = stdout.decode("utf-8", "replace").strip()
	if not out:
		return ToolResult(content="[no matches]", details={"pattern": pattern, "matches": 0})
	matches = out.count("\n") + 1
	body, trunc = truncate(out, keep="head")
	notice = ""
	if trunc["truncated"]:
		notice = f"\n[showing {trunc['output_lines']} of {matches} match lines]"
	return ToolResult(
		content=body + notice,
		details={"pattern": pattern, "matches": matches, "truncation": trunc},
	)
