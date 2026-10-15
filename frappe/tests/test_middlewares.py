"""Keep public-file serving confined to the real files root, including symlinked sites."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.test import Client

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
				# what is outside the root or not on disk passes through to the
				# app, like nginx's try_files; the app answers 404
				for path in ("outside.png", "../../../private.txt", str(secret), "missing.png"):
					with self.subTest(path=path):
						self.assertEqual(loader(path), (None, None))

	def test_files_the_middleware_does_not_serve_reach_the_app_route(self):
		with tempfile.TemporaryDirectory() as directory:
			sites = Path(directory)
			(sites / "rehearsal.localhost" / "public" / "files").mkdir(parents=True)
			(sites / "private.txt").write_bytes(b"private bytes")

			def app(environ, start_response):
				start_response("404 NOT FOUND", [])
				return [b"from app"]

			client = Client(StaticDataMiddleware(app, {"/files": str(sites)}))
			with patch.object(frappe.app, "_site", "rehearsal.localhost"):
				for path in ("/files/missing.png", "/files/../../private.txt"):
					with self.subTest(path=path):
						response = client.get(path)
						self.assertEqual(response.status_code, 404)
						self.assertEqual(response.data, b"from app")
