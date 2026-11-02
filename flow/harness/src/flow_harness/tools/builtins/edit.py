from __future__ import annotations

import difflib
import os

from pydantic import BaseModel, Field

from flow_harness.tools.builtins.common import detect_ending, resolve, to_lf
from flow_harness.tools.tool import ToolContext, ToolResult, tool


class Replacement(BaseModel):
	old: str = Field(description="exact text to replace; must occur exactly once in the file")
	new: str = Field(description="replacement text")


@tool(
	requires_confirmation=True,
	prompt_snippet="Make precise file edits with exact text replacement, including multiple disjoint edits in one call",
	prompt_guidelines=(
		"Use edit for precise changes (each edits[].old must match exactly once).",
		"When changing multiple separate locations in one file, use one edit call with multiple entries in edits[] instead of multiple edit calls.",
		"Each edits[].old is matched against the original file, not after earlier edits are applied. Do not emit overlapping edits; merge nearby changes into one edit.",
		"Keep edits[].old as small as possible while still being unique in the file. Do not pad with large unchanged regions.",
	),
	display_template="Editing file {{ path }}",
)
async def edit(path: str, edits: list[Replacement], *, ctx: ToolContext) -> ToolResult:
	"""Apply one or more exact-string replacements to a file. Each `old` must occur
	exactly once in the original file, and edits must not overlap."""
	# match line-ending-insensitively: normalize to LF, restore original endings + BOM on write
	if not edits:
		return ToolResult(content="[edit failed: no edits provided]", is_error=True)
	full = resolve(ctx, path)
	if not os.path.isfile(full):
		return ToolResult(content=f"[no such file: {path}]", is_error=True)
	with open(full, encoding="utf-8", newline="") as f:
		raw = f.read()
	bom = "\ufeff" if raw.startswith("\ufeff") else ""
	content = raw[len(bom) :]
	ending = detect_ending(content)
	norm = to_lf(content)

	updated, error = _apply_edits(norm, edits)
	if error:
		return ToolResult(content=f"[edit failed: {error}]", is_error=True)
	# per-line entries: joining first glues unterminated lines together
	diff_parts = list(
		difflib.unified_diff(norm.splitlines(keepends=True), updated.splitlines(keepends=True), full, full)
	)
	diff = "".join(diff_parts)
	result = updated.replace("\n", "\r\n") if ending == "\r\n" else updated
	with open(full, "w", encoding="utf-8", newline="") as f:
		f.write(bom + result)
	added = sum(1 for line in diff_parts if line.startswith("+") and not line.startswith("+++"))
	removed = sum(1 for line in diff_parts if line.startswith("-") and not line.startswith("---"))
	return ToolResult(
		content=f"[edited {path} ({len(edits)} block(s))]",
		details={
			"path": full,
			"edits": len(edits),
			"lines_added": added,
			"lines_removed": removed,
			"diff": diff,
		},
	)


def _apply_edits(norm: str, edits: list[Replacement]) -> tuple[str, str | None]:
	"""Validate all replacements against the original content, then apply them
	last-to-first. Returns (new_content, error); on error nothing is applied."""
	spans: list[tuple[int, int, str]] = []
	for i, e in enumerate(edits):
		old_lf = to_lf(e.old)
		if not old_lf:
			return norm, f"edits[{i}].old must not be empty"
		count = norm.count(old_lf)
		if count == 0:
			return norm, f"edits[{i}].old not found"
		if count > 1:
			return norm, f"edits[{i}].old is not unique ({count} matches)"
		start = norm.index(old_lf)
		spans.append((start, start + len(old_lf), to_lf(e.new)))

	ordered = sorted(spans)
	for a in range(1, len(ordered)):
		if ordered[a - 1][1] > ordered[a][0]:
			return norm, "edits overlap; merge them into one edit"

	result = norm
	for start, end, new_lf in sorted(spans, reverse=True):
		result = result[:start] + new_lf + result[end:]
	return result, None
