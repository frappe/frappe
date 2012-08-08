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

from __future__ import unicode_literals
"""assign/unassign to ToDo"""

import webnotes

@webnotes.whitelist()
def get(args=None):
	"""get assigned to"""
	if not args:
		args = webnotes.form_dict
	return webnotes.conn.sql("""select owner from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		order by modified desc limit 5""", args, as_dict=1)
		
@webnotes.whitelist()
def add(args=None):
	"""add in someone's to do list"""
	if not args:
		args = webnotes.form_dict
	
	if webnotes.conn.sql("""select owner from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		and owner=%(assign_to)s""", args):
		webnotes.msgprint("Already in todo")
		return
	else:
		from webnotes.model.doc import Document
		from webnotes.utils import nowdate
		
		d = Document("ToDo")
		d.owner = args['assign_to']
		d.reference_type = args['doctype']
		d.reference_name = args['name']
		d.description = args['description']
		d.priority = args.get('priority', 'Medium')
		d.date = args.get('date', nowdate())
		d.assigned_by = args.get('assigned_by', webnotes.user.name)
		d.save(1)

	# notify
	notify_assignment(d.assigned_by, d.owner, d.reference_type, d.reference_name, action='ASSIGN', notify=args.get('notify'))
		
	# update feeed
	try:
		import home
		from webnotes.utils import get_fullname
		home.make_feed('Assignment', d.reference_type, d.reference_name, webnotes.session['user'],
			'[%s] Assigned to %s' % (d.priority, get_fullname(d.owner)), '#C78F58')
	except ImportError, e:
		pass
	
	
	return get(args)

@webnotes.whitelist()
def remove(args=None):
	"""remove from todo"""
	if not args:
		args = webnotes.form_dict
	
	res = webnotes.conn.sql("""\
		select assigned_by, owner, reference_type, reference_name from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		and owner=%(assign_to)s""", args)

	webnotes.conn.sql("""delete from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		and owner=%(assign_to)s""", args)

	if res and res[0]: notify_assignment(res[0][0], res[0][1], res[0][2], res[0][3])

	return get(args)


def notify_assignment(assigned_by, owner, doc_type, doc_name, action='CLOSE', notify=0):
	"""
		Notify assignee that there is a change in assignment
	"""
	if not (assigned_by and owner and doc_type and doc_name): return

	from webnotes.boot import get_fullnames
	user_info = get_fullnames()

	# Search for email address in description -- i.e. assignee
	assignment = """<a href="#!Form/%s/%s">%s: %s</a>""" % (doc_type, doc_name,
			doc_type, doc_name)
	if action=='CLOSE':
		if owner == webnotes.session.get('user'):
			arg = {
				'contact': assigned_by,
				'txt': "The task %s, that you assigned to %s, has been \
					closed." % (assignment,
						user_info.get(owner, {}).get('fullname'))
			}
		else:
			arg = {
				'contact': assigned_by,
				'txt': "The task %s, that you assigned to %s, \
					has been closed	by %s." % (assignment,
					user_info.get(owner, {}).get('fullname'),
					user_info.get(webnotes.session.get('user'),
						{}).get('fullname'))
			}
	else:
		arg = {
			'contact': owner,
			'txt': "A new task, %s, has been assigned to you by %s." \
				% (assignment,
				user_info.get(webnotes.session.get('user'), {}).get('fullname')),
			'notify': notify
		}
	from utilities.page.messages import messages
	import json
	messages.post(json.dumps(arg))
