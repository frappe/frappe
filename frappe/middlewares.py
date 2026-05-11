# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from pathlib import Path

from werkzeug.exceptions import NotFound
from werkzeug.middleware.shared_data import SharedDataMiddleware

import frappe
from frappe.utils import cstr, get_site_name


class StaticDataMiddleware(SharedDataMiddleware):
	def __call__(self, environ, start_response):
		self.environ = environ
		return super().__call__(environ, start_response)

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
