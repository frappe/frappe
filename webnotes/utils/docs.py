"""Documentation Generation"""
from __future__ import unicode_literals

import webnotes
import inspect, importlib, os
from jinja2 import Template
from webnotes.modules import get_doc_path, get_module_path

@webnotes.whitelist()
def get_docs():
	docs = {}
	get_docs_for(docs, "webnotes")
	docs["modules"] = get_modules()
	docs["pages"] = get_pages()
	return docs

def get_pages():
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
			"page": {},
			"report": {}
		}

		readme_path = os.path.join(get_module_path(m), "README.md")
		if os.path.exists(readme_path):
			with open(readme_path, "r") as readmefile:
				docs[m]["_intro"] = readmefile.read()

	return docs

def get_doctypes(m):
	doctypes = webnotes.conn.sql_list("""select name from 
		tabDocType where module=%s order by name limit 1""", m)
	docs = {
		"_label": "DocTypes for " + m,
		"_toc": ["docs.dev.modules." + m + ".doctype." + d for d in doctypes]
	}
	
	for d in doctypes:
		try:
			meta = webnotes.get_doctype(d)
				
			mydocs = docs[d] = {
				"_label": d,
				"_type": "doctype"
			}

			readme_path = os.path.join(get_doc_path(m, "DocType", d), "README.md")
			if os.path.exists(readme_path):
				with open(readme_path, "r") as readmefile:
					mydocs["_intro"] = readmefile.read()

			for df in meta.get({"doctype": "DocField"}):
				df = df.fields
				df["_type"] = "docfield"
				mydocs[df.fieldname] = df
		except Exception, e:
			pass
			
	return docs

@webnotes.whitelist()
def write_doc_file(name, html, title):
	if not os.path.exists("docs"):
		os.mkdir("docs")
		os.mkdir("docs/css")
		os.mkdir("docs/css/fonts")
		os.mkdir("docs/js")
		os.system("cp ../lib/public/js/lib/bootstrap.min.js docs/js")
		os.system("cp ../lib/public/js/lib/jquery/jquery.min.js docs/js")
		os.system("cp ../lib/public/css/bootstrap.css docs/css")
		os.system("cp ../lib/public/css/font-awesome.css docs/css")
		os.system("cp ../lib/public/css/fonts/* docs/css/fonts")
		
		# clean links in font-awesome
		with open("docs/css/font-awesome.css", "r") as fontawesome:
			t = fontawesome.read()
			t = t.replace("../lib/css/", "")
		with open("docs/css/font-awesome.css", "w") as fontawesome:
			fontawesome.write(t)
	
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
			background-color: #FDFFF9;
		}
		
		body {
			font-family: Georgia, Serif;
			font-size: 16px;
			line-height: 25px;
			text-rendering: optimizeLegibility;
		}

		h1 {
			font-weight: bold;
		}
		
		h1, h2, h3, h4, .logo {
			font-family: Helvetica Neue, Arial, Sans;
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
	<div class="container" style="max-width: 767px; margin-top: 30px;">
	<div class="logo" style="margin-bottom: 15px; height: 71px;">
		<a href="docs.html">
			<img src="img/erpnext-2013.png" style="width: 71px; margin-top: -10px;" />
		</a>
		<span style="font-size: 37px; color: #888; display: inline-block; 
			margin-left: 8px;">erpnext</span>
	</div>
	<div class="navbar" style="background-color: #EDE6DA; margin-bottom: 30px;">
		<a class="navbar-brand" href="docs.html">Home</a>
		<ul class="nav navbar-nav">
			<li><a href="docs.user.html">User</a></li>
			<li><a href="docs.dev.html">Developer</a></li>
			<li><a href="docs.download.html">Download</a></li>
			<li><a href="docs.community.html">Community</a></li>
			<li><a href="docs.blog.html">Blog</a></li>
		</ul>
	</div>
	<div class="content">
	{{ content }}
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
	  $(".dropdown-toggle").dropdown();
	  var _gaq = _gaq || [];
	  _gaq.push(['_setAccount', 'UA-8911157-9']);
	  _gaq.push(['_trackPageview']);

	  (function() {
	    var ga = document.createElement('script'); ga.type = 'text/javascript'; ga.async = true;
	    ga.src = ('https:' == document.location.protocol ? 'https://ssl' : 'http://www') + '.google-analytics.com/ga.js';
	    var s = document.getElementsByTagName('script')[0]; s.parentNode.insertBefore(ga, s);
	  })();
	</script>
</body>
</html>
"""

if __name__=="__main__":
	webnotes.connect()
	#print get_docs()
	print get_pages()
