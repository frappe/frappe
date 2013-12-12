from __future__ import unicode_literals

import webnotes
import os

from werkzeug.wsgi import SharedDataMiddleware
from webnotes.utils import get_site_name, get_site_path, get_site_base_path, get_path, cstr

class StaticDataMiddleware(SharedDataMiddleware):
	def __call__(self, environ, start_response):
		self.environ = environ
		return super(StaticDataMiddleware, self).__call__(environ, start_response)

	def get_directory_loader(self, directory):
		def loader(path):
			filepath = os.path.join(os.path.join(".", self.site), directory, path)
			if os.path.isfile(filepath):
				return os.path.basename(filepath), self._opener(filepath)
			else:
				return None, None

		return loader
