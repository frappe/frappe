from __future__ import unicode_literals

import os
import conf
from startup.website import *
import webnotes
import webnotes.utils

def render(page_name):
	"""render html page"""
	try:
		if page_name:
			html = get_html(page_name)
		else:
			html = get_html('index')
	except Exception:
		html = get_html('error')

	from webnotes.handler import eprint, print_zip
	eprint("Content-Type: text/html; charset: utf-8")
	print_zip(html)

def get_html(page_name):
	"""get page html"""
	page_name = scrub_page_name(page_name)
	
	html = ''
	
	# load from cache, if auto cache clear is falsy
	if not (hasattr(conf, 'auto_cache_clear') and conf.auto_cache_clear or 0):
		if not get_page_settings().get(page_name, {}).get("no_cache"):
			html = webnotes.cache().get_value("page:" + page_name)
			from_cache = True

	if not html:
		from webnotes.auth import HTTPRequest
		webnotes.http_request = HTTPRequest()
		
		#webnotes.connect()
		html = load_into_cache(page_name)
		from_cache = False
	
	if not html:
		html = get_html("404")

	if page_name=="error":
		html = html.replace("%(error)s", webnotes.getTraceback())
	else:
		comments = "\n\npage:"+page_name+\
			"\nload status: " + (from_cache and "cache" or "fresh")
		html += """\n<!-- %s -->""" % webnotes.utils.cstr(comments)

	return html
	
def scrub_page_name(page_name):
	if page_name.endswith('.html'):
		page_name = page_name[:-5]

	return page_name

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

def update_page_name(doc, title):
	"""set page_name and check if it is unique"""
	webnotes.conn.set(doc, "page_name", page_name(title))
	
	if doc.page_name in get_standard_pages():
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

def load_into_cache(page_name):
	args = prepare_args(page_name)
	if not args:
		return ""
	html = build_html(args)
	webnotes.cache().set_value("page:" + page_name, html)
	return html

def build_html(args):
	from jinja2 import Environment, FileSystemLoader

	args["len"] = len
	
	jenv = Environment(loader = FileSystemLoader(webnotes.utils.get_base_path()))
	template_name = args['template']
	if not template_name.endswith(".html"):
		template_name = template_name + ".html"
	html = jenv.get_template(template_name).render(args)
	
	return html
	
def get_standard_pages():
	return webnotes.get_config()["web"]["pages"].keys()
	
def prepare_args(page_name):
	if page_name == 'index':
		page_name = get_home_page()
	
	pages = get_page_settings()
	
	if page_name in pages:
		page_info = pages[page_name]
		args = webnotes._dict({
			'template': page_info["template"],
			'name': page_name,
		})

		# additional args
		if "args_method" in page_info:
			args.update(webnotes.get_method(page_info["args_method"])())
		elif "args_doctype" in page_info:
			args.obj = webnotes.bean(page_info["args_doctype"]).obj

	else:
		args = get_doc_fields(page_name)
	
	if not args:
		return False
	
	update_template_args(page_name, args)
	
	return args	

def get_doc_fields(page_name):
	doc_type, doc_name = get_source_doc(page_name)
	if not doc_type:
		return False
	
	obj = webnotes.get_obj(doc_type, doc_name, with_children=True)

	if hasattr(obj, 'prepare_template_args'):
		obj.prepare_template_args()

	args = obj.doc.fields
	args['template'] = get_generators()[doc_type]["template"]
	args['obj'] = obj
	args['int'] = int
	
	return args

def get_source_doc(page_name):
	"""get source doc for the given page name"""
	for doctype in get_generators():
		name = webnotes.conn.sql("""select name from `tab%s` where 
			page_name=%s and ifnull(%s, 0)=1""" % (doctype, "%s", 
			get_generators()[doctype]["condition_field"]), page_name)
		if name:
			return doctype, name[0][0]

	return None, None
		
def clear_cache(page_name=None):
	if page_name:
		delete_page_cache(page_name)
	else:
		cache = webnotes.cache()
		for p in get_all_pages():
			cache.delete_value("page:" + p)

def get_all_pages():
	all_pages = get_standard_pages()
	for doctype in get_generators():
		all_pages += [p[0] for p in webnotes.conn.sql("""select distinct page_name 
			from `tab%s`""" % doctype) if p[0]]

	return all_pages

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

def get_standard_pages():
	return webnotes.get_config()["web"]["pages"].keys()
	
def get_generators():
	return webnotes.get_config()["web"]["generators"]
	
def get_page_settings():
	return webnotes.get_config()["web"]["pages"]
	

