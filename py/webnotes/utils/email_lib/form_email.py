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

import webnotes
from webnotes.utils import cint

form = webnotes.form

from webnotes.utils.email_lib import get_footer
from webnotes.utils.email_lib.send import EMail

class FormEmail:
	"""
		Represents an email sent from a Form
	"""
	def __init__(self):
		"""
			Get paramteres from the cgi form object
		"""
		self.__dict__.update(webnotes.form_dict)		

		self.recipients = None
		if self.sendto:
			self.recipients = self.sendto.replace(';', ',')
			self.recipients = self.recipients.split(',')

	def update_contacts(self):
		"""
			Add new email contact to database
		"""
		import webnotes
		from webnotes.model.doc import Document

		for r in self.recipients:
			r = r.strip()
			try:
				if not webnotes.conn.sql("select email_id from tabContact where email_id=%s", r):
					d = Document('Contact')
					d.email_id = r
					d.save(1)
			except Exception, e:
				if e.args[0]==1146: pass # no table
				else: raise e
	
	def make_full_links(self):
		"""
			Adds server name the relative links, so that images etc can be seen correctly
		"""
		# only domain
		if not self.__dict__.get('full_domain'):
			return
			
		def make_full_link(match):
			import os
			link = match.group('name')
			if not link.startswith('http'):
				link = os.path.join(self.full_domain, link)
			return 'src="%s"' % link

		import re
		p = re.compile('src[ ]*=[ ]*" (?P<name> [^"]*) "', re.VERBOSE)
		self.body = p.sub(make_full_link, self.body)

		p = re.compile("src[ ]*=[ ]*' (?P<name> [^']*) '", re.VERBOSE)
		self.body = p.sub(make_full_link, self.body)

	def get_form_link(self):
		"""
			Returns publicly accessible form link
		"""
		public_domain = webnotes.conn.get_value('Control Panel', None, 'public_domain')
		from webnotes.utils.encrypt import encrypt

		if not public_domain:
			return ''

		args = {
			'dt': self.dt, 
			'dn':self.dn, 
			'acx': webnotes.conn.get_value('Control Panel', None, 'account_id'),
			'server': public_domain,
			'akey': encrypt(self.dn)
		}
		return '<div>If you are unable to view the form below <a href="http://%(server)s/index.cgi?page=Form/%(dt)s/%(dn)s&acx=%(acx)s&akey=%(akey)s">click here to see it in your browser</div>' % args

	def set_attachments(self):
		"""
			Set attachments to the email from the form
		"""
		al = []
		try:
			al = webnotes.conn.sql('select file_list from `tab%s` where name="%s"' % (form.getvalue('dt'), form.getvalue('dn')))
			if al:
				al = (al[0][0] or '').split('\n')
		except Exception, e:
			if e.args[0]==1146:
				pass # no attachments in single types!
			else:
				raise Exception, e
		return al
	
	def build_message(self):
		"""
			Builds the message object
		"""

		self.email = EMail(self.sendfrom, self.recipients, self.subject, alternative = 1)

		from webnotes.utils.email_lib.html2text import html2text

		self.make_full_links()

		# message
		if not self.__dict__.get('message'):
			self.message = 'Please find attached %s: %s\n' % (self.dt, self.dn)

		html_message = text_message = self.message.replace('\n','<br>')
		
		# separator
		html_message += '<div style="margin:17px 0px; border-bottom:1px solid #AAA"></div>'

		# form itself (only in the html message)
		html_message += self.body

		# form link
		html_message += self.get_form_link()
		text_message += self.get_form_link()

		# footer
		footer = get_footer()
		if footer: 
			html_message += footer
			text_message += footer

		# message as text
		self.email.set_text(html2text(text_message))
		self.email.set_html(html_message)
					
	def send(self):
		"""
			Send the form with html attachment
		"""

		if not self.recipients:
			webnotes.msgprint('No one to send to!')
			return
			
		self.build_message()
		
		# print format (as attachment also - for text-only clients)
		self.email.add_attachment(self.dn.replace(' ','').replace('/','-') + '.html', self.body)

		# attachments
		# self.with_attachments comes from http form variables
		# i.e. with_attachments=1
		if cint(self.with_attachments):
			for a in self.set_attachments():
				a and self.email.attach_file(a.split(',')[0])

		# cc
		if self.cc:
			self.email.cc = [self.cc]
		
		self.email.send(send_now=1)
		webnotes.msgprint('Sent')