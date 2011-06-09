class generate_timestamp:
	def list_js_files(self,jsdir,ext='js'):
		import os
		all_files= []
		oldcwd = os.getcwd()
		os.chdir(jsdir)
		for root, subfolders, files in os.walk('.'):
			for filename in files:
				if filename.endswith(ext):
					all_files.append(os.path.join(root,filename))
		os.chdir(oldcwd)
		return all_files
	
	def get_timestamp_dict(self,jsdir,filelist):
		tsdict={}
		import os
		import webnotes.modules as webmod
		oldcwd = os.getcwd()
		os.chdir(jsdir)
		for filename in self.list_js_files('.'):
			ts = webmod.get_file_timestamp(filename)
			filename = filename.lstrip('./')
			filename = filename.rstrip('.js')
			filename = filename.replace('/','.')
			print filename
			tsdict[filename] = ts
		os.chdir(oldcwd)
		return tsdict
	
	def gents(self,jsdir):
		fl=self.list_js_files(jsdir)
		return self.get_timestamp_dict(jsdir,fl)
