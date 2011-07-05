# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (@rushabh_mehta)

def handle():
	"""
	Handle client requests
	"""
	from chai.handler.request import HTTPRequest
	from chai.handler.response import HTTPResponse
	from chai.handler.session import Session

	chai.request = HTTPRequest()
	chai.session = Session()
	chai.response = HTTPResponse()
	
	# there are two types of request - one for a full page
	# and other for ajax via the "action" property
	if chai.request.form.get('action'):
		chai.request.execute()
	else:
		from chai.handler import index
		index.build()

	print chai.response.to_string()