import sys, os
import json

sys.path.insert(0, '.')
sys.path.insert(0, 'app')
sys.path.insert(0, 'lib')

from werkzeug.wrappers import Request, Response
from werkzeug.local import LocalManager
from webnotes.middlewares import StaticDataMiddleware
from werkzeug.exceptions import HTTPException
from werkzeug.contrib.profiler import ProfilerMiddleware
from webnotes import get_config

import mimetypes
import webnotes
import webnotes.handler
import webnotes.auth
import webnotes.webutils

local_manager = LocalManager([webnotes.local])

@Request.application
def application(request):
	webnotes.local.request = request
	
	try:
		site = webnotes.utils.get_site_name(request.host)
		webnotes.init(site=site)
		
		webnotes.local.form_dict = webnotes._dict({ k:v[0] if isinstance(v, (list, tuple)) else v \
			for k, v in (request.form or request.args).iteritems() })
				
		webnotes.local._response = Response()

		try:
			webnotes.http_request = webnotes.auth.HTTPRequest()
		except webnotes.AuthenticationError, e:
			pass
		
		if webnotes.form_dict.cmd:
			webnotes.handler.handle()
		else:
			webnotes.webutils.render(webnotes.request.path[1:])

	except HTTPException, e:
		return e
		
	finally:
		if webnotes.conn:
			webnotes.conn.close()
	
	return webnotes._response

application = local_manager.make_middleware(application)


application = StaticDataMiddleware(application, {
	'/': 'public',
})


def serve(port=8000, profile=False):
	global application
	from werkzeug.serving import run_simple
	if profile:
		application = ProfilerMiddleware(application)
	run_simple('0.0.0.0', int(port), application, use_reloader=True, 
		use_debugger=True, use_evalex=True)
