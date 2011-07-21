import webnotes
class CookieManager:
	def __init__(self,request):
		import Cookie
		self.cookies = Cookie.SimpleCookie()
		self.get_incoming_cookies()
		self.request = request

	def get_incoming_cookies(self):
		import os
		cookies = {}
		if 'HTTP_COOKIE' in os.environ:
			c = os.environ['HTTP_COOKIE']
			self.cookies.load(c)
			for c in self.cookies.values():
				cookies[c.key] = c.value
					
		webnotes.incoming_cookies = cookies
		
	
	def set_cookies(self):
		if webnotes.conn.cur_db_name:
			self.cookies['account_id'] = webnotes.conn.cur_db_name
		
		# ac_name	
		self.cookies['ac_name'] = webnotes.ac_name or ''
		
		#FIXME
		if webnotes.session.get('sid'): 
			self.cookies['sid'] = webnotes.session['sid']

			# sid expires in 3 days
			import datetime
			expires = datetime.datetime.now() + datetime.timedelta(days=3)

			self.cookies['sid']['expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S')		


	def set_remember_me(self):
		if webnotes.utils.cint(self.request.remember_me):
			remember_days = webnotes.conn.get_value('Control Panel',None,'remember_for_days') or 7
			self.cookies['remember_me'] = 1

			import datetime
			expires = datetime.datetime.now() + datetime.timedelta(days=remember_days)

			for k in self.cookies.keys():
				self.cookies[k]['expires'] = expires.strftime('%a, %d %b %Y %H:%M:%S')	


