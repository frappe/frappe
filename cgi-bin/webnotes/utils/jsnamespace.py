class jsNamespace:
	@staticmethod
	package_prefix = '_'
	def modname_to_filename(modname,jsdir, ext='.js'):
		import os
		path = modname.replace('.',os.sep)
		path = os.path.join(jsdir,path)
		if os.path.isdir(path):
			#package 
			packagename = self.package_prefix + path.split(os.sep)[-1]
			path = os.path.join(path,packagename)
		elif os.path.isfile(path + ext):
			path = path + ext
		else:
			path = 'notf' # TODO raise exception that it doesnt exist
		return path

	def getmodname(self,modpath,ext='.js'):
		"""
		returns filename for the stiched file		
		"""
		import os
		b = modpath.split(os.sep)
		modname = package_prefix + b[-1] + ext
		return modname
