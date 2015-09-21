# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import os
import MySQLdb

from werkzeug.wrappers import Request
from werkzeug.local import LocalManager
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.contrib.profiler import ProfilerMiddleware
from werkzeug.wsgi import SharedDataMiddleware
from werkzeug.serving import run_with_reloader


import frappe
import frappe.handler
import frappe.auth
import frappe.api
import frappe.async
import frappe.utils.response
import frappe.website.render
from frappe.utils import get_site_name, get_site_path
from frappe.middlewares import StaticDataMiddleware


local_manager = LocalManager([frappe.local])

_site = None
_sites_path = os.environ.get("SITES_PATH", ".")

logger = frappe.get_logger()

class RequestContext(object):

	def __init__(self, environ):
		self.request = Request(environ)

	def __enter__(self):
		frappe.local.request = self.request
		init_site(self.request)
		make_form_dict(self.request)
		frappe.local.http_request = frappe.auth.HTTPRequest()

	def __exit__(self, type, value, traceback):
		frappe.destroy()


@Request.application
def application(request):
	frappe.local.request = request
	frappe.local.is_ajax = frappe.get_request_header("X-Requested-With")=="XMLHttpRequest"
	response = None

	try:
		rollback = True

		init_site(request)

		if frappe.local.conf.get('maintenance_mode'):
			raise frappe.SessionStopped

		make_form_dict(request)
		frappe.local.http_request = frappe.auth.HTTPRequest()

		if frappe.local.form_dict.cmd:
			response = frappe.handler.handle()

		elif frappe.request.path.startswith("/api/"):
			response = frappe.api.handle()

		elif frappe.request.path.startswith('/backups'):
			response = frappe.utils.response.download_backup(request.path)

		elif frappe.local.request.method in ('GET', 'HEAD'):
			response = frappe.website.render.render(request.path)

		else:
			raise NotFound

	except HTTPException, e:
		return e

	except frappe.SessionStopped, e:
		response = frappe.utils.response.handle_session_stopped()

	except Exception, e:
		http_status_code = getattr(e, "http_status_code", 500)
		#print frappe.get_traceback()

		if (http_status_code==500
			and isinstance(e, MySQLdb.OperationalError)
			and e.args[0] in (1205, 1213)):
				# 1205 = lock wait timeout
				# 1213 = deadlock
				# code 409 represents conflict
				http_status_code = 508

		if frappe.local.is_ajax or 'application/json' in request.headers.get('Accept', ''):
			response = frappe.utils.response.report_error(http_status_code)
		else:
			traceback = "<pre>"+frappe.get_traceback()+"</pre>"
			if frappe.local.flags.disable_traceback:
				traceback = ""

			frappe.respond_as_web_page("Server Error",
				traceback,
				http_status_code=http_status_code)
			response = frappe.website.render.render("message", http_status_code=http_status_code)

		if e.__class__ == frappe.AuthenticationError:
			if hasattr(frappe.local, "login_manager"):
				frappe.local.login_manager.clear_cookies()

		if http_status_code==500:
			logger.error('Request Error')

	else:
		if frappe.local.request.method in ("POST", "PUT") and frappe.db:
			if frappe.db.transaction_writes:
				frappe.db.commit()
				rollback = False

		# update session
		if getattr(frappe.local, "session_obj", None):
			updated_in_db = frappe.local.session_obj.update()
			if updated_in_db:
				frappe.db.commit()

		# publish realtime
		for args in frappe.local.realtime_log:
			frappe.async.emit_via_redis(*args)

	finally:
		if frappe.local.request.method in ("POST", "PUT") and frappe.db and rollback:
			frappe.db.rollback()

		# set cookies
		if response and hasattr(frappe.local, 'cookie_manager'):
			frappe.local.cookie_manager.flush_cookies(response=response)

		frappe.destroy()

	return response

def init_site(request):
	site = _site or request.headers.get('X-Frappe-Site-Name') or get_site_name(request.host)
	frappe.init(site=site, sites_path=_sites_path)

	if not (frappe.local.conf and frappe.local.conf.db_name):
		# site does not exist
		raise NotFound

def make_form_dict(request):
	frappe.local.form_dict = frappe._dict({ k:v[0] if isinstance(v, (list, tuple)) else v \
		for k, v in (request.form or request.args).iteritems() })

	if "_" in frappe.local.form_dict:
		# _ is passed by $.ajax so that the request is not cached by the browser. So, remove _ from form_dict
		frappe.local.form_dict.pop("_")

application = local_manager.make_middleware(application)
application.debug = True


def serve(port=8000, profile=False, site=None, sites_path='.'):
	global application, _site, _sites_path
	_site = site
	_sites_path = sites_path

	from werkzeug.serving import run_simple

	if profile:
		application = ProfilerMiddleware(application, sort_by=('tottime', 'calls'))

	if not os.environ.get('NO_STATICS'):
		application = SharedDataMiddleware(application, {
			b'/assets': os.path.join(sites_path, 'assets').encode("utf-8"),
		})

		application = StaticDataMiddleware(application, {
			b'/files': os.path.abspath(sites_path).encode("utf-8")
		})

	application.debug = True
	application.config = {
		'SERVER_NAME': 'localhost:8000'
	}

	run_simple('0.0.0.0', int(port), application, use_reloader=True,
		use_debugger=True, use_evalex=True, threaded=True)
