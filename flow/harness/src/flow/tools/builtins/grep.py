from __future__ import annotations

import asyncio
import contextlib
import shutil

from flow.tools.builtins.common import resolve, truncate
from flow.tools.tool import ToolContext, ToolResult, tool

# A catch-all pattern over a big tree yields gigabytes; only the head is ever shown.
MAX_READ_BYTES = 1 << 20


@tool(
	prompt_snippet="Search file contents for regex patterns",
	display_template="Searching code for {{ pattern }}",
)
async def grep(pattern: str, path: str = ".", *, ctx: ToolContext) -> ToolResult:
	"""Search files for a regex pattern (uses ripgrep if available) and return matches."""
	target = resolve(ctx, path, read_only=True)
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
	assert proc.stdout is not None  # stdout=PIPE above
	try:
		stdout, capped = await asyncio.wait_for(_read_capped(proc.stdout), timeout=ctx.timeout)
	except TimeoutError:
		proc.kill()
		return ToolResult(content="[grep timed out]", is_error=True)
	if capped:
		with contextlib.suppress(ProcessLookupError):
			proc.kill()
		stdout = stdout.rsplit(b"\n", 1)[0]  # drop the cut-off last line
	await proc.wait()
	out = stdout.decode("utf-8", "replace").strip()
	if not out:
		return ToolResult(content="[no matches]", details={"pattern": pattern, "matches": 0})
	matches = out.count("\n") + 1
	body, trunc = truncate(out, keep="head")
	notice = ""
	if trunc["truncated"] or capped:
		notice = f"\n[showing {trunc['output_lines']} of {matches}{'+' if capped else ''} match lines]"
	return ToolResult(
		content=body + notice,
		details={"pattern": pattern, "matches": matches, "truncation": trunc},
	)


async def _read_capped(stream: asyncio.StreamReader) -> tuple[bytes, bool]:
	chunks: list[bytes] = []
	size = 0
	while size < MAX_READ_BYTES:
		chunk = await stream.read(65536)
		if not chunk:
			return b"".join(chunks), False
		chunks.append(chunk)
		size += len(chunk)
	return b"".join(chunks), True
