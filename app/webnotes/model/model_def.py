"""
	`Model Def` represents the model definition collection
"""

import webnotes
from webnotes.model.collection import FileCollection

class ModelDef(FileCollection):
	"""
		Class for Meta Model (DocType)
	"""
	def __init__(self, name):
		"""
			Load the model (from file)
		"""
		from webnotes.model.model_index import get_model_path
		path = get_model_path(name)

		self.name = name
		self.type = 'ModelDef'
		
		self.read()
		
		from core.doctype.property_setter.override_properties import PropertyOverrider
		PropertyOverrider(self).override()

	