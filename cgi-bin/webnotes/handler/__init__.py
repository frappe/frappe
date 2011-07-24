# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (@rushabh_mehta)
# Handler design goal, no class should set webnotes.*
# We want biryani not speghatti
#TODO cleanup commented code that is not required
import webnotes
def handle(reqflds):
	"""
	Handle client requests
	"""
	from webnotes.handler.request import HTTPRequest
	from webnotes.handler.response import HTTPResponse
	from webnotes.handler.session import Session
	from webnotes.handler.login import LoginManager
	from webnotes.handler.cookie import CookieManager

	webnotes.request = HTTPRequest(reqflds)
	webnotes.response = HTTPResponse()
#	webnotes.session = Session()
	webnotes.login_manager = LoginManager()
	webnotes.cookie_manager = CookieManager()
	load_session()
	check_status()
#	raise Exception, webnotes.session
#	if webnotes.request.form.get('sid'):
#		webnotes.cookie_manager.set_cookies()
	setup_profile()
	
	# there are two types of request - one for a full page
	# and other for ajax via the "action" property
	#raise Exception, str(webnotes.request.form.get('cmd'))
	if webnotes.request.cmd and webnotes.request.cmd!='login' :
		try:
			webnotes.response['message']=webnotes.request.execute()
			print webnotes.response.to_string()
		except webnotes.ValidationError:
			webnotes.conn.rollback()
		except:
			webnotes.errprint(webnotes.utils.getTraceback())
			webnotes.conn and webnotes.conn.rollback()
	else:
		from webnotes.handler import index
		index.build()
		print webnotes.response.to_string()
	#	print webnotes.response.pagehtml
def load_session():
	"""
		Load the session object
	"""
	webnotes.session_obj = session.Session()
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
