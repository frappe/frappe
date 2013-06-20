# For license information, please see license.txt

from __future__ import unicode_literals
		
import webnotes
import inspect, importlib, os, json
from jinja2 import Template
from webnotes.modules import get_doc_path, get_module_path, scrub

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
		for path, folders, files in os.walk(os.path.join("..", repo)):
			if os.path.basename(path)=="docs":
				# docs folder
				for fname in files:
					if fname.endswith(".md"):
						fpath = os.path.join("..", repo, "docs", fname)
						with open(fpath, "r") as docfile:
							src = unicode(docfile.read(), "utf-8")
							temp, headers, body = src.split("---", 2)
							d = json.loads(headers)
							d["_intro"] = body
							d["_gh_source"] = get_gh_url(fpath)
							mydocs[fname[:-3]] = d

	return mydocs

def get_docs_for(docs, name):
	"""build docs for python module"""
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
		mydocs["_type"] = "module"
		mydocs["_gh_source"] = get_gh_url(obj.__file__)
	else:
		mydocs["_type"] = "class"
		mydocs["_gh_source"] = get_gh_url(inspect.getmodule(obj).__file__)
		
	if not mydocs.get("_intro"):
		mydocs["_intro"] = getattr(obj, "__doc__", "")
	
	for name in dir(obj):
		try:
			value = getattr(obj, name)
		except AttributeError, e:
			value = None
			
		if value:
			if inspect.ismethod(value) or (inspect.isfunction(value) and inspect.getmodule(value)==obj):
				mydocs[name] = {
					"_type": "function",
					"_args": inspect.getargspec(value)[0],
					"_help": getattr(value, "__doc__", ""),
					"_source": inspect.getsource(value)
				}
				
def get_gh_url(path):
	sep = "/lib/" if "/lib/" in path else "/app/"
	url = gh_prefix \
		+ ("wnframework" if sep=="/lib/" else "erpnext") \
		+ ("/blob" if "." in path else "/tree") \
		+"/master/" + path.split(sep)[1]
	if url.endswith(".pyc"):
		url = url[:-1]
	return url

def get_modules(for_module=None):
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
			"_label": m,
			"_toc": [
				prefix + ".doctype",
				prefix + ".page",
				prefix + ".report",
				prefix + ".py_modules"
			],
			"doctype": get_doctypes(m),
			"page": get_pages(m),
			#"report": {},
			"py_modules": {
				"_label": "Independant Python Modules for " + m,
				"_toc": []
			}
		}
		
		# add stand alone modules
		module_path = get_module_path(m)
		prefix = prefix + ".py_modules."
		for basepath, folders, files in os.walk(module_path):
			for f in files:
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
					
					module_docs["_label"] = module_name
					module_docs["_function_namespace"] = module_name
				
		docs[m]["_intro"] = get_readme(m)
		docs[m]["_gh_docs"] = get_gh_url(module_path)
		
	return docs

def get_pages(m):
	pages = webnotes.conn.sql_list("""select name from tabPage where module=%s""", m)
	prefix = "docs.dev.modules." + m + ".page."
	docs = {
		"_label": "Pages",
		"_toc": [prefix + d for d in pages]
	}
	for p in pages:
		page = webnotes.doc("Page", p)
		mydocs = docs[p] = {
			"_label": page.title or p,
			"_type": "page",
			"_intro": get_readme(m, "Page", p) or ""
		}

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
		"_label": "DocTypes",
		"_toc": [prefix + d for d in doctypes]
	}
	
	for d in doctypes:
		meta = webnotes.get_doctype(d)
		meta_p = webnotes.get_doctype(d, True)
		doc_path = get_doc_path(m, "DocType", d)
		
		mydocs = docs[d] = {
			"_label": d,
			"_type": "doctype",
			"_gh_source": get_gh_url(doc_path),
			"_toc": [
				prefix + d + ".model",
				prefix + d + ".permissions",
				prefix + d + ".controller_server"
			],
		}

		mydocs["_intro"] = get_readme(m, "DocType", d) or ""

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
			"_type": "model",
			"_intro": "Properties and fields for " + d,
			"_gh_source": get_gh_url(os.path.join(doc_path, scrub(d) + ".txt")),
			"_fields": [df.fields for df in meta.get({"doctype": "DocField"})],
			"_properties": meta[0].fields
		}
		
		# permissions
		from webnotes.modules.utils import peval_doclist
		with open(os.path.join(doc_path, 
			scrub(d) + ".txt"), "r") as txtfile:
			doclist = peval_doclist(txtfile.read())
			
		permission_docs = mydocs["permissions"] = {
			"_label": d + " Permissions",
			"_type": "permissions",
			"_gh_source": get_gh_url(os.path.join(doc_path, scrub(d) + ".txt")),
			"_intro": "Standard Permissions for " + d + ". These can be changed by the user.",
			"_permissions": [p for p in doclist if p.doctype=="DocPerm"]
		}
			
		# server controller
		controller_docs = mydocs["controller_server"] = {
			"_label": d + " Server Controller",
			"_type": "_class",
			"_gh_source": get_gh_url(os.path.join(doc_path, scrub(d) + ".py"))
		}
		
		
		b = webnotes.bean([{"doctype": d}])
		b.make_obj()
		if not getattr(b.obj, "__doc__"):
			b.obj.__doc__ = "Controller Class for handling server-side events for " + d
		inspect_object_and_update_docs(controller_docs, b.obj)

		# client controller
		if meta_p[0].fields.get("__js"):
			mydocs["_toc"].append(prefix + d + ".controller_client")
			client_controller = mydocs["controller_client"] = {
				"_label": d + " Client Controller",
				"_type": "controller_client",
				"_gh_source": get_gh_url(os.path.join(doc_path, scrub(d) + ".js")),
				"_intro": "Client side triggers and functions for " + d,
				"_code": meta_p[0].fields["__js"],
				"_fields": [d.fieldname for d in meta_p if d.doctype=="DocField"]
			}

	return docs

def get_readme(module, doctype=None, name=None):
	if doctype:
		readme_path = os.path.join(get_doc_path(module, doctype, name), "README.md")
	else:
		readme_path = os.path.join(get_module_path(module), "README.md")
		
	if os.path.exists(readme_path):
		with open(readme_path, "r") as readmefile:
			return readmefile.read()

def prepare_docs():
	if not os.path.exists("docs"):
		os.mkdir("docs")
	if not os.path.exists("docs/css"):
		os.mkdir("docs/css")
		os.mkdir("docs/css/fonts")
		os.system("cp ../lib/public/css/bootstrap.css docs/css")
		os.system("cp ../lib/public/css/font-awesome.css docs/css")
		os.system("cp ../lib/public/css/fonts/* docs/css/fonts")
		os.system("cp ../lib/public/css/prism.css docs/css")
		
	if not os.path.exists("docs/css/docs.css"):
		os.system("cp ../lib/core/doctype/documentation_tool/docs.css docs/css")
		
		# clean links in font-awesome
		with open("docs/css/font-awesome.css", "r") as fontawesome:
			t = fontawesome.read()
			t = t.replace("../lib/css/", "")
		with open("docs/css/font-awesome.css", "w") as fontawesome:
			fontawesome.write(t)

	if not os.path.exists("docs/js"):
		os.mkdir("docs/js")
		os.system("cp ../lib/public/js/lib/bootstrap.min.js docs/js")
		os.system("cp ../lib/public/js/lib/jquery/jquery.min.js docs/js")
		os.system("cp ../lib/public/js/lib/prism.js docs/js")

	if not os.path.exists("docs/img/splash.svg"):
		if not os.path.exists("docs/img"):
			os.mkdir("docs/img")
		os.system("cp ../app/public/images/splash.svg docs/img")

@webnotes.whitelist(allow_roles=["Administrator"])
def write_docs(data):
	data = json.loads(data)
	template = Template(docs_template)
	data["index"] = data["docs"]
	data["docs"] = None
	for name in data:
		if data[name]:
			with open(os.path.join("docs", name + ".html"), "w") as docfile:
				html = template.render({
					"title": data[name]["title"],
					"content": data[name]["content"],
					"description": data[name]["title"]
				})
				docfile.write(html.encode("utf-8", errors="ignore"))
			
docs_template = """
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>{{ title }}</title>
	<meta name="description" content="{{ description }}">	
	<meta name="generator" content="wnframework">
	<script type="text/javascript" src="js/jquery.min.js"></script>
	<script type="text/javascript" src="js/bootstrap.min.js"></script>
	<script type="text/javascript" src="js/prism.js"></script>
	<link type="text/css" rel="stylesheet" href="css/bootstrap.css">
	<link type="text/css" rel="stylesheet" href="css/font-awesome.css">
	<link type="text/css" rel="stylesheet" href="css/prism.css">
	<link type="text/css" rel="stylesheet" href="css/docs.css">
</head>
<body>
	<header>
		<div class="navbar navbar-fixed-top navbar-inverse">
			<div class="container">
				<button type="button" class="navbar-toggle" 
					data-toggle="collapse" data-target=".navbar-responsive-collapse">
					<span class="icon-bar"></span>
					<span class="icon-bar"></span>
					<span class="icon-bar"></span>
				</button>
				<a class="navbar-brand" href="index.html">
					<object data="img/splash.svg" class="erpnext-logo" 
						type="image/svg+xml"></object> erpnext</a>
				<div class="nav-collapse collapse navbar-responsive-collapse">
					<ul class="nav navbar-nav">
						<li><a href="docs.user.html">User</a></li>
						<li><a href="docs.dev.html">Developer</a></li>
						<li><a href="docs.download.html">Download</a></li>
						<li><a href="docs.community.html">Community</a></li>
						<li><a href="docs.blog.html">Blog</a></li>
					</ul>
				</div>
			</div>
		</div>
	</header>
	<div class="container" style=" margin-top: 70px;">
		<!-- div class="logo" style="margin-bottom: 15px; height: 71px;">
			<a href="docs.html">
				<img src="img/erpnext-2013.png" style="width: 71px; margin-top: -10px;" />
			</a>
			<span style="font-size: 37px; color: #888; display: inline-block; 
				margin-left: 8px;">erpnext</span>
		</div -->
		<div class="content row">
			<div class="col col-lg-12">
		{{ content }}
			</div>
		</div>
		<div class="clearfix"></div>
		<hr />
		<div class="footer text-muted" style="font-size: 90%;">
		&copy; Web Notes Technologies Pvt Ltd.<br>
		ERPNext is an open source project under the GNU/GPL License.
		</div>
		<p>&nbsp;</p>
	</div>
	<script type="text/javascript">
		$(document).ready(function() {
			$("[data-toggle]").on("click", function() {
				$("[data-target='"+ $(this).attr("data-toggle") +"']").toggle();
				return false;
			});
		});
		$(".dropdown-toggle").dropdown();
	</script>
	<!-- script type="text/javascript">
	  var _gaq = _gaq || [];
	  _gaq.push(['_setAccount', 'UA-8911157-9']);
	  _gaq.push(['_trackPageview']);
	  (function() {
	    var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
	    ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
	    var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
	  })();
	</script -->
</body>
</html>
"""
