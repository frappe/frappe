class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d,dl

	def autoname(self):
		if (self.doc.name and self.doc.name.startswith('New Page')) or not self.doc.name:
			self.doc.name = self.doc.page_name.lower().replace(' ', '-')

	def onload(self):
		import os
		from webnotes.modules import get_module_path, scrub
		
		# load content
		try:
			file = open(os.path.join(get_module_path(self.doc.module), 'page', scrub(self.doc.name) + '.html'), 'r')
			self.doc.content = file.read() or ''
			file.close()
		except IOError, e: # no file / permission
			if e.args[0]!=2:
				raise e

	# replace $image
	# ------------------
	def validate(self):
		import re
		p = re.compile('\$image\( (?P<name> [^)]*) \)', re.VERBOSE)
		if self.doc.content:
			self.doc.content = p.sub(self.replace_by_img, self.doc.content)
	
	def replace_by_img(self, match):
		import webnotes
		name = match.group('name')
		return '<img src="cgi-bin/getfile.cgi?ac=%s&name=%s">' % (webnotes.conn.get('Control Panel', None, 'account_id'), name)
		
	# export
	def on_update(self):
		from webnotes.modules.export_module import export_to_files
		from webnotes.modules import get_module_path, scrub
		import os
		from webnotes import defs
		
		if getattr(defs,'developer_mode', 0):
			export_to_files(record_list=[['Page', self.doc.name]])
	
			if self.doc.write_content and self.doc.content:
				file = open(os.path.join(get_module_path(self.doc.module), 'page', scrub(self.doc.name), scrub(self.doc.name) + '.html'), 'w')
				file.write(self.doc.content)
				file.close()
 
