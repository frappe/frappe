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

def sendmail_html(sender, recipients, subject, html, text=None, template=None, send_now=1, reply_to=None):
	"""
		Send an html mail with alternative text and using Page Templates
	"""
	sendmail(recipients, sender, html, subject, 
		send_now = send_now, reply_to = reply_to, template = template)

def make_html_body(content, template = None):
	"""
		Generate html content from a Page Template object
	"""
	template_html = '<div class="margin: 12px">%(content)s</div>'

	if template:
		from webnotes.model.code import get_code
		template_html = get_code(webnotes.conn.get_value('Page Template', template, 'module'), 'Page Template', template, 'html', fieldname='template')

	return template_html % {'content': content}

def sendmail_md(recipients, sender=None, msg=None, subject=None, from_defs=0):
	"""send markdown email"""
	import markdown2
	sendmail(recipients, sender, markdown2.markdown(msg), subject, txt=msg, from_defs=from_defs)

def sendmail(recipients, sender='', msg='', subject='[No Subject]', txt=None, \
		parts=[], cc=[], attach=[], send_now=1, reply_to=None, template=None, from_defs=0):
	"""
		send an html email as multipart with attachments and all
	"""

	from webnotes.utils.email_lib.html2text import html2text
	from webnotes.utils.email_lib.send import EMail
	import HTMLParser
		
	email = EMail(sender, recipients, subject, reply_to=reply_to, from_defs=from_defs)
	email.cc = cc
	
	if msg:		
		if template:			
			msg = make_html_body(msg, template)
		else:
			# if not html, then lets put some whitespace
			if (not '<br>' in msg) and (not '<p>' in msg):
				msg = msg.replace('\n','<br>')
		
		footer = get_footer()

		footer = footer

		msg = msg + (footer or '')
		if txt:
			email.set_text(txt)
		else:
			try:
				email.set_text(html2text(msg))
			except HTMLParser.HTMLParseError:
				pass
		email.set_html(msg)
	for p in parts:
		email.set_message(p[1])
	for a in attach:
		email.attach(a)

	email.send(send_now)


def get_footer():
	"""
		Returns combination of footer from globals and Control Panel
	"""

	footer = webnotes.conn.get_value('Control Panel',None,'mail_footer') or ''
	footer += (webnotes.conn.get_global('global_mail_footer') or '')
	return footer

@webnotes.whitelist()
def send_form():
	"""
		Emails a print format (form)
		Called from form UI
	"""
	
	from webnotes.utils.email_lib.form_email import FormEmail
	FormEmail().send()

@webnotes.whitelist()
def get_contact_list():
	"""
		Returns contacts (from autosuggest)
	"""

	cond = ['`%s` like "%s%%"' % (f, 
		webnotes.form_dict.get('txt')) for f in webnotes.form_dict.get('where').split(',')]
	cl = webnotes.conn.sql("select `%s` from `tab%s` where %s" % (
  			 webnotes.form_dict.get('select')
			,webnotes.form_dict.get('from')
			,' OR '.join(cond)
		)
	)
	webnotes.response['cl'] = filter(None, [c[0] for c in cl])
	

