# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals
		
import webnotes
import inspect, os, json, datetime, shutil
from webnotes.modules import get_doc_path, get_module_path, scrub
from webnotes.utils import get_path, get_base_path, cstr

class DocType:
	def __init__(self, d, dl):
		self.doc, self.doclist = d, dl
		
	def onload(self):
		prepare_docs()

gh_prefix = "https://github.com/webnotes/"

@webnotes.whitelist()
def get_docs(options):
	docs = {}
	options = webnotes._dict(json.loads(options))
	if options.build_server_api:
		get_docs_for(docs, "webnotes")
	if options.build_modules:
		docs["modules"] = get_modules(options.module_name)
	if options.build_pages:
		docs["pages"] = get_static_pages()
	return docs

def get_static_pages():
	mydocs = {}
	for repo in ("lib", "app"):
		for basepath, folders, files in os.walk(get_path(repo, "docs")):
			for fname in files:
				fname = cstr(fname)
				if fname.endswith(".md"):
					fpath = get_path(basepath, fname)
					with open(fpath, "r") as docfile:
						src = unicode(docfile.read(), "utf-8")
						try:
							temp, headers, body = src.split("---", 2)
							d = json.loads(headers)
						except Exception, e:
							webnotes.msgprint("Bad Headers in: " + fname)
							continue
						d["_intro"] = body
						d["_gh_source"] = get_gh_url(fpath)
						d["_modified"] = get_timestamp(fpath)
						mydocs[fname[:-3]] = d

	return mydocs

def get_docs_for(docs, name):
	"""build docs for python module"""
	import importlib
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
	
	inspect_object_and_update_docs(mydocs, obj)
	
	# if filename is __init__, list python files and folders with init in folder as _toc
	if hasattr(obj, "__file__") and os.path.basename(obj.__file__).split(".")[0]=="__init__":
		mydocs["_toc"] = []
		dirname = os.path.dirname(obj.__file__)
		for fname in os.listdir(dirname):
			fname = cstr(fname)
			fpath = os.path.join(dirname, fname)
			if os.path.isdir(fpath):
				# append if package
				if "__init__.py" in os.listdir(fpath):
					mydocs["_toc"].append(name + "." + fname)
			elif fname.endswith(".py") and not fname.startswith("__init__") and \
				not fname.startswith("test_"):
				# append if module
				mydocs["_toc"].append(name + "." + fname.split(".")[0])
		
	if mydocs.get("_toc"):
		for name in mydocs["_toc"]:
			get_docs_for(mydocs, name)
	
	return mydocs

def inspect_object_and_update_docs(mydocs, obj):
	mydocs["_toc"] = getattr(obj, "_toc", "")
	if inspect.ismodule(obj):
		obj_module = obj
		mydocs["_type"] = "module"
	else:
		obj_module = inspect.getmodule(obj)
		mydocs["_type"] = "class"

	mydocs["_icon"] = "code"
	mydocs["_gh_source"] = get_gh_url(obj_module.__file__)
	mydocs["_modified"] = get_timestamp(obj_module.__file__)
		
	if not mydocs.get("_intro"):
		mydocs["_intro"] = getattr(obj, "__doc__", "")
		
	for name in dir(obj):
		try:
			value = getattr(obj, name)
		except AttributeError, e:
			value = None
			
		if value:
			if (mydocs["_type"]=="module" and inspect.getmodule(value)==obj)\
				or (mydocs["_type"]=="class" and getattr(value, "im_class", None)==obj):
				if inspect.ismethod(value) or inspect.isfunction(value):
					mydocs[name] = {
						"_type": "function",
						"_args": inspect.getargspec(value)[0],
						"_help": getattr(value, "__doc__", ""),
						"_source": inspect.getsource(value)
					}
				elif inspect.isclass(value):
					if not mydocs.get("_toc"):
						mydocs["_toc"] = []
					mydocs["_toc"].append(obj.__name__ + "." + value.__name__)
				
def get_gh_url(path):
	sep = "/lib/" if "/lib/" in path else "/app/"
	url = gh_prefix \
		+ ("wnframework" if sep=="/lib/" else "erpnext") \
		+ ("/blob" if ("." in path) else "/tree") \
		+"/master/" + path.split(sep)[1]
	if url.endswith(".pyc"):
		url = url[:-1]
	return url

def get_modules(for_module=None):
	import importlib
	docs = {
		"_label": "Modules"
	}
	if for_module:
		modules = [for_module]
	else:
		modules = webnotes.conn.sql_list("select name from `tabModule Def` order by name")
	
	docs["_toc"] = ["docs.dev.modules." + d for d in modules]
	for m in modules:
		prefix = "docs.dev.modules." + m
		mydocs = docs[m] = {
			"_icon": "th",
			"_label": m,
			"_toc": [
				prefix + ".doctype",
				prefix + ".page",
				prefix + ".py_modules"
			],
			"doctype": get_doctypes(m),
			"page": get_pages(m),
			#"report": {},
			"py_modules": {
				"_label": "Independent Python Modules for " + m,
				"_toc": []
			}
		}
		
		# add stand alone modules
		module_path = get_module_path(m)
		prefix = prefix + ".py_modules."
		for basepath, folders, files in os.walk(module_path):
			for f in files:
				f = cstr(f)
				if f.endswith(".py") and \
					(not f.split(".")[0] in os.path.split(basepath)) and \
					(not f.startswith("__")):
				
					module_name = ".".join(os.path.relpath(os.path.join(basepath, f), 
						"../app").split(os.path.sep))[:-3]

					# import module
					try:
						module = importlib.import_module(module_name)
						# create a new namespace for the module
						module_docs = mydocs["py_modules"][f.split(".")[0]] = {}

						# add to toc
						mydocs["py_modules"]["_toc"].append(prefix + f.split(".")[0])

						inspect_object_and_update_docs(module_docs, module)
					except TypeError, e:
						webnotes.errprint("TypeError in importing " + module_name)
					except IndentationError, e:
						continue
					
					module_docs["_label"] = module_name
					module_docs["_function_namespace"] = module_name
		
		update_readme(docs[m], m)
		docs[m]["_gh_source"] = get_gh_url(module_path)
		
	return docs

def get_pages(m):
	import importlib
	pages = webnotes.conn.sql_list("""select name from tabPage where module=%s""", m)
	prefix = "docs.dev.modules." + m + ".page."
	docs = {
		"_icon": "file-alt",
		"_label": "Pages",
		"_toc": [prefix + d for d in pages]
	}
	for p in pages:
		page = webnotes.doc("Page", p)
		mydocs = docs[p] = {
			"_label": page.title or p,
			"_type": "page",
		}
		update_readme(mydocs, m, "page", p)
		mydocs["_modified"] = page.modified

		# controller
		page_name = scrub(p)
		try:
			page_controller = importlib.import_module(scrub(m) + ".page." +  page_name + "." + page_name)
			inspect_object_and_update_docs(mydocs, page_controller)
		except ImportError, e:
			pass

	return docs

def get_doctypes(m):
	doctypes = webnotes.conn.sql_list("""select name from 
		tabDocType where module=%s order by name""", m)
	prefix = "docs.dev.modules." + m + ".doctype."
	docs = {
		"_icon": "th",
		"_label": "DocTypes",
		"_toc": [prefix + d for d in doctypes]
	}
	
	for d in doctypes:
		meta = webnotes.get_doctype(d)
		meta_p = webnotes.get_doctype(d, True)
		doc_path = get_doc_path(m, "DocType", d)
		
		mydocs = docs[d] = {
			"_label": d,
			"_icon": meta[0].icon,
			"_type": "doctype",
			"_gh_source": get_gh_url(doc_path),
			"_toc": [
				prefix + d + ".model",
				prefix + d + ".permissions",
				prefix + d + ".controller_server"
			],
		}

		update_readme(mydocs, m, "DocType", d)

		# parents and links
		links, parents = [], []
		for df in webnotes.conn.sql("""select * from tabDocField where options=%s""", 
			d, as_dict=True):
			if df.parent:
				if df.fieldtype=="Table":
					parents.append(df.parent)
				if df.fieldtype=="Link":
					links.append(df.parent)
				
		if parents:
			mydocs["_intro"] += "\n\n#### Child Table Of:\n\n- " + "\n- ".join(list(set(parents))) + "\n\n"

		if links:
			mydocs["_intro"] += "\n\n#### Linked In:\n\n- " + "\n- ".join(list(set(links))) + "\n\n"
			
		if meta[0].issingle:
			mydocs["_intro"] += "\n\n#### Single DocType\n\nThere is no table for this DocType and the values of the Single instance are stored in `tabSingles`"

		# model
		modeldocs = mydocs["model"] = {
			"_label": d + " Model",
			"_icon": meta[0].icon,
			"_type": "model",
			"_intro": "Properties and fields for " + d,
			"_gh_source": get_gh_url(os.path.join(doc_path, scrub(d) + ".txt")),
			"_fields": [df.fields for df in meta.get({"doctype": "DocField"})],
			"_properties": meta[0].fields,
			"_modified": meta[0].modified
		}
		
		# permissions
		from webnotes.modules.utils import peval_doclist
		with open(os.path.join(doc_path, 
			scrub(d) + ".txt"), "r") as txtfile:
			doclist = peval_doclist(txtfile.read())
			
		permission_docs = mydocs["permissions"] = {
			"_label": d + " Permissions",
			"_type": "permissions",
			"_icon": meta[0].icon,
			"_gh_source": get_gh_url(os.path.join(doc_path, scrub(d) + ".txt")),
			"_intro": "Standard Permissions for " + d + ". These can be changed by the user.",
			"_permissions": [p for p in doclist if p.doctype=="DocPerm"],
			"_modified": doclist[0]["modified"]
		}
			
		# server controller
		server_controller_path = os.path.join(doc_path, scrub(d) + ".py")
		controller_docs = mydocs["controller_server"] = {
			"_label": d + " Server Controller",
			"_type": "_class",
			"_gh_source": get_gh_url(server_controller_path)
		}
		
		b = webnotes.bean([{"doctype": d}])
		b.make_controller()
		if not getattr(b.controller, "__doc__"):
			b.controller.__doc__ = "Controller Class for handling server-side events for " + d
		inspect_object_and_update_docs(controller_docs, b.controller)

		# client controller
		if meta_p[0].fields.get("__js"):
			client_controller_path = os.path.join(doc_path, scrub(d) + ".js")
			if(os.path.exists(client_controller_path)):
				mydocs["_toc"].append(prefix + d + ".controller_client")
				client_controller = mydocs["controller_client"] = {
					"_label": d + " Client Controller",
					"_icon": meta[0].icon,
					"_type": "controller_client",
					"_gh_source": get_gh_url(client_controller_path),
					"_modified": get_timestamp(client_controller_path),
					"_intro": "Client side triggers and functions for " + d,
					"_code": meta_p[0].fields["__js"],
					"_fields": [d.fieldname for d in meta_p if d.doctype=="DocField"]
				}

	return docs

def update_readme(mydocs, module, doctype=None, name=None):
	if doctype:
		readme_path = os.path.join(get_doc_path(module, doctype, name), "README.md")
	else:
		readme_path = os.path.join(get_module_path(module), "README.md")
	
	mydocs["_intro"] = ""
	
	if os.path.exists(readme_path):
		with open(readme_path, "r") as readmefile:
			mydocs["_intro"] = readmefile.read()
		mydocs["_modified"] = get_timestamp(readme_path)

def prepare_docs(force=False):
	os.chdir(get_path("public"))
	if not os.path.exists("docs"):
		os.mkdir("docs")
	
	if force:
		shutil.rmtree("docs/css")
	
	if not os.path.exists("docs/css"):
		os.mkdir("docs/css")
		os.mkdir("docs/css/font")
		os.system("cp ../lib/public/css/bootstrap.css docs/css")
		os.system("cp ../lib/public/css/font-awesome.css docs/css")
		os.system("cp ../lib/public/css/font/* docs/css/font")
		os.system("cp ../lib/public/css/prism.css docs/css")

		# clean links in font-awesome
		with open("docs/css/font-awesome.css", "r") as fontawesome:
			t = fontawesome.read()
			t = t.replace("../lib/css/", "")
		with open("docs/css/font-awesome.css", "w") as fontawesome:
			fontawesome.write(t)
	
	# copy latest docs.css	
	os.system("cp ../lib/core/doctype/documentation_tool/docs.css docs/css")
		

	if force:
		shutil.rmtree("docs/js")

	if not os.path.exists("docs/js"):
		os.mkdir("docs/js")
		os.system("cp ../lib/public/js/lib/bootstrap.min.js docs/js")
		os.system("cp ../lib/public/js/lib/jquery/jquery.min.js docs/js")
		os.system("cp ../lib/public/js/lib/prism.js docs/js")

	if force:
		os.remove("docs/img/splash.svg")

	if not os.path.exists("docs/img/splash.svg"):
		if not os.path.exists("docs/img"):
			os.mkdir("docs/img")
		os.system("cp ../app/public/images/splash.svg docs/img")

@webnotes.whitelist()
def write_docs(data, build_sitemap=None, domain=None):
	from webnotes.utils import global_date_format
	if webnotes.session.user != "Administrator":
		raise webnotes.PermissionError
		
	if isinstance(data, basestring):
		data = json.loads(data)

	template = webnotes.get_template("app/docs/templates/docs.html")

	data["index"] = data["docs"]
	data["docs"] = None
	for name, d in data.items():
		if d:
			if not d.get("title"):
				d["title"] = d["_label"]
			if d.get("_parent_page")=="docs.html":
				d["_parent_page"] = "index.html"
			if not d.get("_icon"):
				d["_icon"] = "icon-file-alt"
			if not d["_icon"].startswith("icon-"):
				d["_icon"] = "icon-" + d["_icon"]
			if d.get("_modified"):
				d["_modified"] = global_date_format(d["_modified"])

			with open(get_path("public", "docs", name + ".html"), "w") as docfile:
				if not d.get("description"):
					d["description"] = "Help pages for " + d["title"]
				html = template.render(d)
				docfile.write(html.encode("utf-8", errors="ignore"))
				
	if build_sitemap and domain:
		if not domain.endswith("/"):
			domain = domain + "/"
		content = ""
		for fname in os.listdir(get_path("public", "docs")):
			fname = cstr(fname)
			if fname.endswith(".html"):
				content += sitemap_link_xml % (domain + fname, 
					get_timestamp(get_path("public", "docs", fname)))
					
		with open(get_path("public", "docs", "sitemap.xml"), "w") as sitemap:
			sitemap.write(sitemap_frame_xml % content)

def write_static():
	webnotes.local.session = webnotes._dict({"user":"Administrator"})
	pages = prepare_static_pages()
	write_docs(pages)
	prepare_docs()
	
def prepare_static_pages():
	from markdown2 import markdown
	
	pages = get_static_pages()
	autogenerated_roots = ["docs.dev.framework.server", "docs.dev.framework.client",
		"docs.dev.modules"]

	# build toc
	for name, page in pages.items():
		if name in autogenerated_roots:
			del pages[name]
			continue
		
		# toc
		if page.get("_toc"):
			prev = None
			page["_toc_links"] = []
			for child in page["_toc"]:
				if child in pages:
					page["_toc_links"].append({
						"link": child + ".html",
						"label": pages[child]["_label"]
					})
					
					if not "_child_title" in page:
						page["_child_title"] = pages[child]["_label"]
						page["_child_page"] = child + ".html"
					
					pages[child]["_parent_title"] = page["_label"]
					pages[child]["_parent_page"] = name + ".html"

					if prev:
						prev["_next_title"] = pages[child]["_label"]
						prev["_next_page"] = child + ".html"
					
					prev = pages[child]
					
		# breadcrumbs
		if name!="docs":
			fullname = ""
			page["_breadcrumbs"] = []
			for p in name.split(".")[:-1]:
				fullname = fullname + (fullname and "." or "") + p
				page["_breadcrumbs"].append({
					"link": (fullname=="docs" and "index" or fullname) + ".html",
					"label": pages[fullname]["_label"]
				})
		
		page["content"] = markdown(page["_intro"])
		
	return pages
	
def get_timestamp(path):
	return datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
		
		
sitemap_frame_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s
</urlset>"""

sitemap_link_xml = """\n<url><loc>%s</loc><lastmod>%s</lastmod></url>"""

if __name__=="__main__":
	write_static()
	