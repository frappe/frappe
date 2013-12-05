# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals
import webnotes
from webnotes import conf

def sendmail_md(recipients, sender=None, msg=None, subject=None):
	"""send markdown email"""		
	import markdown2
	sendmail(recipients, sender, markdown2.markdown(msg), subject)
			
def sendmail(recipients, sender='', msg='', subject='[No Subject]'):
	"""send an html email as multipart with attachments and all"""
	from webnotes.utils.email_lib.smtp import get_email
	get_email(recipients, sender, msg, subject).send()

def sendmail_to_system_managers(subject, content):
	from webnotes.utils.email_lib.smtp import get_email
	get_email(get_system_managers(), None, content, subject).send()

@webnotes.whitelist()
def get_contact_list():
	"""Returns contacts (from autosuggest)"""
	cond = ['`%s` like "%s%%"' % (f, 
		webnotes.form_dict.get('txt')) for f in webnotes.form_dict.get('where').split(',')]
	cl = webnotes.conn.sql("select `%s` from `tab%s` where %s" % (
  			 webnotes.form_dict.get('select')
			,webnotes.form_dict.get('from')
			,' OR '.join(cond)
		)
	)
	webnotes.response['cl'] = filter(None, [c[0] for c in cl])

def get_system_managers():
	return webnotes.conn.sql_list("""select parent FROM tabUserRole 
				  WHERE role='System Manager' 
				  AND parent!='Administrator' 
				  AND parent IN 
						 (SELECT email FROM tabProfile WHERE enabled=1)""")