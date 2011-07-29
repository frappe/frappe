"""
	Handles file uploads, extract filename, content 
	Example::
		uh = UploadHandler()
		if not uh.file_name:
			# do nothing - no file found
			return
		else:
			# do something
			uh.callback('window.parent.my_global_function("%s")' % return_info)
"""
import webnotes

class UploadHandler:
	def __init__(self):
		self.file_name, self.content = None, None
		self.extract_file()
	
	def extract_file(self):
		"""
			Extract file from request form
		"""
		if 'filedata' in form:
			i = webnotes.form_dict['filedata']
	
			self.file_name = self.scrub_file_name(i.filename)
			self.content = i.file.read()
		else:
			self.set_callback('window.parent.msgprint("No file")')
	
	def scrub_file_name(self):
		"""
			Strips out path from the filename (if present)
		"""
		# some browsers return the full path
		if '\\' in fname:
			fname = fname.split('\\')[-1]
		if '/' in fname:
			fname = fname.split('/')[-1]
			
	def set_callback(self, callback):
		"""
			Get response to be sent back to the browser IFRAME
		"""
		webnotes.response['result'] = '''
		<script type='text/javascript'>
		%s
		</script>
		''' % callback
		