class jsNamespace:
	package_prefix = '_'
	@staticmethod
	def modname_to_filename(modname,jsdir, ext='.js'):
		import os
		path = modname.replace('.',os.sep)
		path = os.path.join(jsdir,path)
		if jsNamespace.is_package(modname,jsdir):
			packagename = jsNamespace.getmodfilename(modname)
			path = os.path.join(path,packagename)
		elif jsNamespace.is_jsfile(modname,jsdir,ext):
			path = path + ext
		else:
			path = 'notf' # TODO raise exception that it doesnt exist
		return path
	@staticmethod
	def is_package(modname,jsdir):
		import os
		path = modname.replace('.',os.sep)
		path = os.path.join(jsdir,path)
		return os.path.isdir(path)
	@staticmethod
	def is_jsfile(modname,jsdir,ext='.js'):
		import os
		path = modname.replace('.',os.sep)
		path = os.path.join(jsdir,path)
		return os.path.isfile(path + ext)

	@staticmethod
	def getmodname(modpath,ext='.js'):
		"""
		returns filename for the stiched file		
		"""
		import os
		b = modpath.split(os.sep)
		modname = jsNamespace.package_prefix + b[-1] + ext
		return modname
	@staticmethod
	def getmodfilename(modname,ext='.js'):
		ret = modname.split('.')
		ret = ret[-1]
		ret = jsNamespace.getmodname(ret)
		return ret
