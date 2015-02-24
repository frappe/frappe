# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import sys, os
import json
import logging

from werkzeug.wrappers import Request, Response
from werkzeug.local import LocalManager
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.contrib.profiler import ProfilerMiddleware
from werkzeug.wsgi import SharedDataMiddleware

import mimetypes
import frappe
import frappe.handler
import frappe.auth
import frappe.api
import frappe.utils.response
import frappe.website.render
from frappe.utils import get_site_name
from frappe.middlewares import StaticDataMiddleware

local_manager = LocalManager([frappe.local])

_site = None
_sites_path = os.environ.get("SITES_PATH", ".")

logger = frappe.get_logger()

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

		if frappe.local.is_ajax:
			response = frappe.utils.response.report_error(http_status_code)
		else:
			frappe.respond_as_web_page("Server Error",
				"<pre>"+frappe.get_traceback()+"</pre>",
				http_status_code=http_status_code)
			response = frappe.website.render.render("message", http_status_code=http_status_code)

		if e.__class__ == frappe.AuthenticationError:
			if hasattr(frappe.local, "login_manager"):
				frappe.local.login_manager.clear_cookies()

		if http_status_code==500:
			logger.error('Request Error')

	else:
		if frappe.local.request.method in ("POST", "PUT") and frappe.db:
			frappe.db.commit()
			rollback = False

		# update session
		if getattr(frappe.local, "session_obj", None):
			updated_in_db = frappe.local.session_obj.update()
			if updated_in_db:
				frappe.db.commit()

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

application = local_manager.make_middleware(application)

def serve(port=8000, profile=False, site=None, sites_path='.'):
	global application, _site, _sites_path
	_site = site
	_sites_path = sites_path

	from werkzeug.serving import run_simple

	if profile:
		application = ProfilerMiddleware(application, sort_by=('tottime', 'calls'))

	if not os.environ.get('NO_STATICS'):
		application = SharedDataMiddleware(application, {
			'/assets': os.path.join(sites_path, 'assets'),
		})

		application = StaticDataMiddleware(application, {
			'/files': os.path.abspath(sites_path)
		})

	run_simple('0.0.0.0', int(port), application, use_reloader=True,
		use_debugger=True, use_evalex=True, threaded=True)
