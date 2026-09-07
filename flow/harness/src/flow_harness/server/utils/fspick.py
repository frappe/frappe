"""Native folder picker for the web UI's cwd selection.

A browser can't reveal an absolute path from a directory upload (security), so
the daemon — which runs on the user's machine — opens the OS's own folder
dialog and returns the chosen absolute path. Best-effort per platform; the
caller maps "no dialog available" to 501 and "cancelled" to a null path.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

_PROMPT = "Choose a project folder"
_TIMEOUT = 120  # seconds; a dialog left open past this counts as cancelled


class PickerUnavailable(RuntimeError):
	"""No native folder dialog on this platform/host (e.g. headless Linux)."""


def pick_folder() -> str | None:
	"""Open the OS folder picker; return the absolute path, or None if cancelled."""
	if sys.platform == "darwin":
		return _run(
			[
				"osascript",
				"-e",
				f'POSIX path of (choose folder with prompt "{_PROMPT}")',
			]
		)
	if sys.platform.startswith("linux"):
		if shutil.which("zenity"):
			return _run(["zenity", "--file-selection", "--directory", f"--title={_PROMPT}"])
		if shutil.which("kdialog"):
			return _run(["kdialog", "--getexistingdirectory", "."])
		raise PickerUnavailable("neither zenity nor kdialog is installed")
	if sys.platform == "win32":
		script = (
			"Add-Type -AssemblyName System.Windows.Forms; "
			"$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
			f"$d.Description = '{_PROMPT}'; "
			"if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
		)
		return _run(["powershell", "-NoProfile", "-Command", script])
	raise PickerUnavailable(f"unsupported platform: {sys.platform}")


def _run(cmd: list[str]) -> str | None:
	"""Run one dialog command. A non-zero exit is the platform's cancel path."""
	try:
		proc = subprocess.run(cmd, capture_output=True, text=True, timeout=_TIMEOUT)
	except subprocess.TimeoutExpired:
		return None  # dialog abandoned
	except OSError as e:
		raise PickerUnavailable(f"cannot launch {cmd[0]}: {e}") from None
	if proc.returncode != 0:
		return None
	path = proc.stdout.strip()
	if not path:
		return None
	# strip a trailing slash without turning the filesystem root into ""
	return path.rstrip("/") or "/"
