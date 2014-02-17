# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

import sys, os
import json

from werkzeug.wrappers import Request, Response
from werkzeug.local import LocalManager
from werkzeug.wsgi import SharedDataMiddleware
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.contrib.profiler import ProfilerMiddleware

import mimetypes
import frappe
import frappe.handler
import frappe.auth
import frappe.api
import frappe.website.render
from frappe.utils import get_site_name

local_manager = LocalManager([frappe.local])

_site = None
_sites_path = '.'

def handle_session_stopped():
	res = Response("""<html>
							<body style="background-color: #EEE;">
									<h3 style="width: 900px; background-color: #FFF; border: 2px solid #AAA; padding: 20px; font-family: Arial; margin: 20px auto">
											Updating.
											We will be back in a few moments...
									</h3>
							</body>
					</html>""")
	res.status_code = 503
	res.content_type = 'text/html'
	return res

@Request.application
def application(request):
	frappe.local.request = request
	
	try:
		site = _site or get_site_name(request.host)
		frappe.init(site=site, sites_path=_sites_path)
		
		if not frappe.local.conf:
			# site does not exist
			raise NotFound
		
		frappe.local.form_dict = frappe._dict({ k:v[0] if isinstance(v, (list, tuple)) else v \
			for k, v in (request.form or request.args).iteritems() })
				
		frappe.local._response = Response()
		frappe.http_request = frappe.auth.HTTPRequest()

		if frappe.local.form_dict.cmd:
			frappe.handler.handle()
		elif frappe.request.path.startswith("/api/"):
			frappe.api.handle()
		elif frappe.local.request.method in ('GET', 'HEAD'):
			frappe.website.render.render(frappe.request.path[1:])
		else:
			raise NotFound

	except HTTPException, e:
		return e
		
	except frappe.AuthenticationError, e:
		frappe._response.status_code=401
		
	except frappe.SessionStopped, e:
		frappe.local._response = handle_session_stopped()
		
	finally:
		if frappe.conn:
			frappe.conn.close()
	
	return frappe.local._response

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
	
	if site:
		application = SharedDataMiddleware(application, {
			'/files': os.path.join(sites_path, site, 'public', 'files')
		})

	run_simple('0.0.0.0', int(port), application, use_reloader=True, 
		use_debugger=True, use_evalex=True)
