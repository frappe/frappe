class generateTimestamp:
	ts_filename = 'timestamp.js'
	@staticmethod
	def list_js_files(jsdir,ext='js'):
		import os
		all_files= []
		nono = ['./tiny_mce','./jquery']
		oldcwd = os.getcwd()
		os.chdir(jsdir)
		# TODO Sanitize the loop below
		for root, subfolders, files in os.walk('.'):
			if generateTimestamp.is_allowed(nono,root):
				for filename in files:
					if filename.endswith(ext):
						all_files.append(os.path.join(root,filename))
		
		os.chdir(oldcwd)
		for i in nono:
			for j in all_files:
				if j.startswith(i):
					all_files.remove(j)
		return all_files
	
	@staticmethod
	def is_allowed(disallowed,item):
		for i in disallowed:
			if item.startswith(i):
				return False
		return True

	
	@staticmethod
	def get_timestamp_dict(jsdir,filelist):
		tsdict={}
		import os
		import webnotes.modules as webmod
		oldcwd = os.getcwd()
		os.chdir(jsdir)
		for filename in generateTimestamp.list_js_files('.'):
			ts = webmod.get_file_timestamp(filename)
			filename = filename.lstrip('./')
			filename = filename.rstrip('.js')
			filename = filename.replace('/','.')
			#TODO Remove _packagename from the end if file is a package
			tsdict[filename] = ts
		os.chdir(oldcwd)
		return tsdict
	
	@staticmethod
	def read_ts_from_file(jsdir):
		import json
		filename=generateTimestamp.ts_filename
		f = open(generateTimestamp.ts_filename)
		tsjson = eval(f.read())
		f.close()
		ret = json.loads(tsjson)
		return ret
	
	@staticmethod
	def gents(jsdir):
		fl=generateTimestamp.list_js_files(jsdir)
		return generateTimestamp.get_timestamp_dict(jsdir,fl)

	@staticmethod
	def gentsfile(jsdir):
		"""
		function to generate timestamps of all files in spath
		dpath is the file in which the timestamps JSON is stored
		"""
		import json
		import os
		tsdict = generateTimestamp.gents(jsdir)
		f = open(os.path.join(jsdir,'wn',generateTimestamp.ts_filename),'w') #FIXME Hard coded!
		f.write('wn={}\n')
		f.write('wn.timestamp=')
		f.write(json.dumps(tsdict))
		f.close()
