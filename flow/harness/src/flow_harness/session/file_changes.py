"""Reconstruct a file's pre-session content from the edit/write tool results
recorded in the durable log. This is the reader side of the builtin tools'
result contract: `details.path`, `details.diff`, and write-as-creation."""

from __future__ import annotations

import contextlib
import json
import re

from flow_harness.tools.builtins.common import to_lf

_HUNK_RE = re.compile(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def file_change_results(rows: list[dict], full_path: str) -> list[dict]:
	"""Successful edit/write results for one file, in log order."""
	results = []
	for row in rows:
		if row.get("type") != "tool_result" or row.get("name") not in ("edit", "write"):
			continue
		if row.get("is_error") or (row.get("details") or {}).get("path") != full_path:
			continue
		content = row.get("content") or ""
		if content.startswith("{"):  # an approval decision marker, not a real result
			with contextlib.suppress(ValueError):
				if json.loads(content).get("status") in ("denied", "cancelled", "redirect"):
					continue
		results.append(row)
	return results


def reconstruct_original(modified: str, results: list[dict]) -> str:
	"""The file as it was before the session's changes, by reverse-applying the
	recorded edit diffs newest-first. A write marks the file as created by the
	session, so its original is empty."""
	text = to_lf(modified)
	for result in reversed(results):
		if result.get("name") == "write":
			return ""
		diff = (result.get("details") or {}).get("diff") or ""
		if diff:
			text = _reverse_unified_diff(diff, text)
	return text


def _reverse_unified_diff(diff: str, text: str) -> str:
	"""Undo one recorded unified diff (LF, keepends) against `text`, best-effort:
	hunks whose after-side no longer matches (the file changed since) are left
	as they are, so the caller still gets a usable original for the rest."""
	lines = text.splitlines(keepends=True)
	out: list[str] = []
	pos = 0
	dl = diff.splitlines(keepends=True)
	i = 0
	while i < len(dl) and not dl[i].startswith("@@"):
		i += 1
	while i < len(dl):
		m = _HUNK_RE.match(dl[i])
		if not m:
			break  # malformed: keep the rest of the file untouched
		new_len = int(m.group(2)) if m.group(2) is not None else 1
		new_start = int(m.group(1)) - (1 if new_len else 0)
		i += 1
		before: list[str] = []
		after: list[str] = []
		while i < len(dl) and not dl[i].startswith("@@"):
			tag, body = dl[i][:1], dl[i][1:]
			if tag == " ":
				before.append(body)
				after.append(body)
			elif tag == "-":
				before.append(body)
			elif tag == "+":
				after.append(body)
			i += 1
		if new_start < pos or new_start + new_len > len(lines):
			continue  # out of bounds for the current file: skip the hunk
		region = lines[new_start : new_start + new_len]
		out.extend(lines[pos:new_start])
		out.extend(before if region == after else region)
		pos = new_start + new_len
	out.extend(lines[pos:])
	return "".join(out)
