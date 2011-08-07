"""
	Returns the controller object defined in the model
	The controller object will either be in the same folder as the model
	or will be defined in __init__.py
"""

import webnotes

class ControllerFactory:
	def __init__(self, collection):
		self.collection = collection
		
	def get_module_obj(self, mname):
		"""
			Imports a module and returns the package using getattr::
				
				get_module_obj('core.models.sandbox.sandbox')
				
			returns last sandbox module
		"""
		try:
			# import the module
			exec 'import %s' % mname in locals()
			mlist = mname.split('.')
			obj = locals()[mlist[0]]
			
			# dig deeper and get the last leaf using getattr
			for m in mlist[1:]:
				obj = getattr(obj, m)
			
			return obj
			
		except ImportError, e:
			webnotes.errprint(webnotes.getTraceback())
			return None
			
	def import_model_package(self):
		"""
			import the package of the parent of the collection
		"""
		import os
		model_path = os.path.dirname(self.collection.parent._def.path).replace(os.path.sep, '.')
		return self.get_module_obj(model_path)
			
	def get_class_obj(self, package):
		"""
			Returns the class name from object
		"""
		package = self.import_model_package()

		if hasattr(package, 'controller_key'):
			try:
				class_name = package.controllers[self.collection.parent.get(package.controller_key)]
				module_obj = self.get_module_obj('.'.join(class_name.split('.')[:-1]))
				return getattr(module_obj, class_name.split('.')[-1])
			except KeyError, e:
				webnotes.errprint("Bad controller definition, taking default")
				pass
		
		# did not find controller by definition, take a new one
		return self.get_std_controller_class()
		
	def get_std_controller_class(self):
		"""
			returns the std controller object
		"""	
		model_path = self.collection.parent._def.path.replace('.model','').replace(os.path.sep, '.')
		module_obj = self.get_module_obj(model_path)
			
		std_class_name = self.collection.parent.type.replace(' ','') + 'Controller'
				
		if hasattr(module_obj, std_class_name):
			return getattr(module_obj, std_class_name)
			
	def set(self):
		"""
			Set the controller
		"""
		package = self.import_model_package()
		if package:
			self.collection.controller \
				= self.get_class_obj(package)(self.collection.parent, self.collection.models)
		else:
			self.collection.controller = None
		return