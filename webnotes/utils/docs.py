"""Documentation Generation"""

import webnotes
import inspect, importlib, os

@webnotes.whitelist()
def get_docs():
	docs = {}
	get_docs_for(docs, "webnotes")
	return docs
	
def get_docs_for(docs, name):
	classname = ""
	parts = name.split(".")

	if not parts[-1] in docs:
		docs[parts[-1]] = {}
		
	mydocs = docs[parts[-1]]
	try:
		obj = importlib.import_module(name)
	except ImportError:
		# class
		name, classname = ".".join(parts[:-1]), parts[-1]
		module = importlib.import_module(name)
		obj = getattr(module, classname)
	
	mydocs["_intro"] = getattr(obj, "__doc__", "")
	mydocs["_toc"] = getattr(obj, "_toc", "")
	mydocs["_type"] = inspect.isclass(obj) and "class" or "module"
	
	for name in dir(obj):
		value = getattr(obj, name)
		if (mydocs["_type"]=="class" and inspect.ismethod(value)) or \
			(mydocs["_type"]=="module" and inspect.isfunction(value)):
			mydocs[name] = {
				"_type": "function",
				"_args": inspect.getargspec(value)[0],
				"_help": getattr(value, "__doc__", "")
			}
	
	if mydocs["_toc"]:
		for name in mydocs["_toc"]:
			get_docs_for(mydocs, name)
	
	return mydocs
	
@webnotes.whitelist()
def write_doc_file(name, html):
	if not os.path.exists("docs"):
		os.mkdir("docs")
	
	with open(os.path.join("docs", name + ".html"), "w") as docfile:
		docfile.write(html)

if __name__=="__main__":
	print get_docs_for({}, "webnotes.db.Database")