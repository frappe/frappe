import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class WebUIBuildHook(BuildHookInterface):
	"""Builds ui/app into src/flow_harness/server/webui, so a package always carries the web UI."""

	PLUGIN_NAME = "webui"

	def initialize(self, version, build_data):
		root = Path(self.root)
		webui_index = root / "src" / "flow_harness" / "server" / "webui" / "index.html"
		if version == "editable":
			return
		if (root / "PKG-INFO").is_file():
			if not webui_index.is_file():
				raise RuntimeError(f"source distribution does not contain {webui_index}")
			return

		npm = shutil.which("npm")
		if npm is None:
			raise RuntimeError(
				"npm is required to package the web UI; install Node.js and npm, then run the build again"
			)
		subprocess.run([npm, "ci"], cwd=root / "ui", check=True)
		subprocess.run([npm, "run", "build", "-w", "app"], cwd=root / "ui", check=True)

		if not webui_index.is_file():
			raise RuntimeError(f"web UI build completed without producing {webui_index}")
