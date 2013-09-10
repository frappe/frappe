# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

from __future__ import unicode_literals

import conf
import webnotes
import webnotes.utils

class PageNotFoundError(Exception): pass

def render(page_name):
	"""render html page"""
	try:
		html = render_page(page_name or "index")
	except PageNotFoundError:
		html = render_page("404")
	except Exception:
		html = render_page('error')
		

	from webnotes.handler import eprint, print_zip
	eprint("Content-Type: text/html; charset: utf-8")
	print_zip(html)

def render_page(page_name):
	"""get page html"""
	page_name = scrub_page_name(page_name)
	html = ''
	
	if page_name=="index":
		page_name = get_home_page()
	
	if not (hasattr(conf, 'auto_cache_clear') and conf.auto_cache_clear or 0):
		html = webnotes.cache().get_value("page:" + page_name)
		from_cache = True

	if not html:
		from webnotes.auth import HTTPRequest
		webnotes.http_request = HTTPRequest()
		
		html = build_page(page_name)
		from_cache = False
	
	if not html:
		raise PageNotFoundError

	if page_name=="error":
		html = html.replace("%(error)s", webnotes.getTraceback())
	else:
		comments = "\n\npage:"+page_name+\
			"\nload status: " + (from_cache and "cache" or "fresh")
		html += """\n<!-- %s -->""" % webnotes.utils.cstr(comments)

	return html

def build_page(page_name):
	from jinja2 import Environment, FileSystemLoader
	import os

	if not webnotes.conn:
		webnotes.connect()

	sitemap = webnotes.cache().get_value("website_sitemap", build_sitemap)
	page_options = sitemap.get(page_name)
	
	if not page_options:
		raise PageNotFoundError
	
	basepath = webnotes.utils.get_base_path()
	module = None
	no_cache = False
	
	if page_options.get("controller"):
		module = webnotes.get_module(page_options["controller"])
		no_cache = getattr(module, "no_cache", False)

	# if generator, then load bean, pass arguments
	if page_options.get("is_generator"):
		if not module:
			raise Exception("Generator controller not defined")
			
		name = webnotes.conn.get_value(module.doctype, {"page_name": page_name})
		obj = webnotes.get_obj(module.doctype, name, with_children=True)

		if hasattr(obj, 'get_context'):
			obj.get_context()

		context = webnotes._dict(obj.doc.fields)
		context["obj"] = obj
	else:
		# page
		context = webnotes._dict({ 'name': page_name })
		if module:
			context.update(module.get_context())
	
	context = update_context(context)
	jenv = Environment(loader = FileSystemLoader(basepath))
	context["base_template"] = jenv.get_template(webnotes.get_config().get("base_template"))
	
	template_name = page_options['template']	
	html = jenv.get_template(template_name).render(context)
	
	if not no_cache:
		webnotes.cache().set_value("page:" + page_name, html)
	return html
	
def build_sitemap():
	sitemap = {}
	config = webnotes.cache().get_value("website_sitemap_config", build_website_sitemap_config)
 	sitemap.update(config["pages"])

	# generators
	for g in config["generators"].values():
		g["is_generator"] = True
		module = webnotes.get_module(g["controller"])
		doctype = module.doctype
		for name in webnotes.conn.sql_list("""select page_name from `tab%s` where 
			ifnull(%s, 0)=1""" % (module.doctype, module.condition_field)):
			sitemap[name] = g
		
	return sitemap
	
def get_home_page():
	if not webnotes.conn:
		webnotes.connect()
	doc_name = webnotes.conn.get_value('Website Settings', None, 'home_page')
	if doc_name:
		page_name = webnotes.conn.get_value('Web Page', doc_name, 'page_name')
	else:
		page_name = 'login'

	return page_name

def update_context(context):
	try:
		from startup.webutils import update_template_args
		context = update_template_args(page_name, context)
	except ImportError:
		pass

	return context
		
def build_website_sitemap_config():
	import os, json
	
	config = {"pages": {}, "generators":{}}
	basepath = webnotes.utils.get_base_path()
	
	def get_options(path, fname):
		name = fname[:-5]
		options = webnotes._dict({
			"link_name": name,
			"template": os.path.relpath(os.path.join(path, fname), basepath),
		})
		controller_path = os.path.join(path, name + ".py")
		if os.path.exists(controller_path):
			options.controller = os.path.relpath(controller_path[:-3], basepath).replace(os.path.sep, ".")
			options.controller = ".".join(options.controller.split(".")[1:])

		return options
	
	for path, folders, files in os.walk(basepath):
		if os.path.basename(path)=="pages" and os.path.basename(os.path.dirname(path))=="templates":
			for fname in files:
				if fname.endswith(".html"):
					options = get_options(path, fname)
					config["pages"][options.link_name] = options

		if os.path.basename(path)=="generators" and os.path.basename(os.path.dirname(path))=="templates":
			for fname in files:
				if fname.endswith(".html"):
					options = get_options(path, fname)
					config["generators"][fname] = options
		
	return config



def clear_cache(page_name=None):
	if page_name:
		delete_page_cache(page_name)
	else:
		cache = webnotes.cache()
		for p in get_all_pages():
			cache.delete_value("page:" + p)

def get_all_pages():
	return webnotes.cache().get_value("website_sitemap", build_sitemap).keys()

def delete_page_cache(page_name):
	if page_name:
		webnotes.cache().delete_value("page:" + page_name)
			
def get_hex_shade(color, percent):
	def p(c):
		v = int(c, 16) + int(int('ff', 16) * (float(percent)/100))
		if v < 0: 
			v=0
		if v > 255: 
			v=255
		h = hex(v)[2:]
		if len(h) < 2:
			h = "0" + h
		return h
		
	r, g, b = color[0:2], color[2:4], color[4:6]
	
	avg = (float(int(r, 16) + int(g, 16) + int(b, 16)) / 3)
	# switch dark and light shades
	if avg > 128:
		percent = -percent

	# stronger diff for darker shades
	if percent < 25 and avg < 64:
		percent = percent * 2
	
	return p(r) + p(g) + p(b)

def scrub_page_name(page_name):
	if page_name.endswith('.html'):
		page_name = page_name[:-5]

	return page_name
			
def get_portal_links():
	portal_args = {}
	for page, opts in webnotes.get_config()["web"]["pages"].items():
		if opts.get("portal"):
			portal_args[opts["portal"]["doctype"]] = {
				"page": page,
				"conditions": opts["portal"].get("conditions")
			}
	
	return portal_args

_is_portal_enabled = None
def is_portal_enabled():
	global _is_portal_enabled
	if _is_portal_enabled is None:
		_is_portal_enabled = True
		if webnotes.utils.cint(webnotes.conn.get_value("Website Settings", 
			"Website Settings", "disable_signup")):
				_is_portal_enabled = False
		
	return _is_portal_enabled

def update_page_name(doc, title):
	"""set page_name and check if it is unique"""
	webnotes.conn.set(doc, "page_name", page_name(title))
	
	if doc.page_name in get_all_pages():
		webnotes.conn.sql("""Page Name cannot be one of %s""" % ', '.join(get_standard_pages()))
	
	res = webnotes.conn.sql("""\
		select count(*) from `tab%s`
		where page_name=%s and name!=%s""" % (doc.doctype, '%s', '%s'),
		(doc.page_name, doc.name))
	if res and res[0][0] > 0:
		webnotes.msgprint("""A %s with the same title already exists.
			Please change the title of %s and save again."""
			% (doc.doctype, doc.name), raise_exception=1)

	delete_page_cache(doc.page_name)

def page_name(title):
	"""make page name from title"""
	import re
	name = title.lower()
	name = re.sub('[~!@#$%^&*()<>,."\']', '', name)
	name = re.sub('[:/]', '-', name)

	name = '-'.join(name.split())

	# replace repeating hyphens
	name = re.sub(r"(-)\1+", r"\1", name)
	
	return name
