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
		from webnotes.utils import get_file_timestamp
		oldcwd = os.getcwd()
		os.chdir(jsdir)
		for filename in generateTimestamp.list_js_files('.'):
			ts = get_file_timestamp(filename)
			filename = filename.lstrip('./')
			filename = filename.rstrip('.js')
			filename = filename.replace('/','.')
			if generateTimestamp.is_package(filename):
				# Whoa its a package
				# Remove _packagename from the end if file is a package
				filename = generateTimestamp.convert_to_packagename(filename)
			tsdict[filename] = ts
		os.chdir(oldcwd)
		return tsdict
	@staticmethod
	def is_package(filename):
		from webnotes.utils import jsnamespace
		p = jsnamespace.jsNamespace.package_prefix
		return filename.split('.')[-1].startswith() 

	@staticmethod
	def convert_to_packagename(filename):
		t = []
		for i in filename.split('.')[:-1]:
			t.append(i)
			t.append('.')
		del t[-1]
		filename = ''.join(t)
		return filename

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
