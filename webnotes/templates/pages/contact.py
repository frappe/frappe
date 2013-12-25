# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import webnotes
from webnotes.utils import now

def get_context():
	bean = webnotes.bean("Contact Us Settings", "Contact Us Settings")
	
	query_options = filter(None, bean.doc.query_options.replace(",", "\n").split()) if \
			bean.doc.query_options else ["Sales", "Support", "General"]
	
	address = webnotes.bean("Address", bean.doc.address).doc if bean.doc.address else None
	
	return {
		"query_options": query_options,
		"address": address,
		"heading": bean.doc.heading,
		"introduction": bean.doc.introduction
	}


max_communications_per_hour = 300

@webnotes.whitelist(allow_guest=True)
def send_message(subject="Website Query", message="", sender=""):
	if not message:
		webnotes.response["message"] = 'Please write something'
		return
		
	if not sender:
		webnotes.response["message"] = 'Email Id Required'
		return
		
	# guest method, cap max writes per hour
	if webnotes.conn.sql("""select count(*) from `tabCommunication`
		where TIMEDIFF(%s, modified) < '01:00:00'""", now())[0][0] > max_communications_per_hour:
		webnotes.response["message"] = "Sorry: we believe we have received an unreasonably high number of requests of this kind. Please try later"
		return
	
	# send email
	forward_to_email = webnotes.conn.get_value("Contact Us Settings", None, "forward_to_email")
	if forward_to_email:
		from webnotes.utils.email_lib import sendmail
		sendmail(forward_to_email, sender, message, subject)
	
	webnotes.response.status = "okay"
	
	return True