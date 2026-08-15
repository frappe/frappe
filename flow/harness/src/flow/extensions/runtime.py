"""The small runtime that owns loaded extensions and their registered tools."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from flow.extensions.loader import ExtensionDiagnostic, LoadedExtension, load_extensions
from flow.tools import Tool


@dataclass(frozen=True, slots=True)
class RegisteredExtension:
	name: str
	path: str


class ExtensionAPI:
	"""Object passed to an extension's ``setup(flow)`` entry point."""

	def __init__(self, runtime: ExtensionRuntime, extension_name: str) -> None:
		self._runtime = runtime
		self._extension_name = extension_name

	@property
	def name(self) -> str:
		return self._extension_name

	def register_tool(self, tool: Tool) -> None:
		"""Register a Flow ``Tool``. The first extension registration wins."""
		if not isinstance(tool, Tool):
			raise TypeError("register_tool expects a flow.tools.Tool (usually created with @tool)")
		self._runtime.register_tool(self._extension_name, tool)


class ExtensionRuntime:
	"""Loads extensions once and exposes their tools and diagnostics."""

	def __init__(self) -> None:
		self._extensions: list[RegisteredExtension] = []
		self._tools: dict[str, Tool] = {}
		self._tool_sources: dict[str, str] = {}
		self._diagnostics: list[ExtensionDiagnostic] = []

	def load(
		self,
		*,
		global_dir: Path | None,
		extra_paths: Sequence[Path] = (),
		include_global_dir: bool = True,
	) -> None:
		result = load_extensions(
			global_dir=global_dir,
			extra_paths=extra_paths,
			include_global_dir=include_global_dir,
		)
		self._diagnostics.extend(result.diagnostics)
		for extension in result.extensions:
			self._setup_extension(extension)

	def _setup_extension(self, extension: LoadedExtension) -> None:
		api = ExtensionAPI(self, extension.name)
		try:
			extension.setup(api)
		except Exception as error:  # extensions are an isolation boundary
			self._remove_tools(extension.name)
			self._diagnostics.append(
				ExtensionDiagnostic(
					message=f"setup failed: {error!r}",
					path=str(extension.path),
					extension=extension.name,
					severity="error",
				)
			)
			return
		self._extensions.append(RegisteredExtension(extension.name, str(extension.path)))

	def register_tool(self, extension_name: str, tool: Tool) -> None:
		existing = self._tool_sources.get(tool.name)
		if existing is not None:
			self._diagnostics.append(
				ExtensionDiagnostic(
					message=(
						f"tool `{tool.name}` already registered by extension `{existing}`; ignoring duplicate"
					),
					extension=extension_name,
				)
			)
			return
		self._tools[tool.name] = tool
		self._tool_sources[tool.name] = extension_name

	def _remove_tools(self, extension_name: str) -> None:
		for name, source in tuple(self._tool_sources.items()):
			if source == extension_name:
				self._tool_sources.pop(name, None)
				self._tools.pop(name, None)

	def compose_tools(self, builtin_tools: dict[str, Tool]) -> dict[str, Tool]:
		"""Return selected built-ins plus extension tools; extensions override by name."""
		return {**builtin_tools, **self._tools}

	@property
	def tools(self) -> dict[str, Tool]:
		return dict(self._tools)

	@property
	def tool_sources(self) -> dict[str, str]:
		return dict(self._tool_sources)

	@property
	def extensions(self) -> tuple[RegisteredExtension, ...]:
		return tuple(self._extensions)

	@property
	def diagnostics(self) -> tuple[ExtensionDiagnostic, ...]:
		return tuple(self._diagnostics)

	def info(self) -> dict:
		return {
			"extensions": [
				{
					"name": extension.name,
					"path": extension.path,
					"tools": [
						name for name, source in self._tool_sources.items() if source == extension.name
					],
				}
				for extension in self._extensions
			],
			"diagnostics": [diagnostic.to_dict() for diagnostic in self._diagnostics],
		}
