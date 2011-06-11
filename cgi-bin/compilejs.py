class wnJSCompiler:
	def concate_files_in_subdirs(self,path,dest):
		"""
		Concatenates all files in a subdir (recursive)
		"""
		import os
		allfiles = []
		for root, subdir, files in os.walk(path):
			for filename in files:
				allfiles.append(os.path.join(root,filename))
		print path
		print allfiles
		print '----'
		fout = open(dest,'w')
		for filename in allfiles:
			f = open(filename)
			fout.write(f.read())
			f.close
		fout.close
		
	
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
	def compilejs(self,path):
		"""
		Compiles the js tree for ondemand import
		"""
		import os
		subs = self.getsubs(path)
		for subdir in subs:
			modname = self.getmodname(subdir)
			self.concate_files_in_subdirs(subdir,os.path.join(subdir, modname))
			self.minifyjs(os.path.join(subdir, modname))

	def minifyjs(self,modpath):
		"""
		Stub to minify js
		"""
		pass
	
	def getmodname(self,modpath,ext='.js'):
		"""
		returns filename for the stiched file		
		"""
		import os
		b = modpath.split(os.sep)
		modname = b[-1] + ext
		return modname


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
