# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""The tables `flow-eval` prints, and the rule that calls a change better, same, worse or unclear."""

import json
import re
import statistics
from pathlib import Path

import click

LABEL = re.compile(r"^[A-Za-z0-9_-]+$")
FOLDER = re.compile(r"^[A-Za-z0-9_-]+(\.with|\.without)?$")


def verdict(a: int, n_a: int, b: int, n_b: int, errors: int = 0) -> str:
	"""`a` of `n_a` counted runs passed in the first arm, `b` of `n_b` in the second."""
	if errors or not n_a or not n_b:
		return "unclear"
	if a == 0 and b == n_b:
		return "better"
	if a == n_a and b == 0:
		return "worse"
	if (a, b) in ((n_a, n_b), (0, 0)):
		return "same"
	return "unclear"


def check_table(results: list[dict]) -> str:
	lines = [f"{'case':<22}{'step':<44}{'result':<28}{'bytes':>7}"]
	for result in results:
		name = result["case"]
		if not result["steps"]:
			lines.append(f"{name:<22}{result['status']}")
			if result["detail"]:
				lines.append(f"{'':<22}{result['detail']}")
		for step in result["steps"]:
			lines.append(f"{name:<22}{step['step'][:43]:<44}{step['word']:<28}{step['bytes']:>7,}")
			if step["word"] in ("fail", "error"):
				lines.append(f"{'':<22}{step['detail']}")
			name = ""
	played = [r for r in results if r["status"] != "no PATH"]
	passed = sum(r["status"] == "pass" for r in played)
	largest = max((s["bytes"] for r in results for s in r["steps"]), default=0)
	from flow_harness.tools.builtins.common import DEFAULT_MAX_BYTES

	lines.append(
		f"{passed} of {len(played)} cases pass. Largest result: {largest:,} bytes. "
		f"A result over {DEFAULT_MAX_BYTES:,} bytes is cut before the model sees it."
	)
	return "\n".join(lines)


def run_table(arms: dict[str, list[dict]], header: str, advice: bool = False) -> str:
	"""One count column per arm; with two, a verdict column and every fail and error under it."""
	names, two = list(arms), len(arms) == 2
	cases = sorted({r["case"] for records in arms.values() for r in records})
	w = max(11, *(len(n) + 2 for n in names))
	lines = [header, ""] * bool(header) + [
		f"{'case':<22}" + "".join(f"{n:<{w}}" for n in names) + "change" * two
	]
	totals, verdicts = {n: [0, 0] for n in names}, []
	for case in cases:
		runs = {n: [r for r in arms[n] if r["case"] == case] for n in names}
		counts = {
			n: (sum(r["status"] == "pass" for r in rs), sum(r["status"] != "error" for r in rs))
			for n, rs in runs.items()
		}
		errors = sum(len(rs) - counts[n][1] for n, rs in runs.items())
		row = f"{case:<22}" + "".join(
			f"{f'{p}/{c}' if runs[n] else '-':<{w}}" for n, (p, c) in counts.items()
		)
		if all(runs.values()):
			for n, (p, c) in counts.items():
				totals[n] = [totals[n][0] + p, totals[n][1] + c]
			if two:
				verdicts.append(verdict(*counts[names[0]], *counts[names[1]], errors))
				row += verdicts[-1] + (f" ({errors} error{'s' * (errors > 1)})" if errors else "")
		lines.append(row)
	total = f"{'total':<22}" + "".join(f"{f'{p}/{c}':<{w}}" for p, c in totals.values())
	total += (
		" · ".join(f"{verdicts.count(word)} {word}" for word in ("better", "same", "unclear", "worse")) * two
	)
	shared = set.intersection(*({r["case"] for r in records} for records in arms.values()))
	lines += [
		total,
		"",
		*_stat_lines({n: [r for r in rs if r["case"] in shared] for n, rs in arms.items()}, w),
	]
	if two:
		failed = [
			f"{r['status']:<6}{r['case']:<22}{n.rsplit('.', 1)[-1]} #{r['n']}  {r['detail']}"
			for n in names
			for r in arms[n]
			if r["status"] != "pass"
		]
		lines += [""] * bool(failed) + failed
		if advice and "unclear" in verdicts:
			lines.append(
				"unclear: run those cases again with more runs, e.g. --only <case> --runs 6 --label again"
			)
	return "\n".join(lines)


def _stat_lines(arms: dict[str, list[dict]], w: int) -> list[str]:
	def tokens(records):
		counted = [
			(r["usage"].get("input_tokens") or 0) + (r["usage"].get("output_tokens") or 0)
			for r in records
			if r["status"] != "error"
		]
		return f"{statistics.median(counted) if counted else 0:,.0f}"

	def cost(records):
		return f"${sum(r['usage'].get('cost') or 0 for r in records):.3f}"

	rows = (
		("tokens per run", tokens, "(median, input + output)"),
		("cost", cost, "(total, as Flow recorded it)"),
	)
	return [
		f"{title:<22}" + "".join(f"{show(rs):<{w}}" for rs in arms.values()) + note
		for title, show, note in rows
	]


def read_folder(root: Path, name: str) -> list[dict]:
	if not FOLDER.match(name):
		raise click.ClickException(f"{name} is not a label.")
	files = sorted((root / name).glob("*.json"))
	if not files:
		existing = sorted(p.name for p in root.glob("*") if p.is_dir()) if root.exists() else []
		raise click.ClickException(f"No runs saved as {name}. Saved: {', '.join(existing) or 'none'}.")
	return [json.loads(path.read_text()) for path in files]


def compare(root: Path, first: str, second: str) -> str:
	arms = {name: read_folder(root, name) for name in (first, second)}
	lines = []
	for name, records in arms.items():
		model = next(((r["model"] or {}).get("model_id") for r in records if r["model"]), "?")
		lines.append(
			f"{name}: {model} · " + " · ".join(f"{app} {sha}" for app, sha in records[0]["commits"].items())
		)
	if len({max(r["n"] for r in records) for records in arms.values()}) > 1:
		lines.append("warning: the two runs have different numbers of runs per case")
	return "\n".join([*lines, "", run_table(arms, "")])
