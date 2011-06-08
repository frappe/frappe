class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d,dl

	# export
	def on_update(self):
		import webnotes.defs
		
		if hasattr(webnotes.defs, 'developer_mode') and webnotes.defs.developer_mode:
			from webnotes.modules.export_module import export_to_files	
			from webnotes.modules import get_module_path, scurb
			import os
			
			export_to_files(record_list=[['Stylesheet', self.doc.name]])

			file = open(os.path.join(get_module_path(self.doc.module), 'Stylesheet', scrub(self.doc.name), scrub(self.doc.name) + '.html'), 'w')
			file.write(self.doc.content)
			file.close()	