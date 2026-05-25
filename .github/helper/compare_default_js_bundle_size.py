#!/usr/bin/env python3
"""Compare default Desk JS bundle size against a base build.

The measured bundles come from `app_include_js` in `frappe/hooks.py` and are
resolved through hashed paths in `sites/assets/assets.json`.

Use `--esbuild-files` to print the comma-separated bundle list for
`node esbuild --files`, `--write-json` to record a base measurement, and
`--compare-to` to fail when the current measurement exceeds the configured
threshold.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path

# WARNING: DO NOT MODIFY THIS!
# Analyze the default bundle and optimize something instead: https://esbuild.github.io/analyze/
DEFAULT_THRESHOLD = 10.0 # KB
THRESHOLD_ENV_VAR = "DEFAULT_JS_BUNDLE_SIZE_THRESHOLD"


def get_default_js_bundles(bench_path: Path) -> list[str]:
	hooks_path = bench_path / "apps/frappe/frappe/hooks.py"
	hooks = ast.parse(hooks_path.read_text())

	for node in hooks.body:
		if not isinstance(node, ast.Assign):
			continue

		if any(isinstance(target, ast.Name) and target.id == "app_include_js" for target in node.targets):
			return ast.literal_eval(node.value)

	raise RuntimeError("Could not find app_include_js in frappe/hooks.py")


def get_default_bundle_size(bench_path: Path) -> dict:
	assets_json_path = bench_path / "sites/assets/assets.json"
	assets_json = json.loads(assets_json_path.read_text())

	bundles = []
	for bundle in get_default_js_bundles(bench_path):
		try:
			asset_path = assets_json[bundle]
		except KeyError:
			raise RuntimeError(
				f"Expected {bundle} from app_include_js, but it was not found in {assets_json_path}"
			) from None
		file_path = bench_path / "sites" / asset_path.lstrip("/")
		size = file_path.stat().st_size
		bundles.append({"bundle": bundle, "path": asset_path, "bytes": size})

	return {
		"total_bytes": sum(bundle["bytes"] for bundle in bundles),
		"bundles": bundles,
	}


def format_size(size: float) -> str:
	return f"{size / (1024 * 1024):.4f} MB"


def compare_bundle_sizes(base: dict, current: dict, threshold: float) -> bool:
	base_size = base["total_bytes"]
	current_size = current["total_bytes"]
	allowed_size = base_size + (threshold * 1024)
	increase = current_size - base_size
	increase_percentage = (increase / base_size) if base_size else 0

	print(f"Base default JS bundle size: {format_size(base_size)}")
	print(f"Current default JS bundle size: {format_size(current_size)}")
	print(f"Allowed default JS bundle size: {format_size(allowed_size)} ({threshold} KBs more than base)")
	print(f"Size change: {format_size(increase)} ({increase_percentage:.2%})")

	if current_size <= allowed_size:
		return True

	print("\nBundle size changes:")
	base_bundles = {bundle["bundle"]: bundle for bundle in base["bundles"]}
	current_bundles = {bundle["bundle"]: bundle for bundle in current["bundles"]}

	for bundle in current["bundles"]:
		base_bundle = base_bundles.get(bundle["bundle"])
		if not base_bundle:
			print(f"- {bundle['bundle']}: added ({format_size(bundle['bytes'])})")
			continue

		size_change = bundle["bytes"] - base_bundle["bytes"]
		if not size_change:
			continue

		print(
			f"- {bundle['bundle']}: {format_size(base_bundle['bytes'])} -> "
			f"{format_size(bundle['bytes'])} ({format_size(size_change)})"
		)

	for bundle in base["bundles"]:
		if bundle["bundle"] not in current_bundles:
			print(f"- {bundle['bundle']}: removed (was {format_size(bundle['bytes'])})")

	return False


def default_threshold() -> float:
	if THRESHOLD_ENV_VAR in os.environ:
		return float(os.environ[THRESHOLD_ENV_VAR])
	return DEFAULT_THRESHOLD


def get_esbuild_files(bench_path: Path) -> str:
	return ",".join(f"frappe/{bundle}" for bundle in get_default_js_bundles(bench_path))


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--bench-path", type=Path, default=Path.cwd())
	parser.add_argument("--write-json", type=Path)
	parser.add_argument("--compare-to", type=Path)
	parser.add_argument("--esbuild-files", action="store_true")
	parser.add_argument("--threshold", type=float, default=default_threshold())
	args = parser.parse_args()

	if args.esbuild_files:
		print(get_esbuild_files(args.bench_path))
		return

	current = get_default_bundle_size(args.bench_path)

	if args.write_json:
		args.write_json.write_text(json.dumps(current, indent=2))
		print(f"Default JS bundle size: {format_size(current['total_bytes'])}")

	if args.compare_to:
		base = json.loads(args.compare_to.read_text())
		if not compare_bundle_sizes(base, current, args.threshold):
			raise SystemExit(1)

	if not args.write_json and not args.compare_to:
		print(current["total_bytes"])


if __name__ == "__main__":
	main()
