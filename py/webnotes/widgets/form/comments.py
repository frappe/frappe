import webnotes

def get_comments(doctype=None, docname=None, limit=5):
	"""load last 5 comments"""
	nc, cl = 0, []

	if not doctype:
		doctype, docname, limit = webnotes.form_dict.get('dt'), webnotes.form_dict.get('dn'), \
			webnotes.form_dict.get('limit')
		
	nc = int(webnotes.conn.sql("""select count(*) from `tabComment Widget Record` 
		where comment_doctype=%s and comment_docname=%s""", (doctype, docname))[0][0])
	if nc:
		cl = webnotes.conn.sql("""select comment, ifnull(comment_by_fullname, comment_by) 
			AS 'comment_by_fullname', creation from `tabComment Widget Record` 
			where comment_doctype=%s and comment_docname=%s 
			order by creation desc limit %s""" % ('%s','%s',limit), (doctype, docname), as_dict=1)

		webnotes.response['n_comments'], webnotes.response['comment_list'] = nc, cl

	
def add_comment():
	"""add a new comment"""
	import time
	args = webnotes.form_dict

	if args.get('comment'):
		from webnotes.model.doc import Document
		from webnotes.utils import nowdate
		
		cmt = Document('Comment Widget Record')
		for arg in ['comment', 'comment_by', 'comment_by_fullname', 'comment_doctype', \
			'comment_docname']:
			cmt.fields[arg] = args[arg]
		cmt.save(1)

	import startup.event_handlers
	if hasattr(startup.event_handlers, 'comment_added'):
		startup.event_handlers.comment_added(cmt)
  			
def remove_comment():
	"""remove a comment"""
	args = webnotes.form_dict
	webnotes.conn.sql("delete from `tabComment Widget Record` where name=%s",args.get('id'))
