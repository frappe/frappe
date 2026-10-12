# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import io
import os
import tempfile
import zipfile
from unittest.mock import MagicMock, patch

from frappe.tests import UnitTestCase
from frappe.utils.chromium.download import download_chromium


def _archive_containing(*names: str) -> bytes:
	"""Build a Chromium-like zip. Recorded permissions do not matter — zipfile.extractall()
	drops them and writes every member as 0o644."""
	buffer = io.BytesIO()
	with zipfile.ZipFile(buffer, "w") as archive:
		for name in names:
			archive.writestr(name, b"not a real binary")
	return buffer.getvalue()


def _streamed_response(payload: bytes) -> MagicMock:
	response = MagicMock()
	response.headers = {"content-length": str(len(payload))}
	response.iter_content.return_value = [payload]
	return MagicMock(__enter__=MagicMock(return_value=response), __exit__=MagicMock(return_value=False))


class TestChromiumDownload(UnitTestCase):
	def download(self, payload: bytes) -> str:
		"""Run download_chromium() against a throwaway bench and return the expected executable path."""
		bench_path = tempfile.mkdtemp()
		with (
			patch("frappe.utils.get_bench_path", return_value=bench_path),
			patch("platform.system", return_value="Linux"),
			patch(
				"frappe.utils.chromium.download.get_chromium_download_url",
				return_value="https://example.com/chromium.zip",
			),
			patch("requests.get", return_value=_streamed_response(payload)),
		):
			download_chromium()

		return os.path.join(bench_path, "chromium", "chrome-linux", "headless_shell")

	def test_linux_arm64_archive_leaves_headless_shell_executable(self):
		"""The arm64 build already unpacks to chrome-linux/headless_shell and skips the rename branch."""
		executable = self.download(_archive_containing("chrome-linux/headless_shell"))

		self.assertTrue(os.path.exists(executable), f"{executable} was not extracted")
		self.assertTrue(os.access(executable, os.X_OK), f"{executable} is not executable")

	def test_linux_x86_64_archive_is_renamed_and_left_executable(self):
		executable = self.download(_archive_containing("chrome-headless-shell-linux64/chrome-headless-shell"))

		self.assertTrue(os.path.exists(executable), f"{executable} was not extracted")
		self.assertTrue(os.access(executable, os.X_OK), f"{executable} is not executable")
