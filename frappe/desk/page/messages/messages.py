# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.notifications import delete_notification_count_for
from frappe.core.doctype.user.user import STANDARD_USERS
from frappe.utils.user import get_enabled_system_users
from frappe.utils import cint, get_fullname

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
	""", frappe.session.user)

	delete_notification_count_for("Messages")

	frappe.db.commit()

	if frappe.form_dict['contact'] == frappe.session['user']:
		# return messages
		return frappe.db.sql("""select * from `tabComment`
		where (owner=%(contact)s
			or comment_docname=%(user)s
			or owner=comment_docname)
		and comment_doctype ='Message'
		and ifnull(parenttype, "")!="Assignment"
		order by creation desc
		limit %(limit_start)s, %(limit_page_length)s""", frappe.local.form_dict, as_dict=1)
	else:
		return frappe.db.sql("""select * from `tabComment`
		where ((owner=%(contact)s and comment_docname=%(user)s)
		or (owner=%(user)s and comment_docname=%(contact)s)
		or (owner=%(contact)s and comment_docname=%(contact)s))
		and comment_doctype ='Message'
		and ifnull(parenttype, "")!="Assignment"
		order by creation desc
		limit %(limit_start)s, %(limit_page_length)s""", frappe.local.form_dict, as_dict=1)


@frappe.whitelist()
def get_active_users():
	data = frappe.db.sql("""select name,
		(select count(*) from tabSessions where user=tabUser.name
			and timediff(now(), lastupdate) < time("01:00:00")) as has_session
	 	from tabUser
		where enabled=1 and
		ifnull(user_type, '')!='Website User' and
		name not in ({})
		order by first_name""".format(", ".join(["%s"]*len(STANDARD_USERS))), STANDARD_USERS, as_dict=1)

	# make sure current user is at the top, using has_session = 100
	users = [d.name for d in data]

	if frappe.session.user in users:
		data[users.index(frappe.session.user)]["has_session"] = 100

	else:
		# in case of administrator
		data.append({"name": frappe.session.user, "has_session": 100})

	return data

@frappe.whitelist()
def post(txt, contact, parenttype=None, notify=False, subject=None):
	import frappe
	"""post message"""

	d = frappe.new_doc('Comment')
	d.parenttype = parenttype
	d.comment = txt
	d.comment_docname = contact
	d.comment_doctype = 'Message'
	d.comment_by_fullname = get_fullname(frappe.session.user)
	d.insert(ignore_permissions=True)

	delete_notification_count_for("Messages")

	if notify and cint(notify):
		if contact==frappe.session.user:
			_notify([user.name for user in get_enabled_system_users()], txt)
		else:
			_notify(contact, txt, subject)

	return d

@frappe.whitelist()
def delete(arg=None):
	frappe.get_doc("Comment", frappe.form_dict['name']).delete()

def _notify(contact, txt, subject=None):
	from frappe.utils import get_fullname, get_url

	try:
		if not isinstance(contact, list):
			contact = [frappe.db.get_value("User", contact, "email") or contact]
		frappe.sendmail(\
			recipients=contact,
			sender= frappe.db.get_value("User", frappe.session.user, "email"),
			subject=subject or "New Message from " + get_fullname(frappe.session.user),
			message=frappe.get_template("templates/emails/new_message.html").render({
				"from": get_fullname(frappe.session.user),
				"message": txt,
				"link": get_url()
			}),
			bulk=True)
	except frappe.OutgoingEmailError:
		pass
