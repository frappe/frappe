from __future__ import annotations

import os
from typing import Annotated

from flow_harness.tools.builtins.common import resolve, truncate
from flow_harness.tools.tool import ToolContext, ToolResult, tool


@tool(
	prompt_snippet="Read file contents",
	prompt_guidelines=("Use read to examine files and images instead of cat or sed.",),
	display_template="Reading file {{ path }}",
)
async def read(
	path: str,
	offset: Annotated[int | None, "1-indexed line to start reading from"] = None,
	limit: Annotated[int | None, "maximum number of lines to read"] = None,
	*,
	ctx: ToolContext,
) -> ToolResult:
	"""Read a text or image file. Use offset/limit to page through large text files."""
	full = resolve(ctx, path, read_only=True)
	if not os.path.isfile(full):
		return ToolResult(content=f"[no such file: {path}]", is_error=True)
	try:
		with open(full, "rb") as f:
			head = f.read(8192)
	except OSError as e:
		return ToolResult(content=f"[cannot read {path}: {e.strerror or e}]", is_error=True)
	if _is_image(head):
		return await _read_image(full, path, ctx)
	if b"\0" in head:  # binary, the way git decides
		return ToolResult(
			content=f"[{path} is a binary file; read shows only text and images]", is_error=True
		)
	if offset is not None and offset < 1:
		return ToolResult(content="[offset must be >= 1]", is_error=True)
	if limit is not None and limit < 1:
		return ToolResult(content="[limit must be >= 1]", is_error=True)
	try:
		with open(full, encoding="utf-8", errors="replace") as f:
			text = f.read()
	except OSError as e:
		return ToolResult(content=f"[cannot read {path}: {e.strerror or e}]", is_error=True)

	total = text.count("\n") + 1
	if offset is None and limit is None:
		body, trunc = truncate(text, keep="head")
		content = body + _notice(0, trunc, total, None)
		return ToolResult(content=content, details={"path": full, "truncation": trunc})

	lines = text.split("\n")
	start = (offset or 1) - 1
	if start >= len(lines):
		return ToolResult(content=f"[offset {offset} is beyond end of file ({total} lines)]", is_error=True)
	end = min(start + limit, len(lines)) if limit is not None else len(lines)
	body, trunc = truncate("\n".join(lines[start:end]), keep="head")
	limited_end = end if end < len(lines) else None
	content = body + _notice(start, trunc, total, limited_end)
	return ToolResult(content=content, details={"path": full, "truncation": trunc})


async def _read_image(full: str, path: str, ctx: ToolContext) -> ToolResult:
	"""Store the image beside the session log; the model sees only a summary line."""
	if ctx.store_image is None:
		return ToolResult(content=f"[image file: {path} — images are unavailable in this session]")
	try:
		with open(full, "rb") as f:
			data = f.read()
	except OSError as e:
		return ToolResult(content=f"[cannot read {path}: {e.strerror or e}]", is_error=True)
	try:
		# AttachmentError is a ValueError; tools must not import session code
		stored = await ctx.store_image(os.path.basename(full), data)
	except ValueError as e:
		return ToolResult(content=f"[cannot read image {path}: {e}]", is_error=True)
	return ToolResult(
		content=f"[Image: {path} ({stored.mime_type}, {stored.width}x{stored.height})]",
		details={"path": full},
		attachments=[stored],
	)


def _is_image(head: bytes) -> bool:
	"""File signature check for the formats the attachment store accepts."""
	return (
		head.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"GIF8"))
		or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
		or (head[:2] == b"BM" and head[6:10] == b"\0\0\0\0")
	)


def _notice(start: int, trunc: dict, total: int, limited_end: int | None) -> str:
	if trunc["truncated"]:
		shown = trunc["output_lines"]
		return (
			f"\n\n[showing lines {start + 1}-{start + shown} of {total}; "
			f"use offset={start + shown + 1} to continue]"
		)
	if limited_end is not None:
		return (
			f"\n\n[showing lines {start + 1}-{limited_end} of {total}; "
			f"use offset={limited_end + 1} to continue]"
		)
	return ""
