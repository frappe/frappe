# Chai Project 0.1
# (c) 2011 Web Notes Technologies
# Chai Project may be freely distributed under MIT license
# Authors: Rushabh Mehta (rmehta at gmail)

class HTTPResponse:
	"""
	Reponse object that goes to the client
	"""
	def __init__(self):
		self.headers = {
			'Content-Type':'text/plain'
			'Content-Encoding': None,
			'Content-Length': None,
		}
		self.content_charset = 'Charset: ISO-8859-1'
		self.content = None
		self.cookies = None
		self.messages = []
		self.notifications = []
		self.exc = []
		self.data = {}
		self.out = []
		self.compressed = False
		self.attachment = True
	
	def set_file(self, file_name, file_content, as_attachment=None):
		"""
		Add file for attachment / download
		"""
		import mimetypes
		
		self.file_name = file_name
		self.file_content = file_content
		self.headers['Content-Type'] = mimetypes.guess_type(file_name)[0] \
			or 'application/unknown'
		
		self.headers['Content-Disposition'] = '%sfilename=%s' % \
			(as_attachment and 'attachment; ' or '', file_name))

		self.content = hasattr(file_content, 'toString') and file_content.toString() or file_content
		self.attachment = True

	def make_header(self):
		"""
		Build the response header
		"""
		# set the charset
		if self.content_charset:
			self.headers['Content-Type'] += '; ' + self.content_charset

		self.headers['Content-Length'] = len(self.content)
		
		# headers
		for key in self.headers:
			if self.headers[key]:
				out.append(key + ': ' + self.headers[key])
		
		if not self.attachment:
			self.out.append(self.cookies)
		

		out.append('')
	
	def accepts_gzip(self):
		"""
		Returns True if client accepts gzip
		"""
		import os, string
		if string.find(os.environ["HTTP_ACCEPT_ENCODING"], "gzip") != -1:
			return True
			
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
			self.content = json.dumps({
				'messages': self.messages,
				'notifications': self.notifications,
				'exc': self.exc,
				'data': data
			})
			
			# compress
			if not self.compressed:
				self.gzip_content()
				
	
				
	def to_string(self):
		"""
		Return the response as string
		"""

		if not self.attachment:
			self.build_content()

		self.make_headers()
		self.out.append(self.content)
		
		return '\n'.join(out)
