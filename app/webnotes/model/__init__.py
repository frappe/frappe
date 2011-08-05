# model __init__.py
import webnotes

def get_coll(doctype, name=None, module=None, models=[]):
	"""
		wrapper for webnotes.model.collection_factory.get
	"""
	from webnotes.model.collection_factory import get
	return get(doctype, name, module, models)