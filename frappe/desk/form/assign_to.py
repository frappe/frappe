# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""assign/unassign to ToDo"""

import frappe
from frappe import _
from frappe.desk.form.load import get_docinfo

class DuplicateToDoError(frappe.ValidationError): pass

def get(args=None):
	"""get assigned to"""
	if not args:
		args = frappe.local.form_dict

	get_docinfo(frappe.get_doc(args.get("doctype"), args.get("name")))

	return frappe.db.sql("""select owner, description from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s and status="Open"
		order by modified desc limit 5""", args, as_dict=True)

@frappe.whitelist()
def add(args=None):
	"""add in someone's to do list
		args = {
			"assign_to": ,
			"doctype": ,
			"name": ,
			"description":
		}

	"""
	if not args:
		args = frappe.local.form_dict

	if frappe.db.sql("""select owner from `tabToDo`
		where reference_type=%(doctype)s and reference_name=%(name)s and status="Open"
		and owner=%(assign_to)s""", args):
		frappe.throw(_("Already in user's To Do list"), DuplicateToDoError)

	else:
		from frappe.utils import nowdate

		# if args.get("re_assign"):
		# 	remove_from_todo_if_already_assigned(args['doctype'], args['name'])

		d = frappe.get_doc({
			"doctype":"ToDo",
			"owner": args['assign_to'],
			"reference_type": args['doctype'],
			"reference_name": args['name'],
			"description": args.get('description'),
			"priority": args.get("priority", "Medium"),
			"status": "Open",
			"date": args.get('date', nowdate()),
			"assigned_by": args.get('assigned_by', frappe.session.user),
		}).insert(ignore_permissions=True)

		# set assigned_to if field exists
		if frappe.get_meta(args['doctype']).get_field("assigned_to"):
			frappe.db.set_value(args['doctype'], args['name'], "assigned_to", args['assign_to'])

	# notify
	notify_assignment(d.assigned_by, d.owner, d.reference_type, d.reference_name, action='ASSIGN',\
			 description=args.get("description"), notify=args.get('notify'))

	return get(args)

@frappe.whitelist()
def add_multiple(args=None):
	import json

	if not args:
		args = frappe.local.form_dict

	docname_list = json.loads(args['name'])

	for docname in docname_list:
		args.update({"name": docname})
		add(args)

def remove_from_todo_if_already_assigned(doctype, docname):
	owner = frappe.db.get_value("ToDo", {"reference_type": doctype, "reference_name": docname, "status":"Open"}, "owner")
	if owner:
		remove(doctype, docname, owner)

@frappe.whitelist()
def remove(doctype, name, assign_to):
	"""remove from todo"""
	try:
		todo = frappe.db.get_value("ToDo", {"reference_type":doctype, "reference_name":name, "owner":assign_to, "status":"Open"})
		if todo:
			todo = frappe.get_doc("ToDo", todo)
			todo.status = "Closed"
			todo.save(ignore_permissions=True)

			notify_assignment(todo.assigned_by, todo.owner, todo.reference_type, todo.reference_name)
	except frappe.DoesNotExistError:
		pass

	# clear assigned_to if field exists
	if frappe.get_meta(doctype).get_field("assigned_to"):
		frappe.db.set_value(doctype, name, "assigned_to", None)

	return get({"doctype": doctype, "name": name})

def clear(doctype, name):
	for assign_to in frappe.db.sql_list("""select owner from `tabToDo`
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

	from frappe.boot import get_fullnames
	user_info = get_fullnames()

	# Search for email address in description -- i.e. assignee
	from frappe.utils import get_link_to_form
	assignment = get_link_to_form(doc_type, doc_name, label="%s: %s" % (doc_type, doc_name))
	owner_name = user_info.get(owner, {}).get('fullname')
	user_name = user_info.get(frappe.session.get('user'), {}).get('fullname')
	if action=='CLOSE':
		if owner == frappe.session.get('user'):
			arg = {
				'contact': assigned_by,
				'txt': _("The task {0}, that you assigned to {1}, has been closed.").format(assignment,
						owner_name)
			}
		else:
			arg = {
				'contact': assigned_by,
				'txt': _("The task {0}, that you assigned to {1}, has been closed by {2}.").format(assignment,
					owner_name, user_name)
			}
	else:
		description_html = "<p>{0}</p>".format(description)
		arg = {
			'contact': owner,
			'txt': _("A new task, {0}, has been assigned to you by {1}. {2}").format(assignment,
				user_name, description_html),
			'notify': notify
		}

	arg["parenttype"] = "Assignment"

	from frappe.desk.page.chat import chat
	chat.post(**arg)
