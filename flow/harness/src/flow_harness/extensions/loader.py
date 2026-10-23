"""Discovery and import of Python extensions.

An extension is either a single ``.py`` file or a directory containing
``extension.py``. Each module must expose a synchronous ``setup(flow)`` function.
Failures are returned as diagnostics so one bad extension cannot prevent others
from loading.
"""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from inspect import iscoroutinefunction
from pathlib import Path
from uuid import uuid4

_MODULE_PREFIX = "flow_extension"


@dataclass(frozen=True, slots=True)
class ExtensionDiagnostic:
	message: str
	path: str | None = None
	extension: str | None = None
	severity: str = "warning"

	def to_dict(self) -> dict[str, str]:
		return {
			key: value
			for key, value in {
				"message": self.message,
				"path": self.path,
				"extension": self.extension,
				"severity": self.severity,
			}.items()
			if value is not None
		}


@dataclass(frozen=True, slots=True)
class DiscoveredExtension:
	name: str
	path: Path
	package_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class LoadedExtension:
	name: str
	path: Path
	setup: Callable[..., object]


@dataclass(frozen=True, slots=True)
class ExtensionLoadResult:
	extensions: tuple[LoadedExtension, ...]
	diagnostics: tuple[ExtensionDiagnostic, ...]


def discover_extensions(
	*,
	global_dir: Path | None,
	extra_paths: Sequence[Path] = (),
	include_global_dir: bool = True,
) -> tuple[tuple[DiscoveredExtension, ...], tuple[ExtensionDiagnostic, ...]]:
	"""Find extensions in deterministic order, keeping the first name/path seen."""
	discovered: list[DiscoveredExtension] = []
	diagnostics: list[ExtensionDiagnostic] = []
	seen_names: set[str] = set()
	seen_paths: set[Path] = set()

	def add(entry: DiscoveredExtension) -> None:
		resolved = entry.path.resolve()
		if resolved in seen_paths:
			return
		if entry.name in seen_names:
			diagnostics.append(
				ExtensionDiagnostic(
					message="duplicate extension name ignored (first-loaded wins)",
					path=str(entry.path),
					extension=entry.name,
				)
			)
			return
		seen_paths.add(resolved)
		seen_names.add(entry.name)
		discovered.append(entry)

	if include_global_dir and global_dir is not None:
		for entry in _discover_in_dir(global_dir):
			add(entry)

	for raw_path in extra_paths:
		path = raw_path.expanduser()
		if path.is_file():
			if path.suffix != ".py":
				diagnostics.append(
					ExtensionDiagnostic(
						message="extension file must use the .py suffix",
						path=str(path),
						severity="error",
					)
				)
				continue
			add(DiscoveredExtension(name=path.stem, path=path))
		elif path.is_dir():
			entry_file = path / "extension.py"
			if entry_file.is_file():
				add(DiscoveredExtension(name=path.name, path=entry_file, package_dir=path))
				continue
			entries = tuple(_discover_in_dir(path))
			if not entries:
				diagnostics.append(
					ExtensionDiagnostic(
						message="no extensions found in explicit extension path",
						path=str(path),
					)
				)
			for entry in entries:
				add(entry)
		else:
			diagnostics.append(
				ExtensionDiagnostic(
					message="explicit extension path does not exist",
					path=str(path),
					severity="error",
				)
			)

	return tuple(discovered), tuple(diagnostics)


def load_extensions(
	*,
	global_dir: Path | None,
	extra_paths: Sequence[Path] = (),
	include_global_dir: bool = True,
) -> ExtensionLoadResult:
	"""Discover and import extensions, isolating import failures."""
	discovered, diagnostics = discover_extensions(
		global_dir=global_dir,
		extra_paths=extra_paths,
		include_global_dir=include_global_dir,
	)
	loaded: list[LoadedExtension] = []
	all_diagnostics = list(diagnostics)
	for entry in discovered:
		extension, failure = _load_extension(entry)
		if failure is not None:
			all_diagnostics.append(failure)
		elif extension is not None:
			loaded.append(extension)
	return ExtensionLoadResult(tuple(loaded), tuple(all_diagnostics))


def _discover_in_dir(directory: Path) -> Iterator[DiscoveredExtension]:
	if not directory.is_dir():
		return
	for path in sorted(directory.iterdir(), key=lambda item: item.name):
		if path.name.startswith((".", "_")):
			continue
		if path.is_file() and path.suffix == ".py":
			yield DiscoveredExtension(name=path.stem, path=path)
		elif path.is_dir() and (path / "extension.py").is_file():
			yield DiscoveredExtension(name=path.name, path=path / "extension.py", package_dir=path)


def _load_extension(
	entry: DiscoveredExtension,
) -> tuple[LoadedExtension | None, ExtensionDiagnostic | None]:
	module_name = f"{_MODULE_PREFIX}_{_slugify(entry.name)}_{uuid4().hex}"
	search_locations = [str(entry.package_dir)] if entry.package_dir is not None else None
	spec = spec_from_file_location(
		module_name,
		entry.path,
		submodule_search_locations=search_locations,
	)
	if spec is None or spec.loader is None:
		return None, _error(entry, "could not create an import spec")

	module = module_from_spec(spec)
	sys.modules[module_name] = module
	try:
		spec.loader.exec_module(module)
	except BaseException as error:  # extensions are an isolation boundary
		_remove_module_tree(module_name)
		return None, _error(entry, f"failed to import extension: {error!r}")

	setup = getattr(module, "setup", None)
	if not callable(setup):
		_remove_module_tree(module_name)
		return None, _error(entry, "extension does not define a callable `setup(flow)` entry point")
	if iscoroutinefunction(setup):
		_remove_module_tree(module_name)
		return None, _error(entry, "`setup` must be synchronous")
	return LoadedExtension(name=entry.name, path=entry.path, setup=setup), None


def _remove_module_tree(module_name: str) -> None:
	for name in tuple(sys.modules):
		if name == module_name or name.startswith(f"{module_name}."):
			del sys.modules[name]


def unload_extension_modules() -> None:
	"""Drop every imported extension module so a reload imports fresh objects.

	In-flight tool calls keep working: their functions hold references to the old
	module objects, which only leave `sys.modules`, not memory.
	"""
	for name in tuple(sys.modules):
		if name.startswith(f"{_MODULE_PREFIX}_"):
			sys.modules.pop(name, None)


def _error(entry: DiscoveredExtension, message: str) -> ExtensionDiagnostic:
	return ExtensionDiagnostic(
		message=message,
		path=str(entry.path),
		extension=entry.name,
		severity="error",
	)


def _slugify(name: str) -> str:
	return "".join(character if character.isalnum() else "_" for character in name).lower()
