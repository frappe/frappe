# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.core.doctype.notification_count.notification_count import delete_notification_count_for
from frappe.core.doctype.user.user import STANDARD_USERS

@frappe.whitelist()
def get_list(arg=None):
	"""get list of messages"""
	frappe.form_dict['limit_start'] = int(frappe.form_dict['limit_start'])
	frappe.form_dict['limit_page_length'] = int(frappe.form_dict['limit_page_length'])
	frappe.form_dict['user'] = frappe.session['user']

	# set all messages as read
	frappe.db.begin()
	frappe.db.sql("""UPDATE `tabComment`
	set docstatus = 1 where comment_doctype in ('My Company', 'Message')
	and comment_docname = %s
	""", frappe.user.name)
	
	delete_notification_count_for("Messages")
	
	frappe.db.commit()

	if frappe.form_dict['contact'] == frappe.session['user']:
		# return messages
		return frappe.db.sql("""select * from `tabComment` 
		where (owner=%(contact)s 
			or comment_docname=%(user)s 
			or (owner=comment_docname and ifnull(parenttype, "")!="Assignment"))
		and comment_doctype ='Message'
		order by creation desc
		limit %(limit_start)s, %(limit_page_length)s""", frappe.local.form_dict, as_dict=1)		
	else:
		return frappe.db.sql("""select * from `tabComment` 
		where (owner=%(contact)s and comment_docname=%(user)s)
		or (owner=%(user)s and comment_docname=%(contact)s)
		or (owner=%(contact)s and comment_docname=%(contact)s)
		and comment_doctype ='Message'
		order by creation desc
		limit %(limit_start)s, %(limit_page_length)s""", frappe.local.form_dict, as_dict=1)
		

@frappe.whitelist()
def get_active_users():
	return frappe.db.sql("""select name,
		(select count(*) from tabSessions where user=tabUser.name
			and timediff(now(), lastupdate) < time("01:00:00")) as has_session
	 	from tabUser 
		where ifnull(enabled,0)=1 and
		ifnull(user_type, '')!='Website User' and 
		name not in ({})
		order by first_name""".format(", ".join(["%s"]*len(STANDARD_USERS))), STANDARD_USERS, as_dict=1)

@frappe.whitelist()
def post(arg=None):
	import frappe
	"""post message"""
	if not arg:
		arg = {}
		arg.update(frappe.local.form_dict)
	
	if isinstance(arg, basestring):
		import json
		arg = json.loads(arg)

	d = frappe.new_doc('Comment')
	d.parenttype = arg.get("parenttype")
	d.comment = arg['txt']
	d.comment_docname = arg['contact']
	d.comment_doctype = 'Message'
	d.insert(ignore_permissions=True)
	
	delete_notification_count_for("Messages")

	import frappe.utils
	if frappe.utils.cint(arg.get('notify')):
		notify(arg)
	
@frappe.whitelist()
def delete(arg=None):
	frappe.db.sql("""delete from `tabComment` where name=%s""", 
		frappe.form_dict['name']);

def notify(arg=None):
	from frappe.utils import cstr, get_fullname, get_url
	
	try:
		frappe.sendmail(\
			recipients=[frappe.db.get_value("User", arg["contact"], "email") or arg["contact"]],
			sender= frappe.db.get_value("User", frappe.session.user, "email"),
			subject="New Message from " + get_fullname(frappe.user.name),
			message=frappe.get_template("templates/emails/new_message.html").render({
				"from": get_fullname(frappe.user.name),
				"message": arg['txt'],
				"link": get_url()
			})
		)
	except frappe.OutgoingEmailError, e:
		pass