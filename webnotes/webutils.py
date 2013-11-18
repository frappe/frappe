# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt

from __future__ import unicode_literals

from webnotes import conf
import webnotes
import json, os, time
from webnotes import _
import webnotes.utils
import mimetypes

class PageNotFoundError(Exception): pass

def render(page_name):
	"""render html page"""
	try:
		html = render_page(page_name or "index")
	except PageNotFoundError:
		html = render_page("404")
	except Exception:
		html = render_page("error")
	
	webnotes._response.data = html
	
def render_page(page_name):
	"""get page html"""
	set_content_type(page_name)
	
	if page_name.endswith('.html'):
		page_name = page_name[:-5]
	html = ''
		
	if not conf.auto_cache_clear:
		html = webnotes.cache().get_value("page:" + page_name)
		from_cache = True

	if not html:		
		html = build_page(page_name)
		from_cache = False
	
	if not html:
		raise PageNotFoundError

	if page_name=="error":
		html = html.replace("%(error)s", webnotes.getTraceback())
	elif "text/html" in webnotes._response.headers["Content-Type"]:
		comments = "\npage:"+page_name+\
			"\nload status: " + (from_cache and "cache" or "fresh")
		html += """\n<!-- %s -->""" % webnotes.utils.cstr(comments)

	return html
	
def set_content_type(page_name):
	webnotes._response.headers["Content-Type"] = "text/html; charset: utf-8"
	
	if "." in page_name and not page_name.endswith(".html"):
		content_type, encoding = mimetypes.guess_type(page_name)
		webnotes._response.headers["Content-Type"] = content_type

def build_page(page_name):
	if not webnotes.conn:
		webnotes.connect()


	sitemap_options = webnotes.doc("Website Sitemap", page_name).fields
	
	page_options = webnotes.doc("Website Sitemap Config", 
		sitemap_options.get("website_sitemap_config")).fields.update(sitemap_options)
		
	if not page_options:
		raise PageNotFoundError
	else:
		page_options["page_name"] = page_name
	
	basepath = webnotes.utils.get_base_path()
	no_cache = page_options.get("no_cache")
	

	# if generator, then load bean, pass arguments
	if page_options.get("page_or_generator")=="Generator":
		doctype = page_options.get("ref_doctype")
		obj = webnotes.get_obj(doctype, page_options["docname"], with_children=True)

		if hasattr(obj, 'get_context'):
			obj.get_context()

		context = webnotes._dict(obj.doc.fields)
		context["obj"] = obj
	else:
		# page
		context = webnotes._dict({ 'name': page_name })
		if page_options.get("controller"):
			module = webnotes.get_module(page_options.get("controller"))
			if module and hasattr(module, "get_context"):
				context.update(module.get_context())
	
	context.update(get_website_settings())

	jenv = webnotes.get_jenv()
	context["base_template"] = jenv.get_template(webnotes.get_config().get("base_template"))
	
	template_name = page_options['template_path']	
	html = jenv.get_template(template_name).render(context)
	
	if not no_cache:
		webnotes.cache().set_value("page:" + page_name, html)
	return html
	
def build_sitemap():	
	webnotes.conn.sql("""delete from `tabWebsite Sitemap Config`""")
	webnotes.conn.sql("""delete from `tabWebsite Sitemap`""")
	webnotes.conn.commit()
	build_website_sitemap_config()

	for config in webnotes.conn.sql("""select * from `tabWebsite Sitemap Config`""", as_dict=True):
		if config.page_or_generator == "Page":
			config.page_name = config.link_name
			add_to_sitemap(config)
		else:
			module = webnotes.get_module(config.controller)

			condition = ""
			if hasattr(module, "condition_field"):
				condition = " where ifnull(%s, 0)=1" % module.condition_field

			page_name_field = getattr(module, "page_name_field", "page_name")
			
			for name in webnotes.conn.sql_list("""select name from `tab%s` %s""" \
				% (module.doctype, condition)):
				webnotes.bean(module.doctype, name).run_method("on_update")

def add_to_sitemap(options):
	doc = webnotes.doc({"doctype":"Website Sitemap"})
	for key in ("page_name", "ref_doctype", "docname", "page_or_generator", "lastmod"):
		doc.fields[key] = options.get(key)
	doc.name = options.page_name
	doc.website_sitemap_config = options.link_name
	doc.insert()
	webnotes.conn.commit()
	
def get_home_page():
	if not webnotes.conn:
		webnotes.connect()
	doc_name = webnotes.conn.get_value('Website Settings', None, 'home_page')
	if doc_name:
		page_name = webnotes.conn.get_value('Web Page', doc_name, 'page_name')
	else:
		page_name = 'login'

	return page_name
		
def build_website_sitemap_config():		
	config = {"pages": {}, "generators":{}}
	basepath = webnotes.utils.get_base_path()
		
	for path, folders, files in os.walk(basepath, followlinks=True):
		if 'locale' in folders: 
			folders.remove('locale')

		# utility - remove pyc files
		for f in files:
			if f.decode("utf-8").endswith(".pyc"):
				os.remove(os.path.join(path, f))

		if os.path.basename(path)=="pages" and os.path.basename(os.path.dirname(path))=="templates":
			for fname in files:
				fname = webnotes.utils.cstr(fname)
				if fname.split(".")[-1] in ("html", "xml", "js", "css"):
					add_website_sitemap_config("Page", path, fname)

		if os.path.basename(path)=="generators" and os.path.basename(os.path.dirname(path))=="templates":
			for fname in files:
				if fname.endswith(".html"):
					add_website_sitemap_config("Generator", path, fname)
	
	webnotes.conn.commit()
		
def add_website_sitemap_config(page_or_generator, path, fname):
	basepath = webnotes.utils.get_base_path()
	name = fname
	if fname.endswith(".html"):
		name = fname[:-5]
	
	template_path = os.path.relpath(os.path.join(path, fname), basepath)
	
	options = webnotes._dict({
		"doctype": "Website Sitemap Config",
		"page_or_generator": page_or_generator,
		"link_name": name,
		"template_path": template_path,
		"lastmod": time.ctime(os.path.getmtime(template_path))
	})

	controller_name = fname.split(".")[0].replace("-", "_") + ".py"
	controller_path = os.path.join(path, controller_name)
	if os.path.exists(controller_path):
		options.controller = os.path.relpath(controller_path[:-3], basepath).replace(os.path.sep, ".")
		options.controller = ".".join(options.controller.split(".")[1:])

	if options.controller:
		module = webnotes.get_module(options.controller)
		options.no_cache = getattr(module, "no_cache", 0)
		options.no_sitemap = options.no_cache or getattr(module, "no_sitemap", 0)
		options.ref_doctype = getattr(module, "doctype", None)
		
	webnotes.doc(options).insert()

	return options
	

def get_website_settings():
	from webnotes.utils import get_request_site_address, encode, cint
	from urllib import quote
		
	all_top_items = webnotes.conn.sql("""\
		select * from `tabTop Bar Item`
		where parent='Website Settings' and parentfield='top_bar_items'
		order by idx asc""", as_dict=1)
	
	top_items = [d for d in all_top_items if not d['parent_label']]
	
	# attach child items to top bar
	for d in all_top_items:
		if d['parent_label']:
			for t in top_items:
				if t['label']==d['parent_label']:
					if not 'child_items' in t:
						t['child_items'] = []
					t['child_items'].append(d)
					break
					
	context = webnotes._dict({
		'top_bar_items': top_items,
		'footer_items': webnotes.conn.sql("""\
			select * from `tabTop Bar Item`
			where parent='Website Settings' and parentfield='footer_items'
			order by idx asc""", as_dict=1),
		"webnotes": webnotes,
		"utils": webnotes.utils,
		"post_login": [
			{"label": "Reset Password", "url": "update-password", "icon": "icon-key"},
			{"label": "Logout", "url": "/?cmd=web_logout", "icon": "icon-signout"}
		]
	})
		
	settings = webnotes.doc("Website Settings", "Website Settings")
	for k in ["banner_html", "brand_html", "copyright", "twitter_share_via",
		"favicon", "facebook_share", "google_plus_one", "twitter_share", "linked_in_share",
		"disable_signup"]:
		if k in settings.fields:
			context[k] = settings.fields.get(k)
			
	if settings.address:
		context["footer_address"] = settings.address

	for k in ["facebook_share", "google_plus_one", "twitter_share", "linked_in_share",
		"disable_signup"]:
		context[k] = cint(context.get(k) or 0)
	
	context.url = quote(str(get_request_site_address(full_address=True)), str(""))
	context.encoded_title = quote(encode(context.title or ""), str(""))
	
	try:
		import startup.webutils
		if hasattr(startup.webutils, "get_website_settings"):
			startup.webutils.get_website_settings(context)
	except:
		pass
	return context


def clear_cache(page_name=None):
	if page_name:
		delete_page_cache(page_name)
	else:
		cache = webnotes.cache()
		for p in webnotes.conn.sql_list("""select name from `tabWebsite Sitemap`"""):
			if p is not None:
				cache.delete_value("page:" + p)
		cache.delete_value("page:index")
		cache.delete_value("website_sitemap")
		cache.delete_value("website_sitemap_config")
		
def delete_page_cache(page_name):
	if page_name:
		cache = webnotes.cache()
		cache.delete_value("page:" + page_name)
		cache.delete_value("website_sitemap")
			
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

def is_signup_enabled():
	if getattr(webnotes.local, "is_signup_enabled", None) is None:
		webnotes.local.is_signup_enabled = True
		if webnotes.utils.cint(webnotes.conn.get_value("Website Settings", 
			"Website Settings", "disable_signup")):
				webnotes.local.is_signup_enabled = False
		
	return webnotes.local.is_signup_enabled

class WebsiteGenerator(object):
	def setup_generator(self):
		self._website_config = webnotes.conn.get_values("Website Sitemap Config", {"ref_doctype": self.doc.doctype}, "*")[0]
		self._website_module = webnotes.get_module(self._website_config.controller)
		
		self._page_name_field = getattr(self._website_module, "page_name_field", "page_name")
		self._condition_field = getattr(self._website_module, "condition_field", "")
		
	def on_update(self, page_name=None):
		self.setup_generator()
		if self._condition_field:
			if not self.doc.fields[self._condition_field]:
				remove_page(self.doc.fields[self._page_name_field])
				return

		if not page_name:
			new_page_name = cleanup_page_name(self.get_page_title() \
				if hasattr(self, "get_page_title") else (self.doc.title or self.doc.name))
			self.check_if_page_name_is_unique(new_page_name)
	
			remove_page(self.doc.page_name)
			add_generator_to_sitemap(self.doc.doctype, self.doc.name, new_page_name, self.doc.modified, 
				self._website_config, self._website_module)

			if self.doc.fields[self._page_name_field]!=new_page_name: 
				webnotes.conn.set(self.doc, self._page_name_field, new_page_name)	
		else:
			add_generator_to_sitemap(self.doc.doctype, self.doc.name, page_name, self.doc.modified, 
				self._website_config, self._website_module)
			
		delete_page_cache(self.doc.page_name)

	def check_if_page_name_is_unique(self, new_page_name):
		if webnotes.conn.sql("""select name from `tabWebsite Sitemap` where name=%s 
			and ref_doctype!=%s and docname!=%s""", (new_page_name, self.doc.doctype, self.doc.name)):
				webnotes.throw("%s: %s. %s: <b>%s<b>" % (new_page_name, _("Page already exists"),
					_("Please change the value"), title))
		
	def on_trash(self):
		self.setup_generator()
		remove_page(self.doc.fields[self._page_name_field])

def add_generator_to_sitemap(ref_doctype, docname, page_name, modified, config=None, module=None):
	if not config:
		config = webnotes.conn.get_values("Website Sitemap Config", {"ref_doctype": ref_doctype}, "*")[0]
	if not module:
		module = webnotes.get_module(config.controller)
	
	page_name_field = getattr(module, "page_name_field", "page_name")
		
	opts = config.copy()
	opts["page_name"] = page_name
	if page_name_field != "page_name":
		opts["page_name_field"] = page_name_field
	opts["docname"] = docname
	opts["lastmod"] = modified
	add_to_sitemap(opts)


def remove_page(page_name):
	if page_name:
		delete_page_cache(page_name)
		webnotes.conn.sql("delete from `tabWebsite Sitemap` where name=%s", page_name)	

def cleanup_page_name(title):
	"""make page name from title"""
	import re
	name = title.lower()
	name = re.sub('[~!@#$%^&*+()<>,."\']', '', name)
	name = re.sub('[:/]', '-', name)

	name = '-'.join(name.split())

	# replace repeating hyphens
	name = re.sub(r"(-)\1+", r"\1", name)
	
	return name
