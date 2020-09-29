import frappe

def execute():
	fix_communications()
	fix_show_as_cc_email_queue()
	fix_email_queue_recipients()

def fix_communications():
	for communication in frappe.db.sql('''select name, recipients, cc, bcc from tabCommunication
		where creation > '2020-06-01'
			and communication_medium='Email'
			and communication_type='Communication'
			and (cc like  '%&lt;%' or bcc like '%&lt;%' or recipients like '%&lt;%')
		''', as_dict=1):

		communication['recipients'] = format_email_id(communication.recipients)
		communication['cc'] = format_email_id(communication.cc)
		communication['bcc'] = format_email_id(communication.bcc)

		frappe.db.sql('''update `tabCommunication` set recipients=%s,cc=%s,bcc=%s
			where name =%s ''', (communication['recipients'], communication['cc'],
			communication['bcc'], communication['name']))

def fix_show_as_cc_email_queue():
	for queue in frappe.get_all("Email Queue", {'creation': ['>', '2020-06-01'],
		'status': 'Not Sent', 'show_as_cc': ['like', '%&lt;%']},
		['name', 'show_as_cc']):

		frappe.db.set_value('Email Queue', queue['name'],
			'show_as_cc', format_email_id(queue['show_as_cc']))

def fix_email_queue_recipients():
	for recipient in frappe.db.sql('''select recipient, name from
		`tabEmail Queue Recipient` where recipient like '%&lt;%'
			and status='Not Sent' and creation > '2020-06-01' ''', as_dict=1):

		frappe.db.set_value('Email Queue Recipient', recipient['name'],
			'recipient', format_email_id(recipient['recipient']))

def format_email_id(email):
	if email and ('&lt;' in email and '&gt;' in email):
		return email.replace('&gt;', '>').replace('&lt;', '<')

	return email
