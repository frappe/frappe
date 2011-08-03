"""
	`Model Def` represents the model definition collection
"""

import webnotes
from webnotes.model.collection import FileCollection

class ModelDef(FileCollection):
	"""
		Class for Meta Model (DocType)
	"""
	def __init__(self, name, module=''):
		"""
			Load the model (from file)
		"""
		if not module:
			# load module from table
			from webnotes.modules import get_module_name
			module = get_module_name(name)

		self.module = module
		self.name = name
		self.doctype = 'DocType'
		
		
		self.read()
		
		from core.doctype.property_setter.override_properties import PropertyOverrider
		PropertyOverrider(self).override()

	