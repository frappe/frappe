# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

from __future__ import unicode_literals
import webnotes

def sendmail_md(recipients, sender=None, msg=None, subject=None):
	"""send markdown email"""
	import markdown2
	sendmail(recipients, sender, markdown2.markdown(msg), subject)
			
def sendmail(recipients, sender='', msg='', subject='[No Subject]'):
	"""send an html email as multipart with attachments and all"""
	from webnotes.utils.email_lib.smtp import get_email
	get_email(recipients, sender, msg, subject).send()

@webnotes.whitelist()
def send_form():
	"""Emails a print format (form). Called from form UI"""
	from webnotes.utils.email_lib.form_email import FormEmail
	FormEmail().send()

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
