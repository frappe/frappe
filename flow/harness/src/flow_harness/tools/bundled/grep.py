from __future__ import annotations

import asyncio
import contextlib
import os
import re
import shutil
from typing import Annotated

from flow_harness.tools.builtins.common import resolve, truncate
from flow_harness.tools.tool import ToolContext, ToolResult, tool

# A catch-all pattern over a big tree yields gigabytes; only the head is ever shown.
MAX_READ_BYTES = 1 << 20


@tool(
	prompt_snippet="Search file contents for regex patterns",
	display_template="Searching code for {{ pattern }}",
)
async def grep(
	pattern: str,
	path: str = ".",
	include: Annotated[str | None, "file names to search, e.g. *.py; folders go in path"] = None,
	*,
	ctx: ToolContext,
) -> ToolResult:
	"""Search files for a regex pattern (uses ripgrep if available), skipping node_modules and binary files."""
	target = resolve(ctx, path, read_only=True)
	names = _name_globs(include)
	if any("{" in name for name in names):  # plain grep would read the rest literally and find nothing
		return ToolResult(
			content="[include takes one {a,b} group; list every combination in it, e.g. *.{spec.js,test.js}]",
			is_error=True,
		)
	# grep would skip the very folder it was asked to search
	skip_node_modules = os.path.basename(target) != "node_modules"
	rg = shutil.which("rg")
	# `--` ends the option list: without it a pattern like "-L" is read as a flag, which
	# shifts `target` out of its slot and searches the daemon's cwd instead of the root.
	# The last matching glob wins, so the skips must follow the caller's include.
	if rg:
		cmd = [rg, "--line-number", "--no-heading", "--color=never"]
		cmd.extend(f"--glob={name}" for name in names)
		if skip_node_modules:
			cmd.append("--glob=!node_modules")
		if ctx.ignore_hidden_files:
			cmd.extend(("--glob=!.*", "--glob=!**/.*"))
		cmd.extend(("--", pattern, target))
	else:
		cmd = ["grep", "-rnIE"]
		cmd.extend(f"--include={name}" for name in names)
		if skip_node_modules:
			cmd.append("--exclude-dir=node_modules")
		if ctx.ignore_hidden_files:
			cmd.extend(("--exclude=.*", "--exclude-dir=.*"))
		cmd.extend(("--", pattern, target))
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


def _name_globs(include: str | None) -> list[str]:
	"""File-name globs both engines read alike: folders dropped, one {a,b} group expanded."""
	name = (include or "").rsplit("/", 1)[-1]
	group = re.search(r"\{([^{}]*)\}", name)
	if not group:
		return [name] if name else []
	return [name[: group.start()] + alt + name[group.end() :] for alt in group.group(1).split(",")]


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
