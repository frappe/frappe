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

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d,dl

	def autoname(self):
		"""
			Creates a url friendly name for this page.
			Will restrict the name to 30 characters, if there exists a similar name,
			it will add name-1, name-2 etc.
		"""
		from webnotes.utils import cint
		if (self.doc.name and self.doc.name.startswith('New Page')) or not self.doc.name:
			self.doc.name = self.doc.page_name.lower().replace('"','').replace("'",'').replace(' ', '-')[:20]
			if webnotes.conn.exists('Page',self.doc.name):
				cnt = webnotes.conn.sql('select name from tabPage where name like "%s-%%" order by name desc limit 1' % self.doc.name)
				if cnt:
					cnt = cint(cnt[0][0].split('-')[-1]) + 1
				else:
					cnt = 1
				self.doc.name += '-' + str(cnt)

	def onload(self):
		"""
			loads html from file before passing
		"""
		import os
		from webnotes.modules import get_module_path, scrub
		
		# load content
		if not self.doc.module:
			return
			
		try:
			file = open(os.path.join(get_module_path(self.doc.module), 'page', scrub(self.doc.name) + '.html'), 'r')
			self.doc.content = file.read() or ''
			file.close()
		except IOError, e: # no file / permission
			if e.args[0]!=2:
				raise e

	def validate(self):
		"""
			Update $image tags
		"""
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
		"""
			Writes the .txt for this page and if write_content is checked,
			it will write out a .html file
		"""
		from webnotes import defs
		from webnotes.utils.transfer import in_transfer
		if not in_transfer and getattr(defs,'developer_mode', 0) and self.doc.standard=='Yes':
			from webnotes.modules.export_module import export_to_files
			from webnotes.modules import get_module_path, scrub
			import os
			export_to_files(record_list=[['Page', self.doc.name]])
	
			if self.doc.write_content and self.doc.content:
				file = open(os.path.join(get_module_path(self.doc.module), 'page', scrub(self.doc.name), scrub(self.doc.name) + '.html'), 'w')
				file.write(self.doc.content)
				file.close()
 
