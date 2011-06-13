class wnJSCompiler:
	@staticmethod
	def concate_files_in_dir(path,dest):
		"""
		Concatenates all files in a directory 
		"""
		import os
		allfiles = []
		dirname = path
		l = os.listdir(path)
		for i in l:
			if os.path.isfile(os.path.join(dirname,i)):
				allfiles.append(os.path.join(dirname,i))
		fout = open(dest,'w')
		for filename in allfiles:
			f = open(filename)
			fout.write(f.read())
			f.close
		fout.close
		
	
	@staticmethod
	def getsubs(path):
		"""
		gets all the sub directories of a directory (recursive)
		"""
		import os
		subs = []
		for root, subd, files in os.walk(path):
			for i in subd:
				subs.append(os.path.join(root,i))
		return subs
	@staticmethod
	def compilejs(path):
		"""
		Compiles the js tree for ondemand import
		"""
		if not wnJSCompiler.is_changed(path):
			return

		import os
		import webnotes.utils.jsnamespace as jsn
		subs = wnJSCompiler.getsubs(path)
		for subdir in subs:
			modname = jsn.jsNamespace.getmodname(subdir)
			wnJSCompiler.concate_files_in_dir(subdir,os.path.join(subdir, modname))
			wnJSCompiler.minifyjs(os.path.join(subdir, modname))

	@staticmethod
	def is_changed(path):
		#compare new timestamps with the ones stored in file
		from webnotes.utils import jstimestamp
		try:
			frm_file = jstimestamp.generateTimestamp.read_ts_from_file(path)
			newts = jstimestamp.generateTimestamp.gents(path)
		except IOError:
			return True
		if frm_file == newts:
			return False
		else:
			return True


	@staticmethod
	def minifyjs(modpath):
		"""
		Stub to minify js
		"""
		pass

if __name__=="__main__":
	a = wnJSCompiler()
	print a.compilejs('../js/wntest')
