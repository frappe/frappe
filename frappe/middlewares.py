# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import os
from werkzeug.exceptions import NotFound
from werkzeug.wsgi import SharedDataMiddleware
from frappe.utils import get_site_name, get_site_path, get_site_base_path, get_path, cstr
from frappe.recorder import Recorder

class StaticDataMiddleware(SharedDataMiddleware):
	def __call__(self, environ, start_response):
		self.environ = environ
		return super(StaticDataMiddleware, self).__call__(environ, start_response)

	def get_directory_loader(self, directory):
		def loader(path):
			site = get_site_name(frappe.app._site or self.environ.get('HTTP_HOST'))
			path = os.path.join(directory, site, 'public', 'files', cstr(path))
			if os.path.isfile(path):
				return os.path.basename(path), self._opener(path)
			else:
				raise NotFound
				# return None, None

		return loader


class RecorderMiddleware(object):
	def __init__(self, app):
		self._app = app

	def __call__(self, environ, start_response):
		response_body = []

		def catching_start_response(status, headers, exc_info=None):
			start_response(status, headers, exc_info)
			return response_body.append

		def runapp():
			appiter = self._app(environ, catching_start_response)
			response_body.extend(appiter)
			if hasattr(appiter, 'close'):
				appiter.close()

		recorder = Recorder()

		runapp()
		body = [b''.join(response_body)]

		recorder.dump()

		return body
