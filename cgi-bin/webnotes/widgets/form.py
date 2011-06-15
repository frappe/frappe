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
	
	form = webnotes.form
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
		doctype, docname, limit = webnotes.form.get('dt'), webnotes.form.get('dn'), webnotes.form.get('limit')
		
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
	args = webnotes.form

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
	args = webnotes.form
	webnotes.conn.sql("delete from `tabComment Widget Record` where name=%s",args.get('id'))

	try:
		get_obj('Feed Control').upate_comment_in_feed(args['dt'], args['dn'])
	except: pass

#===========================================================================================

def getdoctype():
	# load parent doctype too
	import webnotes.model.doctype
	
	form, doclist = webnotes.form, []
	
	dt = form.get('doctype')
	with_parent = form.get('with_parent')

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
	import webnotes.model.code
	import webnotes.model.doclist
	from webnotes.utils import cint

	form = webnotes.form


	method = form.get('method')
	doclist, clientlist = [], []
	arg = form.get('arg')
	dt = form.get('doctype')
	dn = form.get('docname')
		
	if dt: # not called from a doctype (from a page)
		if not dn: dn = dt # single
		so = webnotes.model.code.get_obj(dt, dn)

	else:
		clientlist = webnotes.model.doclist.expand(form.get('docs'))

		# find main doc
		for d in clientlist:
			if cint(d.get('docstatus')) != 2 and not d.get('parent'):
				main_doc = webnotes.model.doc.Document(fielddata = d)
	
		# find child docs
		for d in clientlist:
			doc = webnotes.model.doc.Document(fielddata = d)
			if doc.fields.get('parent'):
				doclist.append(doc)	
	
		so = webnotes.model.code.get_server_obj(main_doc, doclist)

	# check integrity
	if not check_integrity(so.doc):
		return
		
	check_guest_access(so.doc)
				
	if so:
		r = webnotes.model.code.run_server_obj(so, method, arg)
		doclist = so.doclist # reference back [in case of null]
		if r:
			try:
				if r['doclist']:
					clientlist += r['doclist']
			except:
				pass
			
			#build output as csv
			if cint(webnotes.form.get('as_csv')):
				make_csv_output(r, so.doc.doctype)
			else:
				webnotes.response['message'] = r
		
		if clientlist:
			doclist.append(main_doc)
			webnotes.response['docs'] = doclist

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


# Document Save
#===========================================================================================

def _get_doclist(clientlist):
	# converts doc dictionaries into Document objects

	from webnotes.model.doc import Document
	form = webnotes.form

	midx = 0
	for i in range(len(clientlist)):
		if clientlist[i]['name'] == form.get('docname'):
			main_doc = Document(fielddata = clientlist[i])
			midx = i
		else:
			clientlist[i] = Document(fielddata = clientlist[i])

	del clientlist[midx]
	return main_doc, clientlist

def _do_action(doc, doclist, so, method_name, docstatus=0):

	from webnotes.model.code import run_server_obj
	set = webnotes.conn.set

	if so and hasattr(so, method_name):
		errmethod = method_name
		run_server_obj(so, method_name)
		if hasattr(so, 'custom_'+method_name):
			run_server_obj(so, 'custom_'+method_name)
		errmethod = ''

	# fire triggers observers (if any)
	fire_event(doc, method_name)

	# set docstatus for all children records
	if docstatus:
		for d in [doc] + doclist:
			if int(d.docstatus or 0) != 2:
				set(d, 'docstatus', docstatus)

def check_integrity(doc):
	import webnotes
		
	if (not webnotes.model.meta.is_single(doc.doctype)) and (not doc.fields.get('__islocal')):
		tmp = webnotes.conn.sql('SELECT modified FROM `tab%s` WHERE name="%s" for update' % (doc.doctype, doc.name))
		if tmp and str(tmp[0][0]) != str(doc.modified):
			webnotes.msgprint('Document has been modified after you have opened it. To maintain the integrity of the data, you will not be able to save your changes. Please refresh this document. [%s/%s]' % (tmp[0][0], doc.modified))
			return 0
			
	return 1

#===========================================================================================

def savedocs():
	import webnotes.model.doclist

	from webnotes.model.code import get_server_obj
	from webnotes.model.code import run_server_obj
	import webnotes.utils
	from webnotes.widgets.auto_master import update_auto_masters

	from webnotes.utils import cint

	sql = webnotes.conn.sql
	form = webnotes.form

	# action
	action = form.get('action')
	
	# get docs	
	doc, doclist = _get_doclist(webnotes.model.doclist.expand(form.get('docs')))

	# get server object	
	server_obj = get_server_obj(doc, doclist)

	# check integrity
	if not check_integrity(doc):
		return
	
	if not doc.check_perm(verbose=1):
		webnotes.msgprint("Not enough permission to save %s" % doc.doctype)
		return
	
	# validate links
	ret = webnotes.model.doclist.validate_links_doclist([doc] + doclist)
	if ret:
		webnotes.msgprint("[Link Validation] Could not find the following values: %s. Please correct and resave. Document Not Saved." % ret)
		return

	# saving & post-saving
	try:
		# validate befor saving and submitting
		if action in ('Save', 'Submit') and server_obj:
			if hasattr(server_obj, 'validate'):	
				t = run_server_obj(server_obj, 'validate')
			if hasattr(server_obj, 'custom_validate'):
				t = run_server_obj(server_obj, 'custom_validate')
				
		# set owner and modified times
		is_new = cint(doc.fields.get('__islocal'))
		if is_new and not doc.owner:
			doc.owner = form.get('user')
		
		doc.modified, doc.modified_by = webnotes.utils.now(), webnotes.session['user']
		
		# save main doc
		try:
			t = doc.save(is_new)
			update_auto_masters(doc)
		except NameError, e:
			webnotes.msgprint('%s "%s" already exists' % (doc.doctype, doc.name))
			if webnotes.conn.sql("select docstatus from `tab%s` where name=%s" % (doc.doctype, '%s'), doc.name)[0][0]==2:
				webnotes.msgprint('[%s "%s" has been cancelled]' % (doc.doctype, doc.name))
			webnotes.errprint(webnotes.utils.getTraceback())
			raise e
		
		# save child docs
		for d in doclist:
			deleted, local = d.fields.get('__deleted',0), d.fields.get('__islocal',0)
	
			if cint(local) and cint(deleted):
				pass
			elif d.fields.has_key('parent'):
				if d.parent and (not d.parent.startswith('old_parent:')):
					d.parent = doc.name # rename if reqd
					d.parenttype = doc.doctype
				d.modified, d.modified_by = webnotes.utils.now(), webnotes.session['user']
				d.save(new = cint(local))
				update_auto_masters(d)
	
		# on_update
		if action in ('Save','Submit') and server_obj:
			if hasattr(server_obj, 'on_update'):
				t = run_server_obj(server_obj, 'on_update')
				if t: webnotes.msgprint(t)
	
			if hasattr(server_obj, 'custom_on_update'):
				t = run_server_obj(server_obj, 'custom_on_update')
				if t: webnotes.msgprint(t)

			fire_event(doc, 'on_update')
				
		# on_submit
		if action == 'Submit':
			_do_action(doc, doclist, server_obj, 'on_submit', 1)

		# for allow_on_submit type
		if action == 'Update':
			_do_action(doc, doclist, server_obj, 'on_update_after_submit', 0)
				
		# on_cancel
		if action == 'Cancel':
			_do_action(doc, doclist, server_obj, 'on_cancel', 2)

		# update recent documents
		webnotes.user.update_recent(doc.doctype, doc.name)

		# send updated docs
		webnotes.response['saved'] = '1'
		webnotes.response['main_doc_name'] = doc.name
		webnotes.response['docname'] = doc.name
		webnotes.response['docs'] = [doc] + doclist

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

	html = webnotes.model.meta.get_print_format_html(webnotes.form.get('name'))

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
	
	fid = webnotes.form.get('fid')
	webnotes.utils.file_manager.delete_file(fid, verbose=1)

# Get Fields - Counterpart to $c_get_fields
#===========================================================================================
def get_fields():
	import webnotes
	r = {}
	args = {
		'select':webnotes.form.get('select')
		,'from':webnotes.form.get('from')
		,'where':webnotes.form.get('where')
	}
	ret = webnotes.conn.sql("select %(select)s from `%(from)s` where %(where)s limit 1" % args)
	if ret:
		fl, i = webnotes.form.get('fields').split(','), 0
		for f in fl:
			r[f], i = ret[0][i], i+1
	webnotes.response['message']=r

# validate link
#===========================================================================================
def validate_link():
	import webnotes
	import webnotes.utils
	
	value, options, fetch = webnotes.form.get('value'), webnotes.form.get('options'), webnotes.form.get('fetch')

	# no options, don't validate
	if not options or options=='null' or options=='undefined':
		webnotes.response['message'] = 'Ok'
		return
		
	if webnotes.conn.sql("select name from `tab%s` where name=%s" % (options, '%s'), value):
	
		# get fetch values
		if fetch:
			webnotes.response['fetch_values'] = [webnotes.utils.parse_val(c) for c in webnotes.conn.sql("select %s from `tab%s` where name=%s" % (fetch, options, '%s'), value)[0]]
	
		webnotes.response['message'] = 'Ok'
