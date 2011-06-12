class jsDependencyBuilder:
	@staticmethod
	def read_code(self,js_path):
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
	def read_imports(self,code):
		import re
		p = re.compile('\$import\(\' (?P<name> [^)]*)\' \)', re.VERBOSE)
		return p.findall(code)
	@staticmethod
	def build_dependency(self,modname,depends= set()):
		import webnotes.utils.jsnamespace as jsn
		jsdir = '../js'
		js_path = jsn.jsNamespace.modname_to_filename(modname,jsdir)
		code = self.read_code(js_path)
		curdepend = self.read_imports(code)
		for i in curdepend:
			if i not in depends:
				depends.add(i)
				depends = depends.union( self.build_dependency(i,depends))
		return depends
