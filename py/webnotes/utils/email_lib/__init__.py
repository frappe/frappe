import webnotes

def sendmail_html(sender, recipients, subject, html, text=None, template=None, send_now=1, reply_to=None):
	"""
		Send an html mail with alternative text and using Page Templates
	"""
	sendmail(recipients, sender, html, subject, send_now = send_now, reply_to = reply_to, template = template)

def make_html_body(content, template = None):
	"""
		Generate html content from a Page Template object
	"""
	template_html = '%(content)s'

	if template:
		from webnotes.model.code import get_code
		template_html = get_code(webnotes.conn.get_value('Page Template', template, 'module'), 'Page Template', template, 'html', fieldname='template')

	return template_html % {'content': content}


def sendmail(recipients, sender='', msg='', subject='[No Subject]', parts=[], cc=[], attach=[], send_now=1, reply_to=None, template=None, from_defs=0):
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
			msg = make_html_body(msg, template).encode('utf-8')
		else:
			# if not html, then lets put some whitespace
			if (not '<br>' in msg) or (not '<p>' in msg):
				msg = msg.replace('\n','<br>')		
		footer = get_footer()
		msg = msg + (footer or '')
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


def send_form():
	"""
		Emails a print format (form)
		Called from form UI
	"""
	
	from webnotes.utils.email_lib.form_email import FormEmail
	FormEmail().send()


def get_contact_list():
	"""
		Returns contacts (from autosuggest)
	"""
	import webnotes

	cond = ['`%s` like "%s%%"' % (f, webnotes.form.getvalue('txt')) for f in webnotes.form.getvalue('where').split(',')]
	cl = webnotes.conn.sql("select `%s` from `tab%s` where %s" % (
  			 webnotes.form.getvalue('select')
			,webnotes.form.getvalue('from')
			,' OR '.join(cond)
		)
	)
	webnotes.response['cl'] = filter(None, [c[0] for c in cl])
	

