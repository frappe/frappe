"""
	DocLayer is a Single DocType used to mask the Property Setter
	Thus providing a better UI from user perspective
"""

class DocType:
	def __init__(self, doc, doclist=[]):
		self.doc, self.doclist = doc, doclist
		self.doctype_properties = [
			'autoname',
			'search_fields',
			'tag_fields',
			'default_print_format',
			'read_only_onload',
			'allow_print',
			'allow_email',
			'allow_copy',
			'allow_rename',
			'allow_attach',
			'max_attachments' 
		]
		self.docfield_properties = [
			'label',
			'fieldtype',
			'fieldname',
			'options',
			'permlevel',
			'width',
			'reqd',
			'in_filter',
			'hidden',
			'print_hide',
			'no_copy',
			'report_hide',
			'allow_on_submit',
			'depends_on',
			'description',
			'default',
			'name'
		]

	def get(self):
		"""
			Gets DocFields applied with Property Setter customizations via DocLayerField
		"""
		from webnotes.model.doctype import get
		from webnotes.model.doc import addchild
		import webnotes

		self.clear()

		if self.doc.doc_type:
			for d in get(self.doc.doc_type):
				if d.doctype=='DocField':
					new = addchild(self.doc, 'fields', 'DocLayerField', 1, self.doclist)
					self.set(
						{
							'list': self.docfield_properties,
							'doc' : d,
							'doc_to_set': new
						}
					)
				elif d.doctype=='DocType':
					self.set({ 'list': self.doctype_properties, 'doc': d })

	def post(self):
		"""
			Save diff between DocLayer DocList and DocType DocList as property setter entries
		"""
		pass


	def clear(self):
		"""
			Clear fields in the doc
		"""
		# Clear table before adding new doctype's fields
		self.doc.clear_table(self.doclist, 'fields')
		self.set({ 'list': self.doctype_properties, 'value': None })
	
		
	def set(self, args):
		"""
			Set a list of attributes of a doc to a value
			or to attribute values of a doc passed
			
			args can contain:
			* list --> list of attributes to set
			* doc_to_set --> defaults to self.doc
			* value --> to set all attributes to one value eg. None
			* doc --> copy attributes from doc to doc_to_set
		"""
		if not 'doc_to_set' in args:
			args['doc_to_set'] = self.doc

		if 'list' in args:
			if 'value' in args:
				for f in args['list']:
					args['doc_to_set'].fields[f] = None
			elif 'doc' in args:
				for f in args['list']:
					args['doc_to_set'].fields[f] = args['doc'].fields[f]
		else:
			import webnotes
			webnotes.msgprint("Please specify args['list'] to set", raise_exception=1)

