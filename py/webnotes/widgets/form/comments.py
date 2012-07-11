# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

import webnotes

@webnotes.whitelist()
def get_comments(doctype=None, docname=None, limit=5):
	"""load last 5 comments"""
	nc, cl = 0, []

	if not doctype:
		doctype, docname, limit = webnotes.form_dict.get('dt'), webnotes.form_dict.get('dn'), \
			webnotes.form_dict.get('limit')
		
	nc = int(webnotes.conn.sql("""select count(*) from `tabComment` 
		where comment_doctype=%s and comment_docname=%s""", (doctype, docname))[0][0])
	if nc:
		cl = webnotes.conn.sql("""select comment, ifnull(comment_by_fullname, comment_by) 
			AS 'comment_by_fullname', creation from `tabComment` 
			where comment_doctype=%s and comment_docname=%s 
			order by creation desc limit %s""" % ('%s','%s',limit), (doctype, docname), as_dict=1)

		webnotes.response['n_comments'], webnotes.response['comment_list'] = nc, cl

@webnotes.whitelist(allow_guest=True)
def add_comment(args=None):
	"""add a new comment"""
	import time
	if not args: args = webnotes.form_dict

	if args.get('comment'):
		from webnotes.model.doc import Document
		from webnotes.utils import nowdate
		
		cmt = Document('Comment')
		for arg in ['comment', 'comment_by', 'comment_by_fullname', 'comment_doctype', \
			'comment_docname']:
			cmt.fields[arg] = args[arg]
		cmt.save(1)

	import startup.event_handlers
	if hasattr(startup.event_handlers, 'comment_added'):
		startup.event_handlers.comment_added(cmt)
	
	return cmt.fields

@webnotes.whitelist()
def remove_comment():
	"""remove a comment"""
	args = webnotes.form_dict
	webnotes.conn.sql("delete from `tabComment` where name=%s",args.get('id'))
