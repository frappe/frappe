"""
Sends email via outgoing server specified in "Control Panel"
Allows easy adding of Attachments of "File" objects
"""

import webnotes	
import webnotes.defs
from webnotes import msgprint
import email

class EMail:
	"""
	Wrapper on the email module. Email object represents emails to be sent to the client. 
	Also provides a clean way to add binary `FileData` attachments
	Also sets all messages as multipart/alternative for cleaner reading in text-only clients
	"""
	def __init__(self, sender='', recipients=[], subject='', from_defs=0, alternative=0, reply_to=None):
		from email.mime.multipart import MIMEMultipart
		from email import Charset
		Charset.add_charset('utf-8', Charset.QP, Charset.QP, 'utf-8')

		if type(recipients)==str:
			recipients = recipients.replace(';', ',')
			recipients = recipients.split(',')
			
		self.from_defs = from_defs
		self.sender = sender
		self.reply_to = reply_to or sender
		self.recipients = recipients
		self.subject = subject
		
		self.msg_root = MIMEMultipart('mixed')
		self.msg_multipart = MIMEMultipart('alternative')
		self.msg_root.attach(self.msg_multipart)
		self.cc = []
	
	def set_text(self, message):
		"""
			Attach message in the text portion of multipart/alternative
		"""
		from email.mime.text import MIMEText		
		msg = unicode(message, 'utf-8')
		part = MIMEText(msg.encode('utf-8'), 'plain', 'UTF-8')		
		self.msg_multipart.attach(part)
		
	def set_html(self, message):
		"""
			Attach message in the html portion of multipart/alternative
		"""
		from email.mime.text import MIMEText		
		part = MIMEText(message, 'html')
		self.msg_multipart.attach(part)
	
	def set_message(self, message, mime_type='text/html', as_attachment=0, filename='attachment.html'):
		"""
			Append the message with MIME content to the root node (as attachment)
		"""
		from email.mime.text import MIMEText
		
		maintype, subtype = mime_type.split('/')
		part = MIMEText(message, _subtype = subtype)
		
		if as_attachment:
			part.add_header('Content-Disposition', 'attachment', filename=filename)
		
		self.msg_root.attach(part)
		
	def attach_file(self, n):
		"""
		attach a file from the `FileData` table
		"""
		from webnotes.utils.file_manager import get_file		
		res = get_file(n)
		if not res:
			return
	
		self.add_attachment(res[0], res[1])
	
	def add_attachment(self, fname, fcontent, content_type=None):
	
		from email.mime.audio import MIMEAudio
		from email.mime.base import MIMEBase
		from email.mime.image import MIMEImage
		from email.mime.text import MIMEText
					
		import mimetypes

		if not content_type:
			content_type, encoding = mimetypes.guess_type(fname)

		if content_type is None:
			# No guess could be made, or the file is encoded (compressed), so
			# use a generic bag-of-bits type.
			content_type = 'application/octet-stream'
		
		maintype, subtype = content_type.split('/', 1)
		if maintype == 'text':
			# Note: we should handle calculating the charset
			part = MIMEText(fcontent, _subtype=subtype)
		elif maintype == 'image':
			part = MIMEImage(fcontent, _subtype=subtype)
		elif maintype == 'audio':
			part = MIMEAudio(fcontent, _subtype=subtype)
		else:
			part = MIMEBase(maintype, subtype)
			part.set_payload(fcontent)
			# Encode the payload using Base64
			from email import encoders
			encoders.encode_base64(part)
			
		# Set the filename parameter
		if fname:
			part.add_header('Content-Disposition', 'attachment', filename=fname)

		self.msg_root.attach(part)
	
	def validate(self):
		"""
		validate the email ids
		"""
		if not self.sender:
			self.sender = webnotes.conn.get_value('Control Panel',None,'auto_email_id')

		from webnotes.utils import validate_email_add
		# validate ids
		if self.sender and (not validate_email_add(self.sender)):
			webnotes.msgprint("%s is not a valid email id" % self.sender, raise_exception = 1)

		if self.reply_to and (not validate_email_add(self.reply_to)):
			webnotes.msgprint("%s is not a valid email id" % self.reply_to, raise_exception = 1)

		for e in self.recipients:
			if not validate_email_add(e):
				webnotes.msgprint("%s is not a valid email id" % e, raise_exception = 1)
	
	def setup(self):
		"""
		setup the SMTP (outgoing) server from `Control Panel` or defs.py
		"""
		if self.from_defs:
			import webnotes
			self.server = getattr(webnotes.defs,'mail_server','')
			self.login = getattr(webnotes.defs,'mail_login','')
			self.port = getattr(webnotes.defs,'mail_port',None)
			self.password = getattr(webnotes.defs,'mail_password','')
			self.use_ssl = getattr(webnotes.defs,'use_ssl',0)

		else:	
			import webnotes.model.doc
			from webnotes.utils import cint

			# get defaults from control panel
			cp = webnotes.model.doc.Document('Control Panel','Control Panel')
			self.server = cp.outgoing_mail_server or getattr(webnotes.defs,'mail_server','')
			self.login = cp.mail_login or getattr(webnotes.defs,'mail_login','')
			self.port = cp.mail_port or getattr(webnotes.defs,'mail_port',None)
			self.password = cp.mail_password or getattr(webnotes.defs,'mail_password','')
			self.use_ssl = cint(cp.use_ssl)

	def make_msg(self):
		self.msg_root['Subject'] = self.subject
		self.msg_root['From'] = self.sender
		self.msg_root['To'] = ', '.join([r.strip() for r in self.recipients])
		if self.reply_to and self.reply_to != self.sender:
			self.msg_root['Reply-To'] = self.reply_to
		if self.cc:
			self.msg_root['CC'] = ', '.join([r.strip() for r in self.cc])
	
	def add_to_queue(self):
		# write to a file called "email_queue" or as specified in email
		q = EmailQueue()
		q.push({
			'server': self.server, 
			'port': self.port, 
			'use_ssl': self.use_ssl,
			'login': self.login,
			'password': self.password,
			'sender': self.sender,
			'recipients': self.recipients, 
			'msg': self.msg_root.as_string()
		})
		q.close()

	def send(self, send_now = 0):
		"""		
		send the message
		"""
		from webnotes.utils import cint
		
		self.setup()
		self.validate()
		self.make_msg()
		
		if (not send_now) and getattr(webnotes.defs, 'batch_emails', 0):
			self.add_to_queue()
			return
		
		sess = self.smtp_connect()
		
		sess.sendmail(self.sender, self.recipients, self.msg_root.as_string())
		
		try:
			sess.quit()
		except:
			pass
	

	def smtp_connect(self):
		"""
			Gets a smtp connection
		"""
		from webnotes.utils import cint
		import smtplib
		sess = smtplib.SMTP(self.server.encode('utf-8'), cint(self.port) or None)
		
		if self.use_ssl: 
			sess.ehlo()
			sess.starttls()
			sess.ehlo()
		
		ret = sess.login(self.login.encode('utf-8'), self.password.encode('utf-8'))

		# check if logged correctly
		if ret[0]!=235:
			msgprint(ret[1])
			raise Exception

		return sess


# ===========================================
# Email Queue
# Maintains a list of emails in a file
# Flushes them when called from cron
# Defs settings:
# 	email_queue: (filename) [default: email_queue.py]
#
# From the scheduler, call: flush(qty)
# ===========================================

class EmailQueue:
	def __init__(self):
		self.server = self.login = self.sess = None
		self.filename = getattr(webnotes.defs, 'email_queue', 'email_queue.py')
	
		try:
			f = open(self.filename, 'r')
			self.queue = eval(f.read() or '[]')
			f.close()
		except IOError, e:
			if e.args[0]==2:
				self.queue = []
			else:
				raise e
		
	def push(self, email):
		self.queue.append(email)
		
	def close(self):
		f = open(self.filename, 'w')
		f.write(str(self.queue))
		f.close()

	def get_smtp_session(self, e):
		if self.server==e['server'] and self.login==e['login'] and self.sess:
			return self.sess

		webnotes.msgprint('getting server')

		import smtplib
	
		sess = smtplib.SMTP(e['server'], e['port'] or None)
		
		if self.use_ssl: 
			sess.ehlo()
			sess.starttls()
			sess.ehlo()
			
		ret = sess.login(e['login'], e['password'])

		# check if logged correctly
		if ret[0]!=235:
			webnotes.msgprint(ret[1])
			raise Exception
						
		self.sess = sess
		self.server, self.login = e['server'], e['login']
		
		return sess
		
	def flush(self, qty = 100):
		f = open(self.filename, 'r')
		
		self.queue = eval(f.read() or '[]')
		
		if len(self.queue) < 100:
			qty = len(self.queue)

		for i in range(qty):
			e = self.queue[i]
			sess = self.get_smtp_session(e)
			sess.sendmail(e['sender'], e['recipients'], e['msg'])			
		
		self.queue = self.queue[:(len(self.queue) - qty)]
		self.close()

