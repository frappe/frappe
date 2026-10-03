"""Keep public-file serving confined to the real files root, including symlinked sites."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.exceptions import NotFound

import frappe.app
from frappe.middlewares import StaticDataMiddleware


class StaticDataMiddlewareTest(unittest.TestCase):
	def test_symlinked_sites_serve_public_files_without_allowing_paths_outside_the_files_root(self):
		with tempfile.TemporaryDirectory() as directory:
			root = Path(directory)
			sites = root / "sites"
			sites.mkdir()
			files = root / "restored" / "public" / "files"
			files.mkdir(parents=True)
			(sites / "rehearsal.localhost").symlink_to(root / "restored", target_is_directory=True)
			(files / "image.png").write_bytes(b"public image")
			secret = root / "private.txt"
			secret.write_bytes(b"private bytes")
			(files / "outside.png").symlink_to(secret)
			middleware = StaticDataMiddleware(lambda *_: [], {})
			middleware.environ = {"HTTP_HOST": "rehearsal.localhost:8006"}
			loader = middleware.get_directory_loader(str(sites))
			with patch.object(frappe.app, "_site", None):
				name, opener = loader("image.png")
				self.assertEqual(name, "image.png")
				stream, _, _ = opener()
				with stream:
					self.assertEqual(stream.read(), b"public image")
				for path in ("outside.png", "../../../private.txt", str(secret), "missing.png"):
					with self.subTest(path=path), self.assertRaises(NotFound):
						loader(path)
