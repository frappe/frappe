"""Collect the apps of a site and the packages that they depend on.

The result has no SPDX concepts. The attribution page and the SBOM serializer both use it.
"""

import contextlib
import importlib
import importlib.metadata
import json
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
		self.packages: dict[tuple[str, str], Package] = {}
		self.dependencies: dict[Dependency, None] = {}
		self.expanded_python_extras: set[tuple[str, str]] = set()

	def collect(self) -> Inventory:
		for name in self.app_names:
			self.apps[canonicalize_name(name)] = get_app(name)

		for app in self.apps.values():
			self.add_python_dependencies(app)
			self.add_js_dependencies(app)

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
		for package in get_js_deps(app.name):
			key = ("npm", package.name)
			self.packages.setdefault(key, package)
			self.link(app, self.packages[key])


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


def get_js_deps(app: str) -> list[Package]:
	app_root = Path(frappe.get_app_path(app, ".."))

	# Collect (package.json, node_modules) pairs from the app root and any direct
	# child directory that has its own package.json (e.g. a frontend subdirectory).
	sources = []
	root_package_json = app_root / "package.json"
	if root_package_json.exists():
		sources.append((root_package_json, app_root / "node_modules"))
	for subdir in app_root.iterdir():
		if subdir.is_dir() and (subdir / "package.json").exists():
			sources.append((subdir / "package.json", subdir / "node_modules"))

	result = []
	seen = set()

	for package_json, node_modules_path in sources:
		with open(package_json) as f:
			package = json.load(f)

		packages = package.get("dependencies", {}).keys()

		for name in packages:
			if name in seen:
				continue
			seen.add(name)

			package_json_path = node_modules_path / name / "package.json"
			if not package_json_path.exists():
				result.append(Package(ecosystem="npm", name=name))
				continue

			pkg_data = None
			with contextlib.suppress(json.JSONDecodeError):
				pkg_data = json.loads(package_json_path.read_text())
			if not pkg_data:
				continue

			result.append(
				Package(
					ecosystem="npm",
					name=name,
					version=pkg_data.get("version"),
					license=_npm_license(pkg_data),
					author=_npm_author(pkg_data),
				)
			)

	return result


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
