# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
"""assign/unassign to ToDo"""

import frappe
from frappe import _
from frappe.desk.form.document_follow import follow_document
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification,\
	get_title, get_title_html
import frappe.utils
import frappe.share

class DuplicateToDoError(frappe.ValidationError): pass

def get(args=None):
	"""get assigned to"""
	if not args:
		args = frappe.local.form_dict

	return frappe.get_all('ToDo', fields = ['owner', 'description'], filters = dict(
		reference_type = args.get('doctype'),
		reference_name = args.get('name'),
		status = ('!=', 'Cancelled')
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
			description=args.get("description"))

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

def close_all_assignments(doctype, name):
	assignments = frappe.db.get_all('ToDo', fields=['owner'], filters =
		dict(reference_type = doctype, reference_name = name, status=('!=', 'Cancelled')))
	if not assignments:
		return False

	for assign_to in assignments:
		set_status(doctype, name, assign_to.owner, status="Closed")

	return True

@frappe.whitelist()
def remove(doctype, name, assign_to):
	return set_status(doctype, name, assign_to, status="Cancelled")

def set_status(doctype, name, assign_to, status="Cancelled"):
	"""remove from todo"""
	try:
		todo = frappe.db.get_value("ToDo", {"reference_type":doctype,
		"reference_name":name, "owner":assign_to, "status": ('!=', status)})
		if todo:
			todo = frappe.get_doc("ToDo", todo)
			todo.status = status
			todo.save(ignore_permissions=True)

			notify_assignment(todo.assigned_by, todo.owner, todo.reference_type, todo.reference_name)
	except frappe.DoesNotExistError:
		pass

	# clear assigned_to if field exists
	if frappe.get_meta(doctype).get_field("assigned_to") and status=="Cancelled":
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
		set_status(doctype, name, assign_to.owner, "Cancelled")

	return True

def notify_assignment(assigned_by, owner, doc_type, doc_name, action='CLOSE',
	description=None):
	"""
		Notify assignee that there is a change in assignment
	"""
	if not (assigned_by and owner and doc_type and doc_name): return

	# self assignment / closing - no message
	if assigned_by==owner:
		return

	# Search for email address in description -- i.e. assignee
	user_name = frappe.get_cached_value('User', frappe.session.user, 'full_name')
	title = get_title(doc_type, doc_name)
	description_html =  "<div>{0}</div>".format(description) if description else None

	if action=='CLOSE':
		subject = _('Your assignment on {0} {1} has been removed').format(frappe.bold(doc_type), get_title_html(title))
	else:
		user_name = frappe.bold(user_name)
		document_type = frappe.bold(doc_type)
		title = get_title_html(title)
		subject = _('{0} assigned a new task {1} {2} to you').format(user_name, document_type, title)

	notification_doc = {
		'type': 'Assignment',
		'document_type': doc_type,
		'subject': subject,
		'document_name': doc_name,
		'from_user': frappe.session.user,
		'email_content': description_html
	}

	enqueue_create_notification(owner, notification_doc)

