"""trigger doctype events"""

def trigger(method, doc):
	try:
		import startup.event_handlers
	except ImportError:
		return
		
	if hasattr(startup.event_handlers, method):
		getattr(startup.event_handlers, method)(doc)
		
	if hasattr(startup.event_handlers, 'doclist_all'):
		startup.event_handlers.doclist_all(doc, method)
		