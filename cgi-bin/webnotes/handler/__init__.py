# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (@rushabh_mehta)
# Handler design goal, no class should set webnotes.*
# We want biryani not speghatti
import webnotes
def handle(reqflds):
	"""
	Handle client requests
	"""
	from webnotes.handler.request import HTTPRequest
	from webnotes.handler.response import HTTPResponse
	from webnotes.handler.session import Session

	webnotes.request = HTTPRequest(reqflds)
#	webnotes.session = Session()
#	webnotes.login_manager = webnotes.handler.session.LoginManager()
#	load_session()
#	webnotes.cookie_manager = webnotes.handler.session.CookieManager()
	check_status()
#	if webnotes.request.form.get('sid'):
#		webnotes.cookie_manager.set_cookies()
#	setup_profile()
	webnotes.response = HTTPResponse()
	
	# there are two types of request - one for a full page
	# and other for ajax via the "action" property
	#raise Exception, str(webnotes.request.form.get('cmd'))
	if hasattr(webnotes.request,'cmd') or 1:
		try:
			webnotes.response['message']=webnotes.request.execute()
		except webnotes.ValidationError:
			webnotes.conn.rollback()
		except:
			webnotes.errprint(webnotes.utils.getTraceback())
			webnotes.conn and webnotes.conn.rollback()

#else:
#		from webnotes.handler import index
#		index.build()
	print webnotes.response.to_string()
def load_session():
	"""
		Load the session object
	"""
	webnotes.session_obj = webnotes.handler.session.Session()
	webnotes.session = webnotes.session_obj.data
	webnotes.tenant_id = webnotes.session.get('tenant_id', 0)
def check_status():
	"""
		Check session status
	"""
	if webnotes.conn.get_global("__session_status")=='stop':
		webnotes.msgprint(webnotes.conn.get_global("__session_status_message"))
		raise Exception
def setup_profile():
	"""
		Setup Profile
	"""
	webnotes.user = webnotes.profile.Profile()
	# load the profile data
	if webnotes.session['data'].get('profile'):
		webnotes.user.load_from_session(webnotes.session['data']['profile'])
	else:
		webnotes.user.load_profile()	
