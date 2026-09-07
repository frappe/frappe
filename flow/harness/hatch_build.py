import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class WebUIBuildHook(BuildHookInterface):
	"""Builds ui/app into src/flow_harness/server/webui, so a package always carries the web UI."""

	PLUGIN_NAME = "webui"

	def initialize(self, version, build_data):
		root = Path(self.root)
		# editable installs are for development; an sdist already carries the built assets
		if version == "editable" or (root / "PKG-INFO").is_file():
			return
		npm = shutil.which("npm")
		if npm is None:
			raise RuntimeError(
				"npm is required to package the web UI (ui/app -> src/flow_harness/server/webui)"
			)
		subprocess.run(
			[npm, "install", "--prefer-offline", "--no-audit", "--no-fund"], cwd=root / "ui", check=True
		)
		subprocess.run([npm, "run", "build", "-w", "app"], cwd=root / "ui", check=True)
