from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Annotated

from flow_harness.tools.builtins.common import kill_group, spill, truncate
from flow_harness.tools.tool import ToolContext, ToolResult, tool


@tool(
	requires_confirmation=True,
	prompt_snippet="Execute bash commands (git, tests, build steps, etc.)",
	prompt_guidelines=("Use bash for file operations like ls, find, and mv.",),
	display_template="Running command {{ command }}",
)
async def bash(
	command: str,
	timeout: Annotated[float | None, "maximum seconds to run (default 120)"] = None,
	*,
	ctx: ToolContext,
) -> ToolResult:
	"""Run a shell command; returns combined stdout/stderr and the exit code.

	Shell commands are not constrained by ``ToolContext.allowed_roots``. Use process
	isolation when filesystem containment must be a security boundary.
	"""
	if timeout is not None and timeout <= 0:
		return ToolResult(content="[timeout must be > 0]", is_error=True)
	limit = timeout if timeout is not None else ctx.timeout
	start = time.monotonic()
	proc = await asyncio.create_subprocess_shell(
		command,
		cwd=ctx.cwd,
		stdout=asyncio.subprocess.PIPE,
		stderr=asyncio.subprocess.STDOUT,
		start_new_session=True,
	)
	comm = asyncio.ensure_future(proc.communicate())
	abort = asyncio.ensure_future(ctx.abort.wait())
	interrupted = False
	cancelled: asyncio.CancelledError | None = None
	try:
		done, _ = await asyncio.wait({comm, abort}, timeout=limit, return_when=asyncio.FIRST_COMPLETED)
		interrupted = comm not in done
	except asyncio.CancelledError as exc:
		# The agent loop races every tool against cancellation. Preserve Bash's stronger
		# guarantee when that outer race cancels this coroutine: kill the whole process
		# group before allowing cancellation to propagate.
		interrupted = True
		cancelled = exc
	finally:
		abort.cancel()
		with contextlib.suppress(asyncio.CancelledError):
			await abort

	if interrupted:
		kill_group(proc)  # kill the group so pipeline/compound children die too
	try:
		# Drain buffered output; after the group kill communicate() settles promptly.
		stdout, _ = await asyncio.wait_for(asyncio.shield(comm), timeout=5)
	except (TimeoutError, asyncio.CancelledError):
		stdout = b""
	if cancelled is not None:
		raise cancelled
	out = stdout.decode("utf-8", "replace")
	duration = round(time.monotonic() - start, 3)

	body, trunc = truncate(out, keep="tail")
	full_output_path = spill(out) if trunc["truncated"] else None
	details: dict = {
		"command": command,
		"exit_code": proc.returncode,
		"duration_seconds": duration,
		"truncation": trunc,
		"full_output_path": full_output_path,
	}
	text = f"$ {command}\n{body}" if body else f"$ {command}"
	if trunc["truncated"]:
		text += (
			f"\n[output truncated to last {trunc['output_lines']} of "
			f"{trunc['total_lines']} lines; full output: {full_output_path}]"
		)
	if interrupted:
		aborted = ctx.abort.is_set()
		details["aborted"] = aborted
		details["timed_out"] = not aborted
		status = "aborted" if aborted else f"timed out after {limit}s"
		return ToolResult(content=f"{text}\n[command {status}]", details=details, is_error=True)
	text += f"\n[exit code: {proc.returncode}]"
	return ToolResult(content=text, details=details, is_error=proc.returncode not in (0, None))
