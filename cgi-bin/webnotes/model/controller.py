"""
	Returns the controller object defined in the model folder
"""

def set_controller(collection):
	"""
		Return instance of controller object
	"""
	import webnotes
	from webnotes.modules import get_module_name, scrub

	if not getattr(collection, 'module', None):
		# load module from table
		collection.module = get_module_name(collection.doctype)
	
	# the module for the controller
	# is the ".py" file of the doctype
	# name inside the modules folders (packages)
	_module, _doctype = scrub(collection.module), scrub(collection.doctype)
	m = '%s.doctype.%s.%s' % (_module, _doctype, _doctype)
	try:
		
		# import the module
		exec 'import %s' % m in locals()
		
	except ImportError, e:
		
		# there were errors on import
		# safe exit by returning a vanilla
		# collection
		webnotes.errprint("Error while importing %s" % m)
		webnotes.errprint(webnotes.getTraceback())
		collection.controller = None
		return

	# extract the module object from
	# the local namespace using multiple
	# getattr
	module_obj = getattr(getattr(getattr(locals()[_module], 'doctype'), _doctype), _doctype)
	
	class_obj = get_class(module_obj, collection.doctype)
	
	if class_obj:
		collection.controller = class_obj(collection.parent, collection.models)
	else:
		collection.controller = None
		
def get_class(module_obj, doctype):
	"""
		Return the class object, and type `controller` or `collection` based on naming
	"""
	class_name = doctype.replace(' ','')
	class_obj = None
	
	if hasattr(module_obj, 'DocType'):
		class_obj = getattr(module_obj, 'DocType')
		class_type = 'controller'

	elif hasattr(module_obj, class_name + 'Controller'):
		class_obj = getattr(module_obj, class_name + 'Controller')
		class_type = 'controller'
		
	return class_obj