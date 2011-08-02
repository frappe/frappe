"""
	`Model Def` represents the model definition collection
"""

import webnotes
from webnotes.model.model import Model
from webnotes.db import NO_TABLE

class ModelDef(Collection):
	"""
		Class for Meta Model (DocType)
	"""
	def __init__(self, module, name):
		"""
			Load the model (from file)
		"""
		self.module = module
		self.name = name
		self.doctype = 'DocType'
		
		self.from_files(self.module)
		
		from core.doctype.property_setter.override_properties import PropertyOverrider
		PropertyOverrider(self).override()

	