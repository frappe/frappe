"""Documentation Generation"""

import webnotes

@webnotes.whitelist()
def get_docs(module_name):
	import inspect, importlib
	docs = {}
	module = importlib.import_module(module_name)
	
	docs["_intro"] = getattr(module, "__doc__", "")
	
	for name in dir(module):
		value = getattr(module, name)
		if inspect.isfunction(value):
			docs[name] = {
				"_type": "function",
				"_args": inspect.getargspec(value)[0],
				"_help": getattr(value, "__doc__", "")
			}
	
	return docs
	
if __name__=="__main__":
	print get_docs("webnotes")