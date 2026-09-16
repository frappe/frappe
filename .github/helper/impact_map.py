"""
Test impact map: which test modules exercise which source files.

Built from the nightly coverage run (see `ci.py`), where coverage is measured with
`dynamic_context="test_function"` so every covered line records the test that ran it.
Inverting that gives `{source_file: [test_files]}`, both repo-relative.

Coverage observes what actually executed, so it captures Frappe's runtime dispatch
(`frappe.get_attr`, `hooks.py` dotted paths, `frappe.get_doc` controller binding) that a
static import graph cannot see.

Consumed by `roulette.py` to decide which tests a pull request needs.

Usage:
    python impact_map.py merge <out.json> <part.json>...
    python impact_map.py selftest
"""

import json
import os
import sys
from datetime import UTC, datetime, timedelta, timezone
from functools import cache

# A map older than this is not trusted; callers fall back to the full suite.
MAX_AGE = timedelta(days=7)


@cache
def module_to_path(context: str, root: str) -> str | None:
	"""Resolve a coverage context to the test file it lives in.

	`frappe.tests.test_x.TestX.test_y` -> `frappe/tests/test_x.py`

	The split between module, class and method is ambiguous, so try each dotted prefix
	shortest-first and take the one that is an actual file on disk.
	"""
	parts = context.split(".")
	for i in range(1, len(parts) + 1):
		relpath = os.path.join(*parts[:i]) + ".py"
		if os.path.exists(os.path.join(root, relpath)):
			# Shared base classes resolve to non-test modules; those are not test files.
			return relpath if parts[i - 1].startswith("test_") else None
	return None


def build(coverage_data, root: str) -> dict:
	"""Invert coverage data into `{source_file: [test_file]}`, paths relative to `root`."""
	# ponytail: one SQLite query per measured file. Only runs in the nightly, after the
	# suite; batch it if it ever shows up as a meaningful share of that job.
	impact = {}
	for measured_file in coverage_data.measured_files():
		tests = set()
		for contexts in coverage_data.contexts_by_lineno(measured_file).values():
			for context in contexts:
				if context and (test_file := module_to_path(context, root)):
					tests.add(test_file)
		impact[os.path.relpath(measured_file, root)] = sorted(tests)

	return {"generated_at": datetime.now(UTC).isoformat(), "map": impact}


def merge(maps: list[dict]) -> dict:
	"""Combine the per-runner maps of one CI run into a single map."""
	merged = {}
	for part in maps:
		for source_file, tests in part["map"].items():
			merged.setdefault(source_file, set()).update(tests)

	return {
		# Oldest wins: the map is only as fresh as its stalest part.
		"generated_at": min(part["generated_at"] for part in maps),
		"map": {source_file: sorted(tests) for source_file, tests in merged.items()},
	}


def is_stale(impact_map: dict) -> bool:
	generated_at = datetime.fromisoformat(impact_map["generated_at"])
	return datetime.now(UTC) - generated_at > MAX_AGE


def is_test_module(file: str) -> bool:
	"""Is this a test file, as opposed to the source it tests?"""
	return file.endswith(".py") and os.path.basename(file).startswith("test_")


def unmapped(impact_map: dict, py_files: list[str]) -> list[str]:
	"""The changed files the map has no answer for.

	A file maps to no tests when it is brand new, when no test imports it, or when it only ever
	ran at import time (`__init__.py` and the like) -- none of which is evidence that changing it
	is safe, so any of them forces the full suite.

	Test modules are the exception: the tests a test module's content can break are its own, map
	or no map. Coverage omits `*/tests/*` (see `ci.py`), so most of them are absent by design.
	"""
	return [f for f in py_files if not impact_map["map"].get(f) and not is_test_module(f)]


def select(impact_map: dict, py_files: list[str]) -> list[str] | None:
	"""Test files needed for `py_files`, or None if the map cannot answer.

	Returning None means "run everything".
	"""
	if is_stale(impact_map) or unmapped(impact_map, py_files):
		return None

	# A changed test module always runs itself. Anything the map attributes to it on top of that
	# is a second test importing it for helpers, and needs to run too.
	tests = {f for f in py_files if is_test_module(f)}
	for py_file in py_files:
		tests.update(impact_map["map"].get(py_file) or ())

	return sorted(tests)


def all_tests(impact_map: dict) -> set[str]:
	return {test for tests in impact_map["map"].values() for test in tests}


def _selftest():
	fresh = datetime.now(UTC).isoformat()
	old = (datetime.now(UTC) - MAX_AGE - timedelta(days=1)).isoformat()

	one = {"generated_at": fresh, "map": {"frappe/a.py": ["frappe/tests/test_a.py"]}}
	two = {
		"generated_at": old,
		"map": {"frappe/a.py": ["frappe/tests/test_b.py"], "frappe/c.py": ["frappe/tests/test_c.py"]},
	}

	merged = merge([one, two])
	assert merged["generated_at"] == old
	assert merged["map"]["frappe/a.py"] == ["frappe/tests/test_a.py", "frappe/tests/test_b.py"]
	assert merged["map"]["frappe/c.py"] == ["frappe/tests/test_c.py"]

	assert select(one, ["frappe/a.py"]) == ["frappe/tests/test_a.py"]
	assert select(one, ["frappe/a.py", "frappe/unknown.py"]) is None, "unmapped file must bail out"
	import_only = {"generated_at": fresh, "map": {"frappe/__init__.py": []}}
	assert select(import_only, ["frappe/__init__.py"]) is None, "import-time-only file must bail out"
	assert select(one, []) == [], "no python changes selects no tests"
	assert select({**one, "generated_at": old}, ["frappe/a.py"]) is None, "stale map must bail out"

	# A test module runs itself whether or not the map knows it -- coverage omits `*/tests/*`.
	assert select(one, ["frappe/tests/test_new.py"]) == ["frappe/tests/test_new.py"]
	assert select(one, ["frappe/a.py", "frappe/tests/test_new.py"]) == [
		"frappe/tests/test_a.py",
		"frappe/tests/test_new.py",
	]
	helper = {"generated_at": fresh, "map": {"frappe/d/test_d.py": ["frappe/tests/test_a.py"]}}
	assert select(helper, ["frappe/d/test_d.py"]) == [
		"frappe/d/test_d.py",
		"frappe/tests/test_a.py",
	], "a test module other tests import runs those too"

	assert unmapped(one, ["frappe/a.py", "frappe/tests/test_new.py"]) == []
	assert unmapped(one, ["frappe/unknown.py"]) == ["frappe/unknown.py"]
	assert unmapped(import_only, ["frappe/__init__.py"]) == ["frappe/__init__.py"]

	assert all_tests(merged) == {
		"frappe/tests/test_a.py",
		"frappe/tests/test_b.py",
		"frappe/tests/test_c.py",
	}

	assert module_to_path("frappe.does.not.exist", os.getcwd()) is None
	print("impact_map selftest OK")


if __name__ == "__main__":
	command, *args = sys.argv[1:]

	if command == "selftest":
		_selftest()
	elif command == "merge":
		outfile, *infiles = args
		parts = [json.loads(open(f).read()) for f in infiles]
		merged = merge(parts)
		with open(outfile, "w") as f:
			json.dump(merged, f)
		print(f"Merged {len(infiles)} maps -> {outfile}: {len(merged['map'])} source files")
	else:
		sys.exit(f"unknown command: {command}")
