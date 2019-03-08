# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""assign/unassign to ToDo"""

import frappe
from frappe import _
from frappe.desk.form.document_follow import follow_document
import frappe.share

class DuplicateToDoError(frappe.ValidationError): pass

def get(args=None):
	"""get assigned to"""
	if not args:
		args = frappe.local.form_dict

	return frappe.get_all('ToDo', fields = ['owner', 'description'], filters = dict(
		reference_type = args.get('doctype'),
		reference_name = args.get('name'),
		status = 'Open'
	), limit = 5)

@frappe.whitelist()
def add(args=None):
	"""add in someone's to do list
		args = {
			"assign_to": ,
			"doctype": ,
			"name": ,
			"description": ,
			"assignment_rule":
		}

	"""
	if not args:
		args = frappe.local.form_dict

	if frappe.db.sql("""SELECT `owner`
		FROM `tabToDo`
		WHERE `reference_type`=%(doctype)s
		AND `reference_name`=%(name)s
		AND `status`='Open'
		AND `owner`=%(assign_to)s""", args):
		frappe.throw(_("Already in user's To Do list"), DuplicateToDoError)
	else:
		from frappe.utils import nowdate

		# if args.get("re_assign"):
		# 	remove_from_todo_if_already_assigned(args['doctype'], args['name'])

		if not args.get('description'):
			args['description'] = _('Assignment for {0} {1}'.format(args['doctype'], args['name']))

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
			'assignment_rule': args.get('assignment_rule')
		}).insert(ignore_permissions=True)

		# set assigned_to if field exists
		if frappe.get_meta(args['doctype']).get_field("assigned_to"):
			frappe.db.set_value(args['doctype'], args['name'], "assigned_to", args['assign_to'])

		doc = frappe.get_doc(args['doctype'], args['name'])

		# if assignee does not have permissions, share
		if not frappe.has_permission(doc=doc, user=args['assign_to']):
			frappe.share.add(doc.doctype, doc.name, args['assign_to'])
			frappe.msgprint(_('Shared with user {0} with read access').format(args['assign_to']), alert=True)

		# make this document followed by assigned user
		follow_document(args['doctype'], args['name'], args['assign_to'])

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
	owner = frappe.db.get_value("ToDo", {"reference_type": doctype, "reference_name": docname,
		"status":"Open"}, "owner")
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
	'''
	Clears assignments, return False if not assigned.
	'''
	assignments = frappe.db.get_all('ToDo', fields=['owner'], filters =
		dict(reference_type = doctype, reference_name = name))
	if not assignments:
		return False

	for assign_to in assignments:
		remove(doctype, name, assign_to.owner)

	return True

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

	if arg and arg.get("notify"):
		_notify(arg)

def _notify(args):
	from frappe.utils import get_fullname, get_url

	args = frappe._dict(args)
	contact = args.contact
	txt = args.txt

	try:
		if not isinstance(contact, list):
			contact = [frappe.db.get_value("User", contact, "email") or contact]

		frappe.sendmail(\
			recipients=contact,
			sender= frappe.db.get_value("User", frappe.session.user, "email"),
			subject=_("New message from {0}").format(get_fullname(frappe.session.user)),
			template="new_message",
			args={
				"from": get_fullname(frappe.session.user),
				"message": txt,
				"link": get_url()
			},
			header=[_('New Message'), 'orange'])
	except frappe.OutgoingEmailError:
		pass
