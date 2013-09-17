import sys, os

sys.path.extend([".", "app", "lib"])	

from werkzeug.wrappers import Request, Response
from werkzeug.local import LocalManager
from werkzeug.wsgi import SharedDataMiddleware

import mimetypes
import webnotes
import webnotes.handler
import webnotes.auth
import webnotes.webutils

local_manager = LocalManager([webnotes.local])

@Request.application
def application(request):
	webnotes.local.request = request
	
	webnotes.init()
		
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
	
	return webnotes._response

application = local_manager.make_middleware(application)


application = SharedDataMiddleware(application, {
	'/': os.path.join(os.path.dirname(__file__), "..", "..", "public")
})

if __name__ == '__main__':
	import sys
	from werkzeug.serving import run_simple

	run_simple('localhost', 8000, application, use_reloader=True, 
		use_debugger=True, use_evalex=True)

