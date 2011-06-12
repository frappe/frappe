class wnJSCompiler:
	@staticmethod
	def concate_files_in_dir(self,path,dest):
		"""
		Concatenates all files in a directory 
		"""
		import os
		allfiles = []
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
	def getsubs(self,path):
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
	def compilejs(self,path):
		"""
		Compiles the js tree for ondemand import
		"""
		import os
		import webnotes.utils.jsnamespace as jsn
		subs = self.getsubs(path)
		for subdir in subs:
			modname = jsn.jsNamespace.getmodname(subdir)
			self.concate_files_in_dir(subdir,os.path.join(subdir, modname))
			self.minifyjs(os.path.join(subdir, modname))

	@staticmethod
	def minifyjs(self,modpath):
		"""
		Stub to minify js
		"""
		pass
	



	@staticmethod
	def gentsfile(self,spath,dpath):
		"""
		function to generate timestamps of all files in spath
		dpath is the file in which the timestamps JSON is stored
		"""
		import webnotes.utils.jstimestamp as jst
		import json
		a = jst.generateTimestamp()
		f = open(dpath,'w')
		f.write('wn = {}\n')
		f.write('wn.timestamp = ')
		f.write(json.dumps(a.gents(spath)))
		f.close()
if __name__=="__main__":
	a = wnJSCompiler()
	print a.compilejs('../js/wntest')
