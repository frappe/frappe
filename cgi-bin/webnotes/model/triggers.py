"""
Add, manage, fire triggers (events / observers)
Standard events called by the framework are "save, submit, cancel"
"""

import webnotes

def insert_trigger(doctype, docname, event_name, method):
	"inserts a new trigger record"
	
	from webnotes.model.doc import Document
	d = Document('DocTrigger')
	d.doc_type = doctype
	d.doc_name = docname
	d.event_name = event_name
	d.method = method
	d.save(1)
	
def add_trigger(doctype, docname, event_name, method):
	"""Add a trigger to an event on a doctype, docname. The specified method will be called.
	Wild card '*' is allowed in doctype, docname and/or event_name"""

	try:
		if not trigger_exists(doctype, docname, event_name, method):
			insert_trigger(doctype, docname, event_name, method)
	except Exception, e:
		if e.args[0]==1146: 
			setup()
			insert_trigger(doctype, docname, event_name, method)
		else: raise e

def trigger_exists(doctype, docname, event_name, method):
	"returns true if trigger exists"
	return webnotes.conn.sql("select name from tabDocTrigger where doc_name=%s and doc_type=%s and event_name=%s and method=%s", \
		(doctype, docname, event_name, method))

def remove_trigger(doctype, docname, event_name, method):
	"Remove a trigger on an event"
	webnotes.conn.sql("delete from tabDocTrigger where doc_name=%s and doc_type=%s and event_name=%s and method=%s", \
		(doctype, docname, event_name, method))
	
def fire_event(doc, event_name):
	"Fire all triggers on an event and passes the doc to the trigger"
	try:
		tl = webnotes.conn.sql("""select method from tabDocTrigger 
			where (doc_type=%s or doc_type='*')
			and (doc_name=%s or doc_name='*')
			and (event_name=%s or event_name='*')""", (doc.doctype, doc.name, event_name))
	except Exception, e:
		if e.args[0]==1146:
			setup()
			tl = []
		else: raise e
		
	for t in tl:
		module, method = '.'.join(t[0].split('.')[:-1]), t[0].split('.')[-1]
		exec 'from %s import %s' % (module, method) in locals()
		locals()[method](doc, method)
#
# setup
#
def setup():
	"creates the DocTrigger table from core"
	webnotes.conn.commit()
	from webnotes.modules.module_manager import reload_doc
	reload_doc('core','doctype','doctrigger')
	webnotes.conn.begin()
	