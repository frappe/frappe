# The build manifest — Python's half of the one bench-wide bundle.
#
# vite cannot discover any of this for itself. `app_prefix` is a Python scalar hook
# (#42065) and a prefix cannot be globbed for the way v1 globs `*.bundle.js`, so
# Python assembles `[{app, app_prefix, source_dir, deps}]` and hands it over (#42069).
#
# Everything here runs with **no site**: `bench build` calls `frappe.init("")`
# (`frappe/commands/utils.py:64`), which is why apps are enumerated with
# `get_all_apps()` and hooks are read with `get_hooks(app_name=)` — a pure importlib
# path that needs no site (#42105).

import json
import os

import frappe

from .registry import declared_prefix

#: Enforced by the build, not documented. The charter's four plus `reka-ui` and
#: `dompurify`, which are on today's SINGLETONS list (`ui/vite/index.js:21`) because
#: duplicate instances broke provide/inject in real bugs (#42069).
SINGLETONS = ("vue", "vue-router", "frappe-ui", "@framework/ui", "reka-ui", "dompurify")

MANIFEST_FILENAME = "manifest.json"


class SingletonConflict(Exception):
	pass


def contribution_globs(source_dir: str) -> list[str]:
	"""The five contribution kinds, as paths. If a file is not at one of these, it is
	not a contribution — that closure is charter item 1 (#42072).

	The fifth is a navigation item kind's renderer (#42420), colocated with the
	`Navigation Item Type` record it draws — which is what lets the plugin read the type's
	real NAME off the JSON beside it rather than title-casing the folder. The framework's
	own eight kinds are here too, so shipping one is the whole of shipping a kind."""
	return [
		os.path.join(source_dir, "*", "doctype", "*", "frontend", "record.js"),
		os.path.join(source_dir, "*", "doctype", "*", "frontend", "list.js"),
		os.path.join(source_dir, "*", "custom", "*", "record.js"),
		os.path.join(source_dir, "*", "frontend", "pages", "*.js"),
		os.path.join(source_dir, "*", "navigation_item_type", "*", "frontend", "item.js"),
	]


def contributes(source_dir: str) -> bool:
	import glob

	return any(glob.glob(pattern) for pattern in contribution_globs(source_dir))


def read_package(path: str) -> dict:
	if not os.path.exists(path):
		return {}
	# Bench-internal path, composed from `get_app_path`; never request-derived.
	with open(path) as f:  # nosemgrep
		return json.load(f)


def app_deps(app: str) -> dict[str, str]:
	"""The app's own declared dependencies.

	Apps keep declaring deps in their own `package.json`; the framework installs one
	tree. Yarn workspaces were rejected because they hoist and nest on conflict rather
	than fail, and the charter wants hard failure (#42069).

	The framework is the exception, and it has to be: `frappe/package.json` is desk
	v1's esbuild stack, which is a different bundle with different pins. The shell's
	own declaration is `frontend/package.base.json`, so that is what frappe's entry
	reports — otherwise the enforced singleton versions would be read off a tree that
	has nothing to do with the one being enforced.
	"""
	if app == "frappe":
		package = read_package(os.path.join(frontend_dir(), "package.base.json"))
	else:
		package = read_package(os.path.join(frappe.get_app_path(app, ".."), "package.json"))

	return {**package.get("dependencies", {}), **package.get("devDependencies", {})}


def app_runtime_deps(app: str) -> dict[str, str]:
	"""Only what contributed source can actually import.

	`dependencies`, never `devDependencies`: an app's playwright and its own vite are
	tooling for a build the framework has taken over, and installing them into the
	shell's tree would be carrying dead weight. They are still read by
	`enforce_singletons`, because a disagreement about a shared library is a
	disagreement wherever it is declared.
	"""
	if app == "frappe":
		package = read_package(os.path.join(frontend_dir(), "package.base.json"))
	else:
		package = read_package(os.path.join(frappe.get_app_path(app, ".."), "package.json"))

	return package.get("dependencies", {})


def frontend_dir() -> str:
	return os.path.join(frappe.get_app_source_path("frappe"), "frontend")


def assemble() -> list[dict]:
	"""The manifest, in bench-wide `sites/apps.txt` order.

	Note what decides membership: an app is in the *bundle* only if it actually
	contributes source. Every installed app still gets a prefix and is still served by
	the shell with no declaration at all — that is charter item 2 and it needs no
	build. But an app that contributes no modules has nothing in the module graph, so
	its dependency ranges are not part of the graph's version agreement either.
	"""
	manifest = []

	for app in frappe.get_all_apps():
		try:
			source_dir = frappe.get_app_path(app)
		except Exception as e:
			# Fail, naming the app. A silently skipped app is a prefix that silently
			# stops resolving, and frappe today does all three possible things in
			# three places; we follow the one that raises (#42105).
			raise RuntimeError(f"Could not locate source for app '{app}': {e}") from e

		if app != "frappe" and not contributes(source_dir):
			continue

		manifest.append(
			{
				"app": app,
				"app_prefix": declared_prefix(app),
				"source_dir": source_dir,
				"deps": app_deps(app),
				"runtime_deps": app_runtime_deps(app),
			}
		)

	return manifest


def enforce_singletons(manifest: list[dict]):
	"""Fail the build when two apps in the bundle disagree on a shared library.

	This runs at manifest assembly, **before vite starts**, and explicitly not as
	`resolve.dedupe` — dedupe silently picks a winner, and under one module graph a
	version conflict is a real disagreement between two app authors that somebody has
	to settle (#42069).
	"""
	claims: dict[str, list[tuple[str, str]]] = {}

	for entry in manifest:
		for package in SINGLETONS:
			if declared := entry["deps"].get(package):
				claims.setdefault(package, []).append((entry["app"], declared))

	conflicts = []
	for package, declarations in claims.items():
		ranges = {declared for _app, declared in declarations}
		if len(ranges) > 1:
			named = ", ".join(f"{app} wants {declared}" for app, declared in sorted(declarations))
			conflicts.append(f"  {package}: {named}")

	if conflicts:
		raise SingletonConflict(
			"The desk shell builds one module graph, which admits one version of each "
			"shared library. These are declared at conflicting versions:\n"
			+ "\n".join(conflicts)
			+ "\n\nAlign the ranges in the apps' package.json files and build again."
		)


def compose_package_json(manifest: list[dict], frontend: str) -> bool:
	"""The one tree yarn installs: the framework's pins plus every app's own deps.

	Generated rather than committed, because its content depends on which apps are on
	the bench. `package.base.json` is the committed half — the framework's own
	declaration — and it always wins, so an app cannot quietly move a singleton by
	naming it (the singleton check has already refused that case by the time we get
	here, but the precedence is worth being explicit about).
	"""
	base = read_package(os.path.join(frontend, "package.base.json"))
	dependencies = dict(base.get("dependencies", {}))

	for entry in manifest:
		if entry["app"] == "frappe":
			continue
		for package, declared in entry["runtime_deps"].items():
			if package in SINGLETONS or package in dependencies:
				continue
			dependencies[package] = declared

	composed = {
		**base,
		"comment": "GENERATED by frappe/shell/manifest.py from package.base.json. Do not edit.",
		"dependencies": dependencies,
	}

	path = os.path.join(frontend, "package.json")
	# Report whether the dependency set moved, so the caller knows to reinstall. A
	# rewritten file with identical contents must not trigger one.
	changed = read_package(path).get("dependencies") != dependencies

	# Bench-internal path, composed from `frontend_dir()`; never request-derived.
	with open(path, "w") as f:  # nosemgrep
		json.dump(composed, f, indent=2)

	return changed


def write(frontend: str | None = None) -> bool:
	"""Assemble, enforce, drop the manifest where vite will read it.

	Returns whether the composed dependency set changed, which is the caller's cue to
	reinstall.
	"""
	frontend = frontend or frontend_dir()
	manifest = assemble()
	enforce_singletons(manifest)

	# `apps` is the bundle: contributors only. `source_dirs` is every app on the bench,
	# which the contributions plugin needs separately — a `custom/` folder may name a
	# doctype owned by an app that contributes nothing, and the plugin has to read that
	# doctype's real name off disk rather than guess it from the folder.
	# Bench-internal path, composed from `frontend_dir()`; never request-derived.
	with open(os.path.join(frontend, MANIFEST_FILENAME), "w") as f:  # nosemgrep
		json.dump(
			{
				"apps": manifest,
				"source_dirs": [frappe.get_app_path(app) for app in frappe.get_all_apps()],
			},
			f,
			indent="\t",
		)

	return compose_package_json(manifest, frontend)
