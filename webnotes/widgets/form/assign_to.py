# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
"""assign/unassign to ToDo"""

import webnotes

@webnotes.whitelist()
def get(args=None):
	"""get assigned to"""
	if not args:
		args = webnotes.local.form_dict
	return webnotes.conn.sql_list("""select owner from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		order by modified desc limit 5""", args)
		
@webnotes.whitelist()
def add(args=None):
	"""add in someone's to do list"""
	if not args:
		args = webnotes.local.form_dict
		
	if webnotes.conn.sql("""select owner from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		and owner=%(assign_to)s""", args):
		webnotes.msgprint("Already in todo", raise_exception=True)
		return
	else:
		from webnotes.model.doc import Document
		from webnotes.utils import nowdate
		
		d = Document("ToDo")
		d.owner = args['assign_to']
		d.reference_type = args['doctype']
		d.reference_name = args['name']
		d.description = args.get('description')
		d.priority = args.get('priority', 'Medium')
		d.date = args.get('date', nowdate())
		d.assigned_by = args.get('assigned_by', webnotes.user.name)
		d.save(1)
		
		# set assigned_to if field exists
		from webnotes.model.meta import has_field
		if has_field(args['doctype'], "assigned_to"):
			webnotes.conn.set_value(args['doctype'], args['name'], "assigned_to", args['assign_to'])

	# notify
	if not args.get("no_notification"):
		notify_assignment(d.assigned_by, d.owner, d.reference_type, d.reference_name, action='ASSIGN', description=args.get("description"), notify=args.get('notify'))
		
	# update feeed
	try:
		from erpnext.home import make_feed
		from webnotes.utils import get_fullname
		make_feed('Assignment', d.reference_type, d.reference_name, webnotes.session['user'],
			'[%s] Assigned to %s' % (d.priority, get_fullname(d.owner)), '#C78F58')
	except ImportError, e:
		pass
	
	return get(args)

@webnotes.whitelist()
def remove(doctype, name, assign_to):
	"""remove from todo"""
	res = webnotes.conn.sql("""\
		select assigned_by, owner, reference_type, reference_name from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		and owner=%(assign_to)s""", locals())

	webnotes.conn.sql("""delete from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s
		and owner=%(assign_to)s""", locals())
		
	# clear assigned_to if field exists
	from webnotes.model.meta import has_field
	if has_field(doctype, "assigned_to"):
		webnotes.conn.set_value(doctype, name, "assigned_to", None)

	if res and res[0]: notify_assignment(res[0][0], res[0][1], res[0][2], res[0][3])

	return get({"doctype": doctype, "name": name})
	
def clear(doctype, name):
	for assign_to in webnotes.conn.sql_list("""select owner from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s""", locals()):
			remove(doctype, name, assign_to)

def notify_assignment(assigned_by, owner, doc_type, doc_name, action='CLOSE', 
	description=None, notify=0):
	"""
		Notify assignee that there is a change in assignment
	"""	
	if not (assigned_by and owner and doc_type and doc_name): return

	# self assignment / closing - no message
	if assigned_by==owner:
		return

	from webnotes.boot import get_fullnames
	user_info = get_fullnames()

	# Search for email address in description -- i.e. assignee
	from webnotes.utils import get_url_to_form
	assignment = get_url_to_form(doc_type, doc_name, label="%s: %s" % (doc_type, doc_name))
		
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
			'txt': "A new task, %s, has been assigned to you by %s. %s" \
				% (assignment,
				user_info.get(webnotes.session.get('user'), {}).get('fullname'),
				description and ("<p>Description: " + description + "</p>") or ""),
			'notify': notify
		}
		
	arg["parenttype"] = "Assignment"
	from webnotes.core.page.messages import messages
	import json
	messages.post(json.dumps(arg))
