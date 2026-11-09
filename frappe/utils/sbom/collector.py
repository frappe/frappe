"""Collect the apps of a site and the packages that they depend on.

The result has no SPDX concepts. The attribution page and the SBOM serializer both use it.
"""

import base64
import contextlib
import importlib
import importlib.metadata
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

import frappe
from frappe.utils.change_log import get_app_last_commit_ref, get_pyproject, get_source_url


@dataclass(frozen=True)
class License:
	expression: str | None = None
	classifiers: tuple[str, ...] = ()
	text: str | None = None

	@property
	def summary(self) -> str | None:
		"""Short license name to show to a person. It is not always a valid SPDX expression."""
		if self.expression:
			return self.expression
		if self.classifiers:
			return self.classifiers[0].split("::")[-1].strip()
		return self.text


@dataclass(frozen=True)
class App:
	name: str
	version: str | None = None
	commit: str | None = None
	repository_url: str | None = None
	description: str = ""
	authors: tuple[str, ...] = ()
	license: License = License()


@dataclass(frozen=True)
class Package:
	ecosystem: str
	name: str
	version: str | None = None
	license: License = License()
	author: str | None = None
	repository_url: str | None = None
	commit: str | None = None
	download_url: str | None = None
	integrity: str | None = None
	vendored_path: str | None = None


@dataclass(frozen=True)
class Dependency:
	dependent: App | Package
	dependency: App | Package


@dataclass
class Inventory:
	apps: list[App] = field(default_factory=list)
	packages: list[Package] = field(default_factory=list)
	dependencies: list[Dependency] = field(default_factory=list)

	def direct_dependencies(self, app: App) -> list[Package]:
		return [
			d.dependency
			for d in self.dependencies
			if d.dependent == app and isinstance(d.dependency, Package)
		]


def collect(apps: list[str]) -> Inventory:
	return _Collector(apps).collect()


class _Collector:
	def __init__(self, app_names: list[str]):
		self.app_names = app_names
		self.apps: dict[str, App] = {}
		self.packages: dict[tuple[str, str] | tuple[str, str, str | None], Package] = {}
		self.dependencies: dict[Dependency, None] = {}
		self.expanded_python_extras: set[tuple[str, str]] = set()

	def collect(self) -> Inventory:
		for name in self.app_names:
			self.apps[canonicalize_name(name)] = get_app(name)

		for app in self.apps.values():
			self.add_python_dependencies(app)
			self.add_js_dependencies(app)

		if app := self.apps.get("frappe"):
			self.add_vendored_libraries(app)

		return Inventory(
			apps=list(self.apps.values()),
			packages=list(self.packages.values()),
			dependencies=list(self.dependencies),
		)

	def link(self, dependent: App | Package, dependency: App | Package):
		self.dependencies[Dependency(dependent, dependency)] = None

	def add_python_dependencies(self, app: App):
		pyproject = get_pyproject(app.name) or {}
		queue = [
			(app, requirement)
			for requirement in _parse_requirements(pyproject.get("project", {}).get("dependencies", []))
			if _marker_matches(requirement, "")
		]

		while queue:
			dependent, requirement = queue.pop(0)
			name = canonicalize_name(requirement.name)

			if name in self.apps:
				self.link(dependent, self.apps[name])
				continue

			package, distribution = self.get_python_package(requirement.name)
			self.link(dependent, package)
			if not distribution:
				continue

			for extra in ("", *sorted(requirement.extras)):
				if (name, extra) in self.expanded_python_extras:
					continue
				self.expanded_python_extras.add((name, extra))
				queue.extend(
					(package, child)
					for child in _parse_requirements(distribution.requires or [])
					if _marker_matches(child, extra)
				)

	def get_python_package(self, name: str) -> tuple[Package, importlib.metadata.Distribution | None]:
		try:
			distribution = importlib.metadata.distribution(name)
		except importlib.metadata.PackageNotFoundError:
			distribution = None

		key = ("pypi", canonicalize_name(name))
		if key not in self.packages:
			self.packages[key] = (
				_python_package(distribution) if distribution else Package(ecosystem="pypi", name=name)
			)
		return self.packages[key], distribution

	def add_js_dependencies(self, app: App):
		for root in _js_roots(app.name):
			manifest = _read_json(root / "package.json") or {}
			lockfile = _read_yarn_lock(root / "yarn.lock")
			queue = [(app, name, spec) for name, spec in manifest.get("dependencies", {}).items()]

			while queue:
				dependent, name, spec = queue.pop(0)
				entry = lockfile.get(f"{name}@{spec}")
				package, is_new = self.get_js_package(
					_npm_alias_target(name, spec), entry, root / "node_modules" / name / "package.json"
				)
				self.link(dependent, package)
				if entry and is_new:
					queue.extend(
						(package, child_name, child_spec)
						for section in ("dependencies", "optionalDependencies")
						for child_name, child_spec in entry.get(section, {}).items()
					)

	def get_js_package(self, name: str, entry: dict | None, manifest_path: Path) -> tuple[Package, bool]:
		version = entry.get("version") if entry else None
		key = ("npm", name, version)
		if key in self.packages:
			return self.packages[key], False

		manifest = _read_json(manifest_path) or {}
		if version and manifest.get("version") != version:
			manifest = {}

		download_url, integrity = _yarn_source(entry or {})
		self.packages[key] = Package(
			ecosystem="npm",
			name=name,
			version=version,
			license=_npm_license(manifest),
			author=_npm_author(manifest),
			download_url=download_url,
			integrity=integrity,
		)
		return self.packages[key], True

	def add_vendored_libraries(self, app: App):
		"""Add the libraries that are copied into the app, because no manifest lists them."""
		for library in json.loads(Path(__file__).with_name("vendored_libraries.json").read_text()):
			package = Package(
				ecosystem="npm",
				name=library["name"],
				version=library.get("version"),
				license=License(expression=library.get("license")),
				author=library.get("author"),
				vendored_path=library["path"],
			)
			self.packages[("vendored", package.name, package.version)] = package
			self.link(app, package)


def get_app(name: str) -> App:
	project = (get_pyproject(name) or {}).get("project", {})

	return App(
		name=name,
		version=getattr(importlib.import_module(name), "__version__", None),
		commit=get_app_last_commit_ref(name) or None,
		repository_url=get_source_url(name),
		description=project.get("description", ""),
		authors=tuple(a["name"] for a in project.get("authors", []) if a.get("name")),
		license=_pyproject_license(project),
	)


def _pyproject_license(project: dict) -> License:
	declared = project.get("license")
	classifiers = tuple(c for c in project.get("classifiers", []) if c.startswith("License ::"))

	if isinstance(declared, str):
		return License(expression=declared, classifiers=classifiers)
	if isinstance(declared, dict):
		return License(classifiers=classifiers, text=declared.get("text"))
	return License(classifiers=classifiers)


def _parse_requirements(specs: list[str]) -> list[Requirement]:
	requirements = []
	for spec in specs:
		with contextlib.suppress(InvalidRequirement):
			requirements.append(Requirement(spec))
	return requirements


def _marker_matches(requirement: Requirement, extra: str) -> bool:
	"""Match the requirement against this env, for the base package ("") or for one extra.

	A requirement of an extra matches only when it does not also match the base package.
	Then a package that is asked for with extras does not add its base requirements again.
	"""
	marker = requirement.marker
	if extra == "":
		return marker is None or marker.evaluate({"extra": ""})
	return marker is not None and marker.evaluate({"extra": extra}) and not marker.evaluate({"extra": ""})


def _python_package(distribution: importlib.metadata.Distribution) -> Package:
	metadata = distribution.metadata
	repository_url, commit = _vcs_source(distribution)

	return Package(
		ecosystem="pypi",
		name=metadata["Name"],
		version=distribution.version,
		license=License(
			expression=metadata.get("License-Expression"),
			classifiers=tuple(c for c in metadata.get_all("Classifier", []) if c.startswith("License ::")),
			text=metadata.get("License"),
		),
		author=(
			metadata.get("Author")
			or metadata.get("Maintainer")
			or metadata.get("Author-email")
			or metadata.get("Maintainer-email")
		),
		repository_url=repository_url,
		commit=commit,
	)


def _vcs_source(distribution: importlib.metadata.Distribution) -> tuple[str | None, str | None]:
	"""Return the repository and commit of a package that pip installed from a VCS URL (PEP 610)."""
	direct_url = distribution.read_text("direct_url.json")
	if not direct_url:
		return None, None

	with contextlib.suppress(json.JSONDecodeError):
		direct_url = json.loads(direct_url)
		if vcs_info := direct_url.get("vcs_info"):
			return direct_url.get("url"), vcs_info.get("commit_id")

	return None, None


def _js_roots(app: str) -> list[Path]:
	"""Return the app root and its direct child directories that have a package.json."""
	app_root = Path(frappe.get_app_path(app, ".."))
	return [
		directory
		for directory in (app_root, *sorted(app_root.iterdir()))
		if directory.is_dir() and (directory / "package.json").exists()
	]


def _read_json(path: Path) -> dict | None:
	with contextlib.suppress(FileNotFoundError, json.JSONDecodeError):
		return json.loads(path.read_text())
	return None


def _read_yarn_lock(path: Path) -> dict[str, dict]:
	with contextlib.suppress(FileNotFoundError):
		return parse_yarn_lock(path.read_text())
	return {}


def parse_yarn_lock(text: str) -> dict[str, dict]:
	"""Parse a yarn v1 lockfile into a map from each "name@range" key to its entry.

	Return an empty map for other formats, such as the YAML lockfile of yarn 2 and later.
	"""
	if "# yarn lockfile v1" not in text:
		return {}

	entries: dict[str, dict] = {}
	entry: dict = {}
	section: dict | None = None

	for line in text.splitlines():
		if not line.strip() or line.lstrip().startswith("#"):
			continue

		indent = len(line) - len(line.lstrip(" "))
		line = line.strip()

		if indent == 0:
			entry = {}
			section = None
			for key in line.removesuffix(":").split(", "):
				entries[_unquote(key)] = entry
		elif line.endswith(":"):
			section = entry.setdefault(line.removesuffix(":"), {})
		else:
			key, _, value = line.partition(" ")
			key, value = _unquote(key), _unquote(value)
			if indent == 2:
				entry[key] = value
				section = None
			elif section is not None:
				section[key] = value

	return entries


def _unquote(value: str) -> str:
	return value.removeprefix('"').removesuffix('"')


def _npm_alias_target(name: str, spec: str) -> str:
	"""Return the real package name of an alias such as `"string-width-cjs": "npm:string-width@^4"`."""
	if spec.startswith("npm:"):
		target = spec.removeprefix("npm:")
		return target.rsplit("@", 1)[0] if target.rfind("@") > 0 else target
	return name


def _yarn_source(entry: dict) -> tuple[str | None, str | None]:
	"""Return the download URL and the subresource integrity string of a yarn lockfile entry.

	Old lockfiles have no integrity field. Then the URL fragment holds the SHA-1 of the tarball.
	"""
	url, _, fragment = (entry.get("resolved") or "").partition("#")
	integrity = entry.get("integrity")
	if not integrity and re.fullmatch(r"[0-9a-f]{40}", fragment):
		integrity = "sha1-" + base64.b64encode(bytes.fromhex(fragment)).decode()
	return url or None, integrity


def _npm_license(pkg_data: dict) -> License:
	license_info = pkg_data.get("license")
	if isinstance(license_info, dict):
		return License(text=license_info.get("type"))
	if isinstance(license_info, str):
		return License(expression=license_info)
	return License()


def _npm_author(pkg_data: dict) -> str | None:
	author = pkg_data.get("author")
	if isinstance(author, dict):
		author = author.get("name")
	if author:
		return author

	names = []
	for m in pkg_data.get("maintainers", []):
		if isinstance(m, dict):
			m = m.get("name")
		if m and isinstance(m, str):
			names.append(m)
	return ", ".join(names) or None
