"""
	Override field properties in a Model (doctype) that are updated by "Property Setter"
	The term "property" is used to define a fieldname of a field to avoid confusing
	terminology
"""


class PropertyOverrider:
	def __init__(self, model_def):
		self.model_def = model_def
	
	def override(self):
		"""
			Override properties for the given model
		"""
		self.make_override_property_dict()
		self.override_in_children()
		self.override_in_parent()

	def make_override_property_dict(self):
		"""
			Make `Property Setter` dictionaries
		"""
		from webnotes.utils import cint
		
		# load field properties and add them to a dictionary
		self.field_props = fp = {}
		self.parent_props = {}
		
		dt = self.model_def.parent.name
		try:
			for f in webnotes.conn.sql("select property, property_type, value, doctype_or_field from `tabProperty Setter` where doc_type=%s", dt, as_dict=1):
				if f['property_type']=='Check':
					f['value']= cint(f['value'])
				
				# for fields
				if f['doctype_or_field']=='DocField':
					if not fp[f['fieldname']]:
						fp[f['fieldname']] = {}
						
					fp[f['fieldname']][f['property']] = f['value']
				
				# for parent
				else:
					self.parent_props[f['property']] = f['value']
					
		except Exception, e:
			if e.args[0]==NO_TABLE:
				pass
			else: 
				raise e
		return property_dict

	def override_in_children(self):
		"""
			Override properties in children
		"""
		# loop over fields and override property
		if not self.field_props:
			return
			
		for d in self.model_def.children:
			if d.doctype=='DocField':
				if d.fieldname in self.field_props:
					d.__dict__.update(self.field_props[d.fieldname])

	def override_in_parent(self):
		"""
			Override in parent
		"""
		if self.parent_props:
			self.model_def.parent.__dict__.update(self.parent_props)
	