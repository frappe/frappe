# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from pathlib import Path

from werkzeug.exceptions import NotFound
from werkzeug.middleware.shared_data import SharedDataMiddleware

import frappe
from frappe.utils import cstr, get_site_name
from frappe.utils.response import FORCE_DOWNLOAD_EXTENSIONS


class StaticDataMiddleware(SharedDataMiddleware):
	def __call__(self, environ, start_response):
		self.environ = environ

		def patch_start_response(status, headers, exc_info=None):
			if (
				(path := environ.get("PATH_INFO", ""))
				and path.startswith("/files/")
				and path.lower().endswith(FORCE_DOWNLOAD_EXTENSIONS)
			):
				from urllib.parse import quote

				filename = Path(path).name
				headers.append(("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filename)}"))

			return start_response(status, headers, exc_info)

		return super().__call__(environ, patch_start_response)

	def get_directory_loader(self, directory):
		def loader(path):
			site = get_site_name(frappe.app._site or self.environ.get("HTTP_HOST"))
			files_path = Path(directory) / site / "public" / "files"
			requested_path = Path(cstr(path))
			path = (files_path / requested_path).resolve()
			if not path.is_relative_to(files_path) or not path.is_file():
				raise NotFound

			return path.name, self._opener(path)

		return loader
