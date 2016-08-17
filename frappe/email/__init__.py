# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.email.email_body import get_email
from frappe.email.smtp import send
from frappe.utils import markdown

def set_customer_supplier(sender,recipients):
	origin_contact = frappe.db.sql("select name,email_id,supplier,supplier_name, customer,customer_name,user from `tabContact`",as_dict=1)

	for comm in origin_contact:
		if comm["user"] is None and comm["email_id"]:
			if (sender and sender.find(comm["email_id"]) > -1) or (
				recipients and recipients.find(comm["email_id"]) > -1):
				if comm["supplier"] and comm["customer"]:
					return {"timeline_doctype": "Contact","timeline_name":comm["name"],"timeline_label":None}

				elif comm["supplier"]:
					return {"timeline_doctype": "Supplier","timeline_name":comm["supplier"],"timeline_label":comm["supplier_name"]}

				elif comm["customer"]:
					return {"timeline_doctype": "Customer", "timeline_name": comm["customer"],"timeline_label": comm["customer_name"]}
	return {"timeline_doctype": None,"timeline_name":None,"timeline_label":None}

def sendmail_md(recipients, sender=None, msg=None, subject=None, attachments=None, content=None,
	reply_to=None, cc=(), message_id=None, in_reply_to=None):
	"""send markdown email"""
	sendmail(recipients, sender, markdown(content or msg), subject, attachments, reply_to=reply_to, cc=cc)

def sendmail(recipients, sender='', msg='', subject='[No Subject]', attachments=None, content=None,
	reply_to=None, cc=(), message_id=None, in_reply_to=None):
	"""send an html email as multipart with attachments and all"""
	mail = get_email(recipients, sender, content or msg, subject, attachments=attachments, reply_to=reply_to, cc=cc)
	mail.set_message_id(message_id)
	if in_reply_to:
		mail.set_in_reply_to(in_reply_to)

	send(mail)

def sendmail_to_system_managers(subject, content):
	send(get_email(get_system_managers(), None, content, subject))

@frappe.whitelist()
def get_contact_list(doctype, fieldname, txt):
	"""Returns contacts (from autosuggest)"""
	txt = txt.replace('%', '')

	try:
		return filter(None, frappe.db.sql_list('select `{0}` from `tab{1}` where `{0}` like %s'.format(fieldname, doctype),
			'%' + txt + '%'))
	except Exception, e:
		if e.args[0]==1146:
			# no Contact, use User
			return filter(None, frappe.db.sql_list('select email from tabUser where email like %s', ('%' + txt + '%')))
		else:
			raise

def get_system_managers():
	return frappe.db.sql_list("""select parent FROM tabUserRole
		WHERE role='System Manager'
		AND parent!='Administrator'
		AND parent IN (SELECT email FROM tabUser WHERE enabled=1)""")

@frappe.whitelist(allow_guest=False)
def get_email_awaiting(user):
	waiting = frappe.db.sql("""select email_account,email_id
		from `tabUser Emails`
		where awaiting_password = 1
		and parent = %(user)s""",{"user":user},as_dict=1)
	if waiting:
		return waiting
	else:
		frappe.db.sql("""update `tabUser Emails`
	    		set awaiting_password =0
	    		where parent = %(user)s""",{"user":user})
		return False
	#return frappe.get_all("User Emails",filters={"awaiting_password": 1,"parent":user})

@frappe.whitelist(allow_guest=False)
def set_email_password(email_account,user,password):
	account = frappe.get_doc("Email Account",
				email_account)
	if account.awaiting_password:
		account.set("awaiting_password",0)
		account.set("password",password)
		try:
			validate = account.validate()
			save= account.save(ignore_permissions=True)
			frappe.db.sql("""update `tabUser Emails` set awaiting_password = 0
				where email_account = %(account)s""",{"account": email_account})
			ask_pass_update()
		except Exception, e:
			frappe.db.rollback()
			return False
	return True

def ask_pass_update():
	# update the sys defaults as to awaiting users
	from frappe.utils import set_default
	users = frappe.db.sql("""select DISTINCT(parent)
    				from `tabUser Emails`
    				where awaiting_password = 1""", as_list=1)

	password_list = []
	for u in users:
		password_list.append(u[0])
	set_default("email_user_password", u','.join(password_list))


