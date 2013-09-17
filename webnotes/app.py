import sys, os

sys.path.extend(["..", "../app", "../lib"])	

from werkzeug.wrappers import Request, Response
from werkzeug.local import LocalManager

import mimetypes
import webnotes
import webnotes.handler
import webnotes.auth
import webnotes.webutils

local_manager = LocalManager([webnotes.local])

@Request.application
def application(request):
	path = os.path.join("public", request.path[1:])
	if os.path.exists(path) and not os.path.isdir(path) and not path.endswith(".py"):
		with open(path, "r") as static:
			content = static.read()
		
		response = Response()
		response.data = content
		response.headers["Content-type"] = mimetypes.guess_type(path)[0]
		return response
	
	else:
		webnotes.local.request = request
		webnotes.init()
				
		webnotes.local.form_dict = webnotes._dict({ k:v[0] if isinstance(v, (list, tuple)) else v \
			for k, v in (request.form or request.args).iteritems() })
				
		webnotes.local._response = Response()

		try:
			webnotes.http_request = webnotes.auth.HTTPRequest()
		except webnotes.AuthenticationError, e:
			pass

		# cookies
		print request.form
		
		if webnotes.form_dict.cmd:
			webnotes.handler.handle()
		else:
			webnotes.webutils.render(webnotes.request.path[1:])
		
		return webnotes._response

application = local_manager.make_middleware(application)

if __name__ == '__main__':
	import sys
	from werkzeug.serving import run_simple

	run_simple('localhost', 8000, application, use_reloader=True, use_debugger=True, use_evalex=True)