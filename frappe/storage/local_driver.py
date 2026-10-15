# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import contextlib
import os
import shutil
from typing import IO

import frappe
from frappe.storage.driver import StorageDriver

CHUNK_SIZE = 64 * 1024


class LocalDriver(StorageDriver):
	"""Store blobs on the site's disk.

	Layout: ``sites/<site>/{public,private}/files/<key>``, where key is
	``<blob>/<filename>``. A public blob's path matches its URL
	``/files/<blob>/<filename>``, so nginx serves it directly. Backfilled
	legacy blobs keep their original path, such as ``logo.png``."""

	name = "local"

	def get_files_dir(self, is_private: bool = False) -> str:
		return frappe.utils.get_files_path(is_private=is_private)

	def get_path(self, key: str, is_private: bool = False) -> str:
		"""Resolve key to an absolute path under the files root.

		Absolute keys and keys that resolve outside the files root
		(traversal, symlink escape) are rejected."""
		files_root = os.path.realpath(self.get_files_dir(is_private))
		path = os.path.realpath(os.path.join(files_root, key))
		if os.path.isabs(key) or path == files_root or os.path.commonpath((files_root, path)) != files_root:
			raise ValueError(f"Invalid storage key: {key}")
		return path

	def write(self, key: str, stream: IO[bytes], *, is_private: bool = False) -> None:
		path = self.get_path(key, is_private)
		os.makedirs(os.path.dirname(path), exist_ok=True)
		part = path + ".part"
		# get_path confines the resolved path to the files root
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		with open(part, "wb") as f:
			shutil.copyfileobj(stream, f, CHUNK_SIZE)
			f.flush()
			os.fsync(f.fileno())
		os.replace(part, path)

	def read(self, key: str, *, is_private: bool = False) -> IO[bytes]:
		# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
		return open(self.get_path(key, is_private), "rb")

	def delete(self, key: str, *, is_private: bool = False) -> None:
		path = self.get_path(key, is_private)
		if os.path.isfile(path):
			os.remove(path)
		folder = os.path.dirname(path)
		if folder != os.path.realpath(self.get_files_dir(is_private)):
			# the blob's own folder; kept when something else is still in it
			with contextlib.suppress(OSError):
				os.rmdir(folder)

	def exists(self, key: str, *, is_private: bool = False) -> bool:
		return os.path.isfile(self.get_path(key, is_private))
