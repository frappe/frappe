# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""assign/unassign to ToDo"""

import frappe
from frappe import _
from frappe.utils import cint
from frappe.widgets.form.load import get_docinfo

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
		frappe.msgprint(_("Already in user's To Do list"), raise_exception=True)
		return
	else:
		from frappe.utils import nowdate

		d = frappe.get_doc({
			"doctype":"ToDo",
			"owner": args['assign_to'],
			"reference_type": args['doctype'],
			"reference_name": args['name'],
			"description": args.get('description'),
			"priority": args.get("priority", "Medium"),
			"status": "Open",
			"date": args.get('date', nowdate()),
			"assigned_by": args.get('assigned_by', frappe.user.name),
		}).insert(ignore_permissions=True)

		# set assigned_to if field exists
		if frappe.get_meta(args['doctype']).get_field("assigned_to"):
			frappe.db.set_value(args['doctype'], args['name'], "assigned_to", args['assign_to'])

	# notify
	if not args.get("no_notification"):
		notify_assignment(d.assigned_by, d.owner, d.reference_type, d.reference_name, action='ASSIGN', description=args.get("description"), notify=args.get('notify'))

	return get(args)

@frappe.whitelist()
def remove(doctype, name, assign_to):
	"""remove from todo"""
	try:
		todo = frappe.get_doc("ToDo", {"reference_type":doctype, "reference_name":name, "owner":assign_to, "status":"Open"})
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
	from frappe.utils import get_url_to_form
	assignment = get_url_to_form(doc_type, doc_name, label="%s: %s" % (doc_type, doc_name))

	if action=='CLOSE':
		if owner == frappe.session.get('user'):
			arg = {
				'contact': assigned_by,
				'txt': _("The task %s, that you assigned to %s, has been closed.") % (assignment,
						user_info.get(owner, {}).get('fullname'))
			}
		else:
			arg = {
				'contact': assigned_by,
				'txt': _("The task %s, that you assigned to %s, has been closed by %s.") % (assignment,
					user_info.get(owner, {}).get('fullname'),
					user_info.get(frappe.session.get('user'),
						{}).get('fullname'))
			}
	else:
		arg = {
			'contact': owner,
			'txt': _("A new task, %s, has been assigned to you by %s. %s") % (assignment,
				user_info.get(frappe.session.get('user'), {}).get('fullname'),
				description and ("<p>" + _("Description") + ": " + description + "</p>") or ""),
			'notify': notify
		}

	arg["parenttype"] = "Assignment"
	from frappe.core.page.messages import messages
	messages.post(**arg)
