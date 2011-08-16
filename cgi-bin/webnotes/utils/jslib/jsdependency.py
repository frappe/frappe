class jsDependencyBuilder:
	@staticmethod
	def read_code(js_path):
		try:
			f = open(js_path)
			try:
				code = f.read()
			finally:
				f.close
		except Exception, e:
			raise e
		return code
	@staticmethod
	def read_imports(code):
		import re
		p = re.compile('\$import\(\' (?P<name> [^)]*)\' \)', re.VERBOSE)
		return p.findall(code)
	@staticmethod
	def build_dependency(jsdir,modname,depends= set()):
		import webnotes.utils.jsnamespace as jsn
		js_path = jsn.jsNamespace.modname_to_filename(modname,jsdir)
		code = jsDependencyBuilder.read_code(js_path)
		curdepend = jsDependencyBuilder.read_imports(code)
		for i in curdepend:
			if i not in depends:
				depends.add(i)
				depends = depends.union( jsDependencyBuilder.build_dependency(jsdir,i,depends))
		return depends
	def build_dependency_from_file(modname,depends= set()):
		# TODO STUB to read dependency from dependency tree stored in file
		return jsDependencyBuilder.build_dependency(modname)	
