class generateTimestamp:
	def list_js_files(self,jsdir,ext='js'):
		import os
		all_files= []
		nono = ['./tiny_mce','./jquery']
		oldcwd = os.getcwd()
		os.chdir(jsdir)
		for root, subfolders, files in os.walk('.'):
			if self.is_allowed(nono,root):
				for filename in files:
					if filename.endswith(ext):
						all_files.append(os.path.join(root,filename))

		os.chdir(oldcwd)
		for i in nono:
			for j in all_files:
				if j.startswith(i):
					all_files.remove(j)
		return all_files
	
	def is_allowed(self,disallowed,item):
		for i in disallowed:
			if item.startswith(i):
				return False
		return True

	
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
