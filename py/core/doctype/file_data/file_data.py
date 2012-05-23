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

"""
record of files

naming for same name files: file.gif, file-1.gif, file-2.gif etc
"""

import webnotes

class DocType():
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def autoname(self):
		"""save file by its name"""
		if not self.doc.file_name:
			raise Exception, 'file name missing'

		if not '.' in self.doc.file_name:
			raise Exception, 'file name must have extension (.)'

		self.doc.file_name = self.doc.file_name.replace('-', '')

		parts = self.doc.file_name.split('.')

		same = webnotes.conn.sql("""select name from `tabFile Data` 
			where name=%s""", self.doc.file_name)
		
		if same:
			# check for more
			other_list = webnotes.conn.sql("""select name from `tabFile Data` 
				where name like '%s-%%.%s'""" % (parts[0], '.'.join(parts[1:])))
			
			if other_list:
				from webnotes.utils import cint
				# gets the max number from format like name-###.ext
				last_num = max(
						(cint(other[0].split('.')[0].split('-')[-1])
						for other in other_list)
					)
			else:
				last_num = 0
			
			new_id = "%03d" % (last_num + 1)
					
			# new name	
			self.doc.file_name = parts[0] + '-' + new_id + '.' + '.'.join(parts[1:])
		
		self.doc.name = self.doc.file_name