from __future__ import unicode_literals

import webnotes
import os

from werkzeug.wsgi import SharedDataMiddleware
from webnotes.utils import get_site_name, get_site_path, get_site_base_path, get_path

class StaticDataMiddleware(SharedDataMiddleware):
	def __call__(self, environ, start_response):
		self.environ = environ
		return super(StaticDataMiddleware, self).__call__(environ, start_response)

	def get_directory_loader(self, directory):
		def loader(path):
			import conf
			fail = True
			if hasattr(conf, 'sites_dir'):
				site = get_site_name(self.environ.get('HTTP_HOST'))
				possible_site_path = get_path(directory, path, base=os.path.join(conf.sites_dir, site))
				if os.path.isfile(possible_site_path):
					path = possible_site_path
					fail = False

			if fail and os.path.isfile(get_path(directory, path)):
				path = get_path(directory, path)
				fail = False

			if fail:
				return None, None
			return os.path.basename(path), self._opener(path)
		return loader
