# The build manifest — Python's half of the one bench-wide bundle, assembled for vite.

# Everything here runs with no site: `bench build` calls `frappe.init("")`, so apps come
# from `get_all_apps()` and hooks from `get_hooks(app_name=)`.

import json
import os

import frappe
from frappe.utils import get_bench_path

from .registry import declared_prefix

#: Enforced by the build and documented nowhere else; a duplicate instance breaks provide/inject.
SINGLETONS = ("vue", "vue-router", "frappe-ui", "@framework/ui", "reka-ui", "dompurify")

MANIFEST_FILENAME = "manifest.json"


#: What a stored Client Script imports by bare name; the one exemption from the `<app>/<alias>` rule.
FRAMEWORK_NAMES = ("vue", "vue-router", "frappe-ui", "@framework/ui")


#: What an app's desk v2 declaration holds; every other key is refused before vite starts.
DECLARATION_FILENAME = "desk.package.json"
DECLARATION_KEYS = ("dependencies",)


class SingletonConflict(Exception):
	pass


class DeclarationError(Exception):
	pass


class ImportMapConflict(Exception):
	pass


def contribution_globs(source_dir: str) -> list[str]:
	"""The five contribution kinds, as paths; a file anywhere else is not a contribution."""
	return [
		os.path.join(source_dir, "*", "doctype", "*", "frontend", "record.js"),
		os.path.join(source_dir, "*", "doctype", "*", "frontend", "list.js"),
		os.path.join(source_dir, "*", "custom", "*", "record.js"),
		os.path.join(source_dir, "*", "frontend", "pages", "*.js"),
		# Beside the `Navigation Item Type` JSON, where the plugin reads the kind's real name.
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


def declaration_path(app: str, source_dir: str) -> str:
	# frappe's own declaration is `frontend/package.base.json`; `frappe/package.json` is desk v1's
	# esbuild stack, a different bundle with different pins. An app's repo root file serves its own.
	if app == "frappe":
		return os.path.join(frontend_dir(), "package.base.json")
	return os.path.join(source_dir, DECLARATION_FILENAME)


def read_declaration(app: str, source_dir: str) -> dict:
	"""The app's desk v2 declaration: `dependencies` only; no file means no packages."""
	path = declaration_path(app, source_dir)
	declared = read_package(path)
	if app == "frappe":
		return declared

	if refused := sorted(set(declared) - set(DECLARATION_KEYS)):
		named = ", ".join(f"`{key}`" for key in refused)
		raise DeclarationError(
			f"{app} declares {named} in {bench_relative(path)}. "
			f"{DECLARATION_FILENAME} holds `dependencies` and nothing else; "
			"the repo root package.json serves the app's other bundles and is not read."
		)
	return declared


def app_deps(app: str) -> dict[str, str]:
	"""The app's own declared dependencies, dev included."""
	package = read_declaration(app, frappe.get_app_path(app))
	return {**package.get("dependencies", {}), **package.get("devDependencies", {})}


def app_runtime_deps(app: str) -> dict[str, str]:
	"""Only what contributed source can import: `dependencies`, never `devDependencies`."""
	return read_declaration(app, frappe.get_app_path(app)).get("dependencies", {})


def app_import_map(app: str) -> dict[str, str]:
	"""The names the app publishes to the document's import map, as `hooks.py` declares them."""
	# A dict hook comes back with each value wrapped in a list; one app's hooks hold one value each.
	declared = frappe.get_hooks("import_map", {}, app_name=app)
	return {name: value[-1] if isinstance(value, list) else value for name, value in declared.items()}


def frontend_dir() -> str:
	return os.path.join(frappe.get_app_source_path("frappe"), "frontend")


def assemble() -> list[dict]:
	"""The manifest in `sites/apps.txt` order: frappe, plus every app that contributes source."""
	manifest = []

	for app in frappe.get_all_apps():
		try:
			source_dir = frappe.get_app_path(app)
		except Exception as e:
			# Fail naming the app: a silently skipped app is a prefix that silently stops resolving.
			raise RuntimeError(f"Could not locate source for app '{app}': {e}") from e

		import_map = app_import_map(app)
		# A published file is bundled, so publishing alone puts an app in the bundle.
		if app != "frappe" and not contributes(source_dir) and not import_map:
			continue

		manifest.append(
			{
				"app": app,
				"app_prefix": declared_prefix(app),
				"source_dir": source_dir,
				"deps": app_deps(app),
				"runtime_deps": app_runtime_deps(app),
				"import_map": import_map,
			}
		)

	return manifest


def is_file_value(value: str) -> bool:
	"""A `.` or `/` prefix means a file rooted at the app's source dir; anything else is a package."""
	return value.startswith((".", "/"))


def package_name(specifier: str) -> str:
	"""`@scope/pkg/deep` declares `@scope/pkg`; `pkg/deep` declares `pkg`. The vite plugin's rule."""
	segments = specifier.split("/")
	return "/".join(segments[:2]) if specifier.startswith("@") else segments[0]


def bench_relative(path: str) -> str:
	bench = get_bench_path()
	return os.path.relpath(path, bench) if path.startswith(bench + os.sep) else path


def import_map_problems(entry: dict) -> list[str]:
	"""Every way one app's `import_map` breaks its promise, each naming the app, the key and the value."""
	app, source_dir = entry["app"], entry["source_dir"]
	problems = []

	for name, value in entry.get("import_map", {}).items():
		if name in FRAMEWORK_NAMES and app != "frappe":
			problems.append(f"{app} publishes `{name}`, which is a framework name")
			continue
		if not name.startswith(f"{app}/") and not (app == "frappe" and name in FRAMEWORK_NAMES):
			problems.append(f"{app} publishes `{name}`: a published name must start with `{app}/`")
			continue

		if not is_file_value(value):
			if package_name(value) not in entry["runtime_deps"]:
				problems.append(
					f"{app} publishes `{name}` from `{value}`, which "
					f"{bench_relative(declaration_path(app, source_dir))} does not declare under dependencies"
				)
			continue

		# `/lib/x.js` is rooted at the source dir, not the filesystem; `..` or a symlink may still climb out.
		root = os.path.realpath(source_dir)
		target = os.path.realpath(os.path.join(root, value.lstrip("/")))
		if not target.startswith(root + os.sep):
			problems.append(
				f"{app} publishes `{name}` from `{value}`, which resolves outside {bench_relative(source_dir)}"
			)
		elif not os.path.isfile(target):
			problems.append(f"{app} publishes `{name}` from `{value}`, which is not a file")

	return problems


def enforce_import_map(manifest: list[dict]):
	"""Fail the build when an app publishes a name it may not, or a value that does not resolve."""
	# Before vite starts: a bad value would otherwise surface as a resolution failure deep in the build.
	problems = [problem for entry in manifest for problem in import_map_problems(entry)]
	if problems:
		raise ImportMapConflict("\n" + "\n".join(f"  {problem}" for problem in problems))


def enforce_singletons(manifest: list[dict]):
	"""Fail the build when two apps in the bundle disagree on a shared library."""
	# Before vite starts, and not `resolve.dedupe`, which silently picks a winner.
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
			+ f"\n\nAlign the ranges in the apps' {DECLARATION_FILENAME} files and build again."
		)


def added_packages(entry: dict, base_dependencies: dict) -> dict[str, str]:
	"""What one app's declaration adds to the tree; a singleton or a base package adds nothing."""
	return {
		package: declared
		for package, declared in entry["runtime_deps"].items()
		if package not in SINGLETONS and package not in base_dependencies
	}


def compose_package_json(manifest: list[dict], frontend: str) -> bool:
	"""The one tree yarn installs: the framework's pins plus every app's own deps, generated."""
	# `package.base.json` always wins, so an app cannot move a singleton by naming it.
	base = read_package(os.path.join(frontend, "package.base.json"))
	dependencies = dict(base.get("dependencies", {}))

	for entry in manifest:
		if entry["app"] == "frappe":
			continue
		dependencies.update(added_packages(entry, dependencies))

	composed = {
		**base,
		"comment": "GENERATED by frappe/shell/manifest.py from package.base.json. Do not edit.",
		"dependencies": dependencies,
	}

	path = os.path.join(frontend, "package.json")
	# A rewritten file with identical contents must not trigger a reinstall.
	changed = read_package(path).get("dependencies") != dependencies

	# Bench-internal path, composed from `frontend_dir()`; never request-derived.
	with open(path, "w") as f:  # nosemgrep
		json.dump(composed, f, indent=2)

	return changed


def installed_size(package_dir: str) -> int:
	total = 0
	for root, _dirs, files in os.walk(package_dir):
		total += sum(os.lstat(os.path.join(root, name)).st_size for name in files)
	return total


def cost_report(manifest: list[dict], frontend: str) -> list[str]:
	"""One line per app after install: the packages its declaration added and their size on disk."""
	dependencies = dict(read_package(os.path.join(frontend, "package.base.json")).get("dependencies", {}))
	lines = []
	for entry in manifest:
		if entry["app"] == "frappe":
			continue
		added = added_packages(entry, dependencies)
		dependencies.update(added)
		if not added:
			lines.append(f"{entry['app']}: no packages added")
			continue
		sized = ", ".join(
			f"{package} {installed_size(os.path.join(frontend, 'node_modules', package)) / 1000:.1f} kB"
			for package in added
		)
		lines.append(f"{entry['app']}: {sized}")
	return lines


def write(frontend: str | None = None) -> tuple[list[dict], bool]:
	"""Assemble, enforce, write the manifest; returns it, and whether the dependency set changed."""
	frontend = frontend or frontend_dir()
	manifest = assemble()
	enforce_singletons(manifest)
	enforce_import_map(manifest)

	# `source_dirs` is every app, not just contributors: a `custom/` folder may name a doctype
	# owned by an app that contributes nothing. Bench-internal path; never request-derived.
	with open(os.path.join(frontend, MANIFEST_FILENAME), "w") as f:  # nosemgrep
		json.dump(
			{
				"apps": manifest,
				"source_dirs": [frappe.get_app_path(app) for app in frappe.get_all_apps()],
			},
			f,
			indent="\t",
		)

	return manifest, compose_package_json(manifest, frontend)
