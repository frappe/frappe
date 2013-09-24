import sys, os
import json

sys.path.insert(0, '.')
sys.path.insert(0, 'app')
sys.path.insert(0, 'lib')

from werkzeug.wrappers import Request, Response
from werkzeug.local import LocalManager
from werkzeug.wsgi import SharedDataMiddleware
from webnotes import get_config

import mimetypes
import webnotes
import webnotes.handler
import webnotes.auth
import webnotes.webutils

local_manager = LocalManager([webnotes.local])

class MyResponse(Response):
	def set_cookie(self, *args, **kwargs):
		print args, kwargs
		super(Response, self).set_cookie(*args, **kwargs)

@Request.application
def application(request):
	webnotes.local.request = request
	
	webnotes.init(site=request.host)

	webnotes.local.form_dict = webnotes._dict({ k:v[0] if isinstance(v, (list, tuple)) else v \
		for k, v in (request.form or request.args).iteritems() })
			
	webnotes.local._response = MyResponse()

	try:
		webnotes.http_request = webnotes.auth.HTTPRequest()
	except webnotes.AuthenticationError, e:
		pass
	
	if webnotes.form_dict.cmd:
		webnotes.handler.handle()
	else:
		webnotes.webutils.render(webnotes.request.path[1:])
		
	return webnotes._response

application = local_manager.make_middleware(application)


application = SharedDataMiddleware(application, {
	'/': os.path.join(os.path.dirname(__file__), "..", "..", "public")
})

if __name__ == '__main__':
	import sys
	from werkzeug.serving import run_simple
	
	port = 8000
	if len(sys.argv) > 1:
		port = sys.argv[1]

	run_simple('0.0.0.0', int(port), application, use_reloader=True, 
		use_debugger=True, use_evalex=True)

