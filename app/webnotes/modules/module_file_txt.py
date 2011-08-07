from webnotes.modules.module_file import ModuleFile

class ModuleFileTxt(ModuleFile):
	"""
		Class for .txt files, sync the doclist in the txt file into the database
	"""
	def __init__(self, path):
		ModuleFile.__init__(self, path)
	
	def get_collection(self):
		"""
			Returns the raw model collection from the file
		"""
		from webnotes.model.utils import peval_doclist
		return peval_doclist(self.read())
	
	def sync(self):
		"""
			import the doclist if new
		"""
		if self.is_new():
			doclist = get_collection()
			if doclist:
				# since there is a new timestamp on the file, update timestamp in
				# the record
				webnotes.conn.sql("update `tab%s` set modified=now() where name=%s" \
					% (doclist[0]['doctype'], '%s'), doclist[0]['name'])
					
				from webnotes.utils.transfer import set_doc
				set_doc(doclist, 1, 1, 1)
		
			self.update()
			

