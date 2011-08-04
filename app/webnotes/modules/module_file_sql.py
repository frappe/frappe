from webnotes.modules.module_file import ModuleFile


class ModuleFileSql(ModuleFile):
	def __init__(self, path):
		ModuleFile.__init__(self, path)
	
	def sync(self):
		"""
			execute the sql if new
			The caller must either commit or rollback an open transaction
		"""
		if self.is_new():
			import webnotes
			content = self.read()
			
			# execute everything but selects
			# theses are ddl statements, should either earlier
			# changes must be committed or rollbacked
			# by the caller
			if content.strip().split()[0].lower() in ('insert','update','delete','create','alter','drop'):
				webnotes.conn.sql(self.read())

			# start a new transaction, as we have to update
			# the timestamp table
			webnotes.conn.begin()
			self.update()
