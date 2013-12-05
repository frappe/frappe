# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.model.doc import Document

@webnotes.whitelist()
def get(arg=None):
	"""get todo list"""
	return webnotes.conn.sql("""select name, owner, description, date,
		priority, checked, reference_type, reference_name, assigned_by
		from `tabToDo` where (owner=%s or assigned_by=%s)
		order by field(priority, 'High', 'Medium', 'Low') asc, date asc""",
		(webnotes.session['user'], webnotes.session['user']), as_dict=1)

@webnotes.whitelist()		
def edit(arg=None):
	import markdown2
	args = webnotes.local.form_dict

	if args.name:
		b = webnotes.bean("ToDo", args.name)
	else:
		b = webnotes.new_bean("ToDo")

	for key in ("description", "date", "priority", "checked"):
		b.doc.fields[key] = args.get(key)
				
	b.insert_or_update()
		
	if args.name and args.checked:
		notify_assignment(d)

	return b.doc.name

@webnotes.whitelist()
def delete(arg=None):
	name = webnotes.local.form_dict.name
	d = Document('ToDo', name)
	if d and d.name and d.owner != webnotes.session['user']:
		notify_assignment(d)
	webnotes.delete_doc("ToDo", d.name, ignore_permissions=True)

def notify_assignment(d):
	doc_type = d.reference_type
	doc_name = d.reference_name
	assigned_by = d.assigned_by
	
	if doc_type and doc_name and assigned_by:
		from webnotes.widgets.form import assign_to
		assign_to.notify_assignment(assigned_by, d.owner, doc_type, doc_name)
		