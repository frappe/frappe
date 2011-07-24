# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (rmehta at gmail)
import webnotes
class HTTPResponse:
	"""
	Reponse object that goes to the client
	"""
	def __init__(self):
		self.headers = {
			'Content-Type':'text/plain',
			'Content-Encoding': None,
			'Content-Length': None,
		}
		self.content_charset = 'Charset: ISO-8859-1'
		self.content = None
		self.cookies = None
		# NOTE wnframework has 'message' (singular) 
		self.message = ''
		self.notifications = []
		self.exc = ''
		self.data = {}
		self.out = []
		self.compressed = False
		self.pagehtml = None
		# Setting self.attachment to False,  pitfall?
		self.attachment = False
		self.file_name = None
	
	def __setitem__(self,key,value):
		self.__dict__[key]=value
	
	def set_file(self, file_name, file_content, as_attachment=None):
		"""
		Add file for attachment / download
		"""
		import mimetypes
		
		self.file_name = file_name
		self.file_content = file_content
		self.headers['Content-Type'] = mimetypes.guess_type(file_name)[0] \
			or 'application/unknown'
		
		#FIXME : below
		#self.headers['Content-Disposition'] = '%sfilename=%s' %	(as_attachment and 'attachment; ' or '', file_name))

		self.content = hasattr(file_content, 'toString') and file_content.toString() or file_content
		self.attachment = True

	def make_header(self):
		"""
		Build the response header
		"""
		# set the charset
		if self.content_charset:
			self.headers['Content-Type'] += '; ' + self.content_charset
		if self.content:
			self.headers['Content-Length'] = str(len(self.content))
		else:
			self.headers['Content-Length'] = 0
		# headers
		for key in self.headers:
			if self.headers[key]:
				self.out.append(key + ': ' + self.headers[key])
		
		if not self.attachment:
			self.cookies and self.out.append(self.cookies.output())
		

		self.out.append('')
	
	def accepts_gzip(self):
		"""
		Returns True if client accepts gzip
		"""
		import os, string
		return False
		if string.find(os.environ["HTTP_ACCEPT_ENCODING"], "gzip") != -1:pass
			
	def gzip_content(self):
		"""
		Compress JSON before sending to server
		"""
		if len(self.content) < 512:
			# too small or already compressed
			return
		else:
			if self.accepts_gzip():
				import gzip, cStringIO
				zbuf = cStringIO.StringIO()
				zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 5)
				zfile.write(self.content)
				zfile.close()
				self.content = zbuf.getvalue()
				self.headers['Content-Encoding'] = 'gzip'

	def build_content(self):
		"""
		Build JSON content
		"""
		if not self.file_name:
			import json
			if self.pagehtml:
				self.content = self.pagehtml
			else:
				self.content = json.dumps({
					'message': self.message,
					'notifications': self.notifications,
					'exc': self.exc,
					'data': self.data,
				})
			
			# compress
			if not self.compressed:
				self.gzip_content()
				
	
				
	def to_string(self):
		"""
		Return the response as string
		"""
		#Any better way of getting the cookies?
		self.cookies = webnotes.cookie_manager.cookies
		if not self.attachment:
			self.build_content()

		self.make_header()
		if self.content:
			self.out.append(self.content)
			pass
		return '\n'.join(self.out)
#		raise Exception,str(self.out)
