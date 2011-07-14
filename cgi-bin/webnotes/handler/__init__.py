# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (@rushabh_mehta)
import webnotes
def handle():
	"""
	Handle client requests
	"""
	from webnotes.handler.request import HTTPRequest
	from webnotes.handler.response import HTTPResponse
	from webnotes.handler.session import Session

	webnotes.request = HTTPRequest()
#	webnotes.session = Session()
	webnotes.response = HTTPResponse()
	
	# there are two types of request - one for a full page
	# and other for ajax via the "action" property
	#raise Exception, str(webnotes.request.form.get('cmd'))
	if webnotes.request.form.get('cmd') or 1:
		try:
			webnotes.request.execute()
		except webnotes.ValidationError:
			webnotes.conn.rollback()
		except:
			webnotes.errprint(webnotes.utils.getTraceback())
			webnotes.conn and webnotes.conn.rollback()

#else:
#		from webnotes.handler import index
#		index.build()
	print webnotes.response.to_string()
