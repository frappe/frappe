"""Documentation Generation"""
from __future__ import unicode_literals

import webnotes
import inspect, importlib, os
from jinja2 import Template
from webnotes.modules import get_doc_path, get_module_path, scrub

@webnotes.whitelist()
def get_docs():
	docs = {}
	get_docs_for(docs, "webnotes")
	docs["modules"] = get_modules()
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
							mydocs[fname[:-3]] = docfile.read()
	
	return mydocs

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
	
	inspect_object_and_update_docs(mydocs, obj)
	
	if mydocs["_toc"]:
		for name in mydocs["_toc"]:
			get_docs_for(mydocs, name)
	
	return mydocs

def inspect_object_and_update_docs(mydocs, obj):
	mydocs["_toc"] = getattr(obj, "_toc", "")
	mydocs["_type"] = "module" if inspect.ismodule(obj) else "class"
	if not mydocs.get("_intro"):
		mydocs["_intro"] = getattr(obj, "__doc__", "")
	
	for name in dir(obj):
		value = getattr(obj, name)
		if inspect.ismethod(value) or inspect.isfunction(value):
			mydocs[name] = {
				"_type": "function",
				"_args": inspect.getargspec(value)[0],
				"_help": getattr(value, "__doc__", "")
			}

def get_modules():
	# readme.md
	# _toc [doctypes, pages, reports]
	# in doctype
	docs = {
		"_label": "Modules"
	}
	modules = webnotes.conn.sql_list("select name from `tabModule Def` order by name limit 1")
	docs["_toc"] = ["docs.dev.modules." + d for d in modules]
	for m in modules:
		prefix = "docs.dev.modules." + m
		docs[m] = {
			"_label": m,
			"_toc": [
				prefix + ".doctype",
				prefix + ".page",
				prefix + ".report"
			],
			"doctype": get_doctypes(m),
			"page": get_pages(m),
			"report": {}
		}

		docs[m]["_intro"] = get_readme(m)

	return docs

def get_pages(m):
	pages = webnotes.conn.sql_list("""select name from tabPage where module=%s limit 1""", m)
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
		page_controller = importlib.import_module(scrub(m) + ".page." +  page_name + "." + page_name)
		inspect_object_and_update_docs(mydocs, page_controller)

	return docs

def get_doctypes(m):
	doctypes = webnotes.conn.sql_list("""select name from 
		tabDocType where module=%s order by name limit 1""", m)
	prefix = "docs.dev.modules." + m + ".doctype."
	docs = {
		"_label": "DocTypes",
		"_toc": [prefix + d for d in doctypes]
	}
	
	for d in doctypes:
		meta = webnotes.get_doctype(d)
		meta_p = webnotes.get_doctype(d, True)
			
		mydocs = docs[d] = {
			"_label": d,
			"_type": "doctype",
			"_toc": [
				prefix + d + ".model",
				prefix + d + ".permissions",
				prefix + d + ".controller_server",
				prefix + d + ".controller_client",
			]
		}

		mydocs["_intro"] = get_readme(m, "DocType", d) or ""

		# model
		modeldocs = mydocs["model"] = {
			"_label": d + " Model",
			"_type": "model",
			"_intro": "Properties and fields for " + d,
			"_fields": [df.fields for df in meta.get({"doctype": "DocField"})],
			"_properties": meta[0].fields
		}
		
		# permissions
		from webnotes.modules.utils import peval_doclist
		with open(os.path.join(get_doc_path(meta[0].module, "DocType", d), 
			scrub(d) + ".txt"), "r") as txtfile:
			doclist = peval_doclist(txtfile.read())
			
		permission_docs = mydocs["permissions"] = {
			"_label": d + " Permissions",
			"_type": "permissions",
			"_intro": "Standard Permissions for " + d + ". These can be changed by the user.",
			"_permissions": [p for p in doclist if p.doctype=="DocPerm"]
		}
			
		# server controller
		controller_docs = mydocs["controller_server"] = {
			"_label": d + " Server Controller",
			"_type": "_class",
		}
		
		
		b = webnotes.bean([{"doctype": d}])
		b.make_obj()
		if not getattr(b.obj, "__doc__"):
			b.obj.__doc__ = "Controller Class for handling server-side events for " + d
		inspect_object_and_update_docs(controller_docs, b.obj)
		
		# client controller
		client_controller = mydocs["controller_client"] = {
			"_label": d + " Client Controller",
			"_type": "controller_client",
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

@webnotes.whitelist()
def write_doc_file(name, html, title):
	if not os.path.exists("docs"):
		os.mkdir("docs")
	if not os.path.exists("docs/css"):
		os.mkdir("docs/css")
		os.mkdir("docs/css/fonts")
		os.system("cp ../lib/public/css/bootstrap.css docs/css")
		os.system("cp ../lib/public/css/font-awesome.css docs/css")
		os.system("cp ../lib/public/css/fonts/* docs/css/fonts")
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
		

	with open(os.path.join("docs", name + ".html"), "w") as docfile:
		html = Template(docs_template).render({
			"title": title,
			"content": html,
			"description": title
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
	<link type="text/css" rel="stylesheet" href="css/bootstrap.css">
	<link type="text/css" rel="stylesheet" href="css/font-awesome.css">
	<style>
		body {
			/*background-color: #FDFFF9;*/
		}
		
		body {
			font-family: Arial, Sans Serif;
			font-size: 16px;
			line-height: 25px;
			text-rendering: optimizeLegibility;
		}

		h1 {
			font-weight: bold;
		}
		
		h1, h2, h3, h4, .logo {
			font-family: Arial, Sans;
			font-weight: bold;
		}
		
		li {
			line-height: inherit;
		}
				
		.content img {
			border-radius: 5px;
		}

		blockquote {
			padding: 10px 0 10px 15px;
			margin: 0 0 20px;
			background-color: #FFFCED;
			border-left: 5px solid #fbeed5;
		}

		blockquote p {
		  margin-bottom: 0;
		  font-size: 16px;
		  font-weight: normal;
		  line-height: 1.25;
		}
		
	</style>
</head>
<body>
	<header>
		<div class="navbar navbar-fixed-top navbar-inverse">
			<div class="container">
				<button type="button" class="navbar-toggle" data-toggle="collapse" data-target=".navbar-responsive-collapse">
					<span class="icon-bar"></span>
					<span class="icon-bar"></span>
					<span class="icon-bar"></span>
				</button>
				<a class="navbar-brand" href="docs.html">Home</a>
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

if __name__=="__main__":
	webnotes.connect()
	#print get_docs()
	print get_static_pages()
