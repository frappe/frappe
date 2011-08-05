from webnotes.modules.module_file import ModuleFile


class ModuleFileJs(ModuleFile):
	"""
		JS File. read method will read file and replace all $import() with relevant code
		Example::
			$import(accounts/common.js)
	"""
	def __init__(self, path):
		ModuleFile.__init__(self, path)
	
	def get_js(self, match):
		"""
			New style will expect file path or doctype
			
		"""
		name = match.group('name')
		custom = ''
		
		import webnotes.defs, os
		from webnotes.modules import get_doc_path, scrub, Module
		
		if os.path.sep in name:
			module = name.split(os.path.sep)[0]
			path = os.path.join(Module(module).get_path(), os.path.sep.join(name.split(os.path.sep)[1:]))
		else:
			# its a doctype
			path = os.path.join(get_doc_path('DocType', name), scrub(name) + '.js')
			
			# add custom script if present
			from webnotes.model.code import get_custom_script
			custom = get_custom_script(name, 'Client')
			
		return ModuleFileJs(path).read() + custom
			
	def read(self):
		"""
			return js content (replace $imports if needed)
		"""
		self.load_content()
		code = self.content
		
		if code and code.strip():
			import re
			p = re.compile('\$import\( (?P<name> [^)]*) \)', re.VERBOSE)

			code = p.sub(self.get_js, code)
			
		return code