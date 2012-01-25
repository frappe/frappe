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

		parts = self.doc.file_name.split('.')

		same = webnotes.conn.sql("""select name from `tabFile Data` 
			where name like %s order by name desc""", self.doc.file_name)
		
		if same:
			# check for more
			other_list = webnotes.conn.sql("""select name from `tabFile Data` 
				where name like '%s-%%.%s' order by name desc""" % (parts[0], '.'.join(parts[1:])))
			
				if other_list:
					last_name = other_list[0][0]
				
					from webnotes.utils import cint
					new_id = str(cint(last_name.split('.')[0].split('-')[-1]) + 1)
				else:
					new_id = '1'
					
			# new name	
			self.doc.file_name = parts[0] + '-' + new_id + '.' + '.'.join(parts[1:])
		
		self.doc.name = self.doc.file_name