import webnotes
import webnotes.utils

class FrameworkServer:
	"""
	   Connect to a remote server via HTTP (webservice).
	   
	   * `host` is the the address of the remote server
	   * `path` is the path of the Framework (excluding index.cgi)
	"""
	def __init__(self, host, path, user='', password='', account='', cookies=None, opts=None, https = 0):
		# validate
		if not (host and path):
			raise Exception, "Server address and path necessary"

		if not ((user and password) or (cookies)):
			raise Exception, "Either cookies or user/password necessary"
	
		self.host = host
		self.base_path = path
		self.cookies = cookies or {}
		self.account = account
		self.account_id = None
		self.https = https
		self.conn = None

		# login
		if not cookies:
			args = { 'usr': user, 'pwd': password, 'acx': account }
			
			if opts:
				args.update(opts)
			
			res = self.get_response('POST', 'login', args)
						
			if 'message' in ret and ret['message']!='Logged In':
				webnotes.msgprint(ret.get('server_messages'), raise_exception=1)
								
			self.account_id = self.cookies.get('account_id')
			self.sid = self.cookies.get('sid')
			
			self.login_response = res
			self.login_return = ret

	# -----------------------------------------------------------------------------------------

	def make_request(self, method, path, args={}):
		import urllib, urllib2, os

		# base_path not to be from root
		if self.base_path.startswith('/'): self.base_path = self.base_path[1:]
		
		protocol = self.https and 'https://' or 'http://'
		
		# set path equal to base path + relative path
		path = os.path.join(self.base_path, path)
		
		# make the request
		req = urllib2.Request(protocol + os.path.join(self.host, path, 'index.cgi'), urllib.urlencode(args))

		# add cookies to the request
		for key in self.cookies:
			req.add_header('cookie', '; '.join(['%s=%s' % (key, self.cookies[key]) for key in self.cookies]))

		# override the get_method to return user asked method
		req.get_method = lambda: method
		
	def get_response(self, method, path, args):
		"""
		Run a method on the remote server, with the given arguments
		"""
		# get response from remote server
	
		import urllib2
		request = make_request(method, path, args)

		res = urllib2.urlopen(req)
		# extract cookies
		self._extract_cookies(res)

		ret_json = json.loads(req.read())
		
		if ret_json['exc']:
			raise Exception, 'Host Exception:\n' + ret_json['exc']
			
		return ret_json
