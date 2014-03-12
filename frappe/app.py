# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

import sys, os
import json

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

@Request.application
def application(request):
	frappe.local.request = request
	response = Response()
	
	try:
		rollback = True
		
		init_site(request)
		make_form_dict(request)
		frappe.local.http_request = frappe.auth.HTTPRequest()
		
		if frappe.local.form_dict.cmd:
			frappe.handler.handle()
		
		elif frappe.request.path.startswith("/api/"):
			frappe.api.handle()
		
		elif frappe.request.path.startswith('/backups'):
			frappe.utils.response.download_backup(request.path, response=response)
		
		elif frappe.local.request.method in ('GET', 'HEAD'):
			frappe.website.render.render(request.path, response=response)
		
		else:
			raise NotFound

	except HTTPException, e:
		return e
		
	except frappe.SessionStopped, e:
		response = frappe.utils.response.handle_session_stopped()
		
	except (frappe.AuthenticationError,
		frappe.PermissionError,
		frappe.DoesNotExistError,
		frappe.DuplicateEntryError,
		frappe.OutgoingEmailError,
		frappe.ValidationError), e:
		
		frappe.utils.response.report_error(e.http_status_code, response=response)
		
		if e.__class__ == frappe.AuthenticationError:
			frappe.local.login_manager.clear_cookies()
	
	else:
		if frappe.local.request.method in ("POST", "PUT") and frappe.db:
			frappe.db.commit()
			rollback = False
	
	finally:
		if frappe.local.request.method in ("POST", "PUT") and frappe.db and rollback:
			frappe.db.rollback()
			
		if frappe.local.form_dict.cmd or frappe.request.path.startswith("/api/"):
			if not frappe.local.response.get("type"):
				frappe.local.response["type"] = "json"
			
			frappe.utils.response.build_response(response=response)
		
		# set cookies
		frappe.local.cookie_manager.flush_cookies(response=response)
		
		frappe.destroy()
		
	return response
	
def init_site(request):
	site = _site or get_site_name(request.host)
	frappe.init(site=site, sites_path=_sites_path)
	
	if not frappe.local.conf:
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
		application = ProfilerMiddleware(application)

	if not os.environ.get('NO_STATICS'):
		application = SharedDataMiddleware(application, {
			'/assets': os.path.join(sites_path, 'assets'),
		})
	
		application = StaticDataMiddleware(application, {
			'/files': os.path.abspath(sites_path)
		})
		
	run_simple('0.0.0.0', int(port), application, use_reloader=True, 
		use_debugger=True, use_evalex=True)
