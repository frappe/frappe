"""
Server side handler for "Form" events
"""

import webnotes
import webnotes.model.doc
import webnotes.model.meta
from webnotes.model.triggers import fire_event

def getdoc():
	"""
	Loads a doclist for a given document. This method is called directly from the client.
	Requries "doctype", "docname" as form variables. If "from_archive" is set, it will get from archive.
	Will also call the "onload" method on the document.
	"""

	import webnotes
	from webnotes.utils import cint
	
	form = webnotes.form_dict
	doctype, docname = form.get('doctype'), form.get('name')
	prefix = cint(form.get('from_archive')) and 'arc' or 'tab'

	if not (doctype and docname):
		raise Exception, 'doctype and name required!'
	
	doclist = []
	# single
	doclist = load_single_doc(doctype, docname, (form.get('user') or webnotes.session['user']), prefix)
	
	# load doctype along with the doc
	if form.get('getdoctype'):
		import webnotes.model.doctype
		doclist += webnotes.model.doctype.get(doctype)

	# tag as archived
	if prefix == 'arc':
		doclist[0].__archived=1

	webnotes.response['docs'] = doclist

#===========================================================================================

def get_comments(doctype=None, docname=None, limit=5):
	nc, cl = 0, []

	if not doctype:
		doctype, docname, limit = webnotes.form_dict.get('dt'), webnotes.form_dict.get('dn'), webnotes.form_dict.get('limit')
		
	try:
		nc = int(webnotes.conn.sql("select count(*) from `tabComment Widget Record` where comment_doctype=%s and comment_docname=%s", (doctype, docname))[0][0])
		if nc:
			cl = webnotes.conn.sql("select comment, ifnull(comment_by_fullname, comment_by) AS 'comment_by_fullname', creation from `tabComment Widget Record` where comment_doctype=%s and comment_docname=%s order by creation desc limit %s" % ('%s','%s',limit), (doctype, docname), as_dict=1)

	except Exception, e:
		if e.args[0]==1146:
			# no table
			make_comment_table()
		else:
			raise e

	webnotes.response['n_comments'], webnotes.response['comment_list'] = nc, cl

#
# make comment table
#
def make_comment_table():
	"Make table for comments - if missing via import module"
	webnotes.conn.commit()
	from webnotes.modules import reload_doc
	reload_doc('core', 'doctype', 'comment_widget_record')
	webnotes.conn.begin()	
	
#===========================================================================================

def add_comment():
	import time
	args = webnotes.form_dict

	if args.get('comment'):
		from webnotes.model.doc import Document
		from webnotes.utils import nowdate
		
		cmt = Document('Comment Widget Record')
		for arg in ['comment', 'comment_by', 'comment_by_fullname', 'comment_doctype', 'comment_docname']:
			cmt.fields[arg] = args[arg]
		cmt.comment_date = nowdate()
		cmt.comment_time = time.strftime('%H:%M')
		cmt.save(1)
  			
#===========================================================================================

def remove_comment():
	args = webnotes.form_dict
	webnotes.conn.sql("delete from `tabComment Widget Record` where name=%s",args.get('id'))

	try:
		get_obj('Feed Control').upate_comment_in_feed(args['dt'], args['dn'])
	except: pass

#===========================================================================================

def getdoctype():
	# load parent doctype too
	import webnotes.model.doctype
	
	form, doclist = webnotes.form, []
	
	dt = form.getvalue('doctype')
	with_parent = form.getvalue('with_parent')

	# with parent (called from report builder)
	if with_parent:
		parent_dt = webnotes.model.meta.get_parent_dt(dt)
		if parent_dt:
			doclist = webnotes.model.doctype.get(parent_dt)
			webnotes.response['parent_dt'] = parent_dt
	
	if not doclist:
		doclist = webnotes.model.doctype.get(dt)
	
	# if single, send the record too
	if doclist[0].issingle:
		doclist += webnotes.model.doc.get(dt)

	# load search criteria for reports (all)
	doclist += webnotes.model.meta.get_search_criteria(dt)


	webnotes.response['docs'] = doclist

#===========================================================================================

def load_single_doc(dt, dn, user, prefix):
	import webnotes.model.code

	if not dn: dn = dt
	dl = webnotes.model.doc.get(dt, dn, prefix=prefix)

	# archive, done
	if prefix=='arc':
		return dl

	try:
		so, r = webnotes.model.code.get_server_obj(dl[0], dl), None
		if hasattr(so, 'onload'):
			r = webnotes.model.code.run_server_obj(so, 'onload')
		if hasattr(so, 'custom_onload'):
			r = webnotes.model.code.run_server_obj(so, 'custom_onload')
		if r: 
			webnotes.msgprint(r)
	except Exception, e:
		webnotes.errprint(webnotes.utils.getTraceback())
		webnotes.msgprint('Error in script while loading')
		raise e

	if dl and not dn.startswith('_'):
		webnotes.user.update_recent(dt, dn)

	# load search criteria ---- if doctype
	if dt=='DocType':
		dl += webnotes.model.meta.get_search_criteria(dt)

	return dl

# Check Guest Access
#===========================================================================================
def check_guest_access(doc):
	if webnotes.session['user']=='Guest' and not webnotes.conn.sql("select name from tabDocPerm where role='Guest' and parent=%s and ifnull(`read`,0)=1", doc.doctype):
		webnotes.msgprint("Guest not allowed to call this object")
		raise Exception

# Runserverobj - run server calls from form
#===========================================================================================

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
		doclist.from_compressed(form.getvalue('docs'), form.getvalue('docname'))
		so = doclist.make_obj()
		
	check_guest_access(so.doc)
				
	if so:
		r = webnotes.model.code.run_server_obj(so, method, arg)
		if r:			
			#build output as csv
			if cint(webnotes.form.getvalue('as_csv')):
				make_csv_output(r, so.doc.doctype)
			else:
				webnotes.response['message'] = r
		
		if doclist:
			webnotes.response['docs'] = doclist.docs

def make_csv_output(res, dt):
	import webnotes
	from webnotes.utils import getCSVelement

	txt = []
	if type(res)==list:
		for r in res:
			txt.append(','.join([getCSVelement(i) for i in r]))
		
		txt = '\n'.join(txt)
	
	else:
		txt = 'Output was not in list format\n' + r
					
	webnotes.response['result'] = txt
	webnotes.response['type'] = 'csv'
	webnotes.response['doctype'] = dt.replace(' ','')						


def savedocs():
	try:
		from webnotes.model.doclist import DocList
		form = webnotes.form_dict

		doclist = DocList()
		doclist.from_compressed(form.get('docs'), form.get('docname'))

		# action
		action = form.get('action')

		if action=='Update': action='update_after_submit'

		getattr(doclist, action.lower())()

		# update recent documents
		webnotes.user.update_recent(doclist.doc.doctype, doclist.doc.name)

		# send updated docs
		webnotes.response['saved'] = '1'
		webnotes.response['main_doc_name'] = doclist.doc.name
		webnotes.response['docname'] = doclist.doc.name
		webnotes.response['docs'] = [doclist.doc] + doclist.children

	except Exception, e:
		webnotes.msgprint('Did not save')
		webnotes.errprint(webnotes.utils.getTraceback())
		raise e


# Print Format
#===========================================================================================
def _get_print_format(match):
	name = match.group('name')
	return webnotes.model.meta.get_print_format_html(name)

def get_print_format():
	import re
	import webnotes

	html = webnotes.model.meta.get_print_format_html(webnotes.form.getvalue('name'))

	p = re.compile('\$import\( (?P<name> [^)]*) \)', re.VERBOSE)
	out_html = ''
	if html: 
		out_html = p.sub(_get_print_format, html)

	webnotes.response['message'] = out_html
	
# remove attachment
#===========================================================================================

def remove_attach():
	import webnotes
	import webnotes.utils.file_manager
	
	fid = webnotes.form.getvalue('fid')
	webnotes.utils.file_manager.delete_file(fid, verbose=1)

# Get Fields - Counterpart to $c_get_fields
#===========================================================================================
def get_fields():
	import webnotes
	r = {}
	args = {
		'select':webnotes.form.getvalue('select')
		,'from':webnotes.form.getvalue('from')
		,'where':webnotes.form.getvalue('where')
	}
	ret = webnotes.conn.sql("select %(select)s from `%(from)s` where %(where)s limit 1" % args)
	if ret:
		fl, i = webnotes.form.getvalue('fields').split(','), 0
		for f in fl:
			r[f], i = ret[0][i], i+1
	webnotes.response['message']=r

# validate link
#===========================================================================================
def validate_link():
	import webnotes
	import webnotes.utils
	
	value, options, fetch = webnotes.form.getvalue('value'), webnotes.form.getvalue('options'), webnotes.form.getvalue('fetch')

	# no options, don't validate
	if not options or options=='null' or options=='undefined':
		webnotes.response['message'] = 'Ok'
		return
		
	if webnotes.conn.sql("select name from `tab%s` where name=%s" % (options, '%s'), value):
	
		# get fetch values
		if fetch:
			webnotes.response['fetch_values'] = [webnotes.utils.parse_val(c) for c in webnotes.conn.sql("select %s from `tab%s` where name=%s" % (fetch, options, '%s'), value)[0]]
	
		webnotes.response['message'] = 'Ok'
