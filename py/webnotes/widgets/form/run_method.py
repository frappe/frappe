import webnotes

@webnotes.whitelist()
def runserverobj():
	"""
		Run server objects
	"""
	import webnotes.model.code
	from webnotes.model.doclist import DocList
	from webnotes.utils import cint

	form = webnotes.form

	doclist = None
	method = form.getvalue('method')
	arg = form.getvalue('arg')
	dt = form.getvalue('doctype')
	dn = form.getvalue('docname')

	if dt: # not called from a doctype (from a page)
		if not dn: dn = dt # single
		so = webnotes.model.code.get_obj(dt, dn)

	else:
		doclist = DocList()
		doclist.from_compressed(form.getvalue('docs'), dn)
		so = doclist.make_obj()
		doclist.check_if_latest()

	check_guest_access(so.doc)
	
	if so:
		r = webnotes.model.code.run_server_obj(so, method, arg)
		if r:
			#build output as csv
			if cint(webnotes.form.getvalue('as_csv')):
				make_csv_output(r, so.doc.doctype)
			else:
				webnotes.response['message'] = r
		
		webnotes.response['docs'] =[so.doc] + so.doclist

def check_guest_access(doc):
	if webnotes.session['user']=='Guest' and not webnotes.conn.sql("select name from tabDocPerm where role='Guest' and parent=%s and ifnull(`read`,0)=1", doc.doctype):
		webnotes.msgprint("Guest not allowed to call this object")
		raise Exception

def make_csv_output(res, dt):
	"""send method response as downloadable CSV file"""
	import webnotes
	
	from cStringIO import StringIO
	import csv
	
	f = StringIO()
	writer = csv.writer(f)
	for r in res:
		writer.writerow(r)
	
	f.seek(0)
						
	webnotes.response['result'] = f.read()
	webnotes.response['type'] = 'csv'
	webnotes.response['doctype'] = dt.replace(' ','')		