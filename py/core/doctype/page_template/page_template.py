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
	
	# export
	def on_update(self):
		import webnotes.defs
		from webnotes.modules.export_module import export_to_files	
		from webnotes.modules import get_module_path, scrub
		import os
		
		if hasattr(webnotes.defs, 'developer_mode') and webnotes.defs.developer_mode:
			
			export_to_files(record_list=[['Page Template', self.doc.name]])

			file = open(os.path.join(get_module_path(self.doc.module), 'Page Template', self.doc.name, self.doc.name + '.html'), 'w')
			file.write(self.doc.content)
			file.close()