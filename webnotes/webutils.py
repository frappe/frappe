# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
import json, os, time
from webnotes import _
import webnotes.utils
from webnotes.utils import get_request_site_address, encode, cint
from webnotes.model import default_fields
from webnotes.model.controller import DocListController
from urllib import quote

import mimetypes
from webnotes.website.doctype.website_sitemap.website_sitemap import add_to_sitemap, update_sitemap, remove_sitemap
from webnotes.website.doctype.website_sitemap_permission.website_sitemap_permission \
	import get_access

class PageNotFoundError(Exception): pass

def render(page_name):
	"""render html page"""
	page_name = scrub_page_name(page_name)
	
	try:
		data = render_page(page_name)
	except Exception:
		page_name = "error"
		data = render_page(page_name)
		data = insert_traceback(data)
	
	data = set_content_type(data, page_name)
	webnotes._response.data = data
	webnotes._response.headers["Page Name"] = page_name
	
def render_page(page_name):
	"""get page html"""
	cache_key = ("page_context:{}" if is_ajax() else "page:{}").format(page_name)

	out = None
	
	# try memcache
	if can_cache():
		out = webnotes.cache().get_value(cache_key)
		if is_ajax():
			out = out.get("data")
			
	if out:
		webnotes._response.headers["From Cache"] = True
		return out
	
	return build(page_name)
	
def build(page_name):
	if not webnotes.conn:
		webnotes.connect()
	
	build_method = (build_json if is_ajax() else build_page)
	try:
		return build_method(page_name)

	except webnotes.DoesNotExistError:
		hooks = webnotes.get_hooks()
		if hooks.website_catch_all:
			return build_method(hooks.website_catch_all[0])
		else:
			return build_method("404")
	
def build_json(page_name):
	return get_context(page_name).data
	
def build_page(page_name):
	context = get_context(page_name)
	
	html = webnotes.get_template(context.base_template_path).render(context)
	
	if can_cache(context.no_cache):
		webnotes.cache().set_value("page:" + page_name, html)
	
	return html

def get_context(page_name):
	context = None
	cache_key = "page_context:{}".format(page_name)
	
	# try from memcache
	if can_cache():
		context = webnotes.cache().get_value(cache_key)
	
	if not context:
		sitemap_options = get_sitemap_options(page_name)
		context = build_context(sitemap_options)
		if can_cache(context.no_cache):
			webnotes.cache().set_value(cache_key, context)

	context.update(context.data or {})
	return context
	
def get_sitemap_options(page_name):
	sitemap_options = None
	cache_key = "sitemap_options:{}".format(page_name)

	if can_cache():
		sitemap_options = webnotes.cache().get_value(cache_key)
	if sitemap_options:
		return sitemap_options
		
	sitemap_options = build_sitemap_options(page_name)
	if can_cache(sitemap_options.no_cache):
		webnotes.cache().set_value(cache_key, sitemap_options)
		
	return sitemap_options
	
def build_sitemap_options(page_name):
	sitemap_options = webnotes.doc("Website Sitemap", page_name).fields
	
	# only non default fields
	for fieldname in default_fields:
		if fieldname in sitemap_options:
			del sitemap_options[fieldname]
	
	sitemap_config = webnotes.doc("Website Sitemap Config", 
		sitemap_options.get("website_sitemap_config")).fields
	
	# get sitemap config fields too
	for fieldname in ("base_template_path", "template_path", "controller", "no_cache", "no_sitemap", 
		"page_name_field", "condition_field"):
		sitemap_options[fieldname] = sitemap_config.get(fieldname)
	
	# establish hierarchy
	sitemap_options.parents = webnotes.conn.sql("""select name, page_title from `tabWebsite Sitemap`
		where lft < %s and rgt > %s order by lft asc""", (sitemap_options.lft, sitemap_options.rgt), as_dict=True)

	sitemap_options.children = webnotes.conn.sql("""select * from `tabWebsite Sitemap`
		where parent_website_sitemap=%s""", (sitemap_options.page_name,), as_dict=True)
	
	# determine templates to be used
	if not sitemap_options.base_template_path:
		sitemap_options.base_template_path = "templates/base.html"
		
	sitemap_options.template = webnotes.get_jenv().get_template(sitemap_options.template_path)
	
	return sitemap_options
	
def build_context(sitemap_options):
	"""get_context method of bean or module is supposed to render content templates and push it into context"""
	context = webnotes._dict({ "_": webnotes._ })
	context.update(sitemap_options)
	context.update(get_website_settings())
	
	if sitemap_options.get("controller"):
		module = webnotes.get_module(sitemap_options.get("controller"))
		if module and hasattr(module, "get_context"):
			context.data = module.get_context(context) or {}
			
	return context
	
def can_cache(no_cache=False):
	return not (webnotes.conf.disable_website_cache or no_cache)
	
def get_home_page():
	return webnotes.cache().get_value("home_page", \
		lambda: webnotes.conn.get_value("Website Settings", None, "home_page") or "login")
	
def get_website_settings():
	# TODO Cache this
	hooks = webnotes.get_hooks()
	
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
			{"label": "Logout", "url": "?cmd=web_logout", "icon": "icon-signout"}
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
	
	context.url = quote(str(get_request_site_address(full_address=True)), safe="/:")
	context.encoded_title = quote(encode(context.title or ""), str(""))
	
	for update_website_context in hooks.update_website_context or []:
		webnotes.get_attr(update_website_context)(context)
		
	context.web_include_js = hooks.web_include_js or []
	context.web_include_css = hooks.web_include_css or []
	
	# get settings from site config
	if webnotes.conf.get("fb_app_id"):
		context.fb_app_id = webnotes.conf.fb_app_id
	
	return context
	
def is_ajax():
	return webnotes.get_request_header("X-Requested-With")=="XMLHttpRequest"
	
def scrub_page_name(page_name):
	if not page_name:
		page_name = "index"
	
	if "/" in page_name:
		page_name = page_name.split("/")[0]
		
	if page_name.endswith('.html'):
		page_name = page_name[:-5]
		
	if page_name == "index":
		page_name = get_home_page()
		
	return page_name

def insert_traceback(data):
	traceback = webnotes.get_traceback()
	if isinstance(data, dict):
		data["error"] = traceback
	else:
		data = data % {"error": traceback}
		
	return data
	
def set_content_type(data, page_name):
	if isinstance(data, dict):
		webnotes._response.headers["Content-Type"] = "application/json; charset: utf-8"
		data = json.dumps(data)
		return data
	
	webnotes._response.headers["Content-Type"] = "text/html; charset: utf-8"
	
	if "." in page_name and not page_name.endswith(".html"):
		content_type, encoding = mimetypes.guess_type(page_name)
		webnotes._response.headers["Content-Type"] = content_type
	
	return data

def clear_cache(page_name=None):
	if page_name:
		delete_page_cache(page_name)
	else:
		cache = webnotes.cache()
		for p in webnotes.conn.sql_list("""select name from `tabWebsite Sitemap`"""):
			if p is not None:
				cache.delete_value("page:" + p)
		cache.delete_value("home_page")
		cache.delete_value("page:index")
		cache.delete_value("website_sitemap")
		cache.delete_value("website_sitemap_config")
		
def delete_page_cache(page_name):
	if page_name:
		cache = webnotes.cache()
		cache.delete_value("page:" + page_name)
		cache.delete_value("website_sitemap")
			
def is_signup_enabled():
	if getattr(webnotes.local, "is_signup_enabled", None) is None:
		webnotes.local.is_signup_enabled = True
		if webnotes.utils.cint(webnotes.conn.get_value("Website Settings", 
			"Website Settings", "disable_signup")):
				webnotes.local.is_signup_enabled = False
		
	return webnotes.local.is_signup_enabled
	
def call_website_generator(bean, method):
	getattr(WebsiteGenerator(bean.doc, bean.doclist), method)()
	
class WebsiteGenerator(DocListController):
	def setup_generator(self):
		if webnotes.flags.in_install_app:
			return
		self._website_config = webnotes.conn.get_values("Website Sitemap Config", 
			{"ref_doctype": self.doc.doctype}, "*")[0]
			
	def on_update(self):
		self.update_sitemap()
		
	def after_rename(self, olddn, newdn, merge):
		webnotes.conn.sql("""update `tabWebsite Sitemap`
			set docname=%s where ref_doctype=%s and docname=%s""", (newdn, self.doc.doctype, olddn))
		
		if merge:
			self.setup_generator()
			remove_sitemap(ref_doctype=self.doc.doctype, docname=olddn)
		
	def on_trash(self):
		self.setup_generator()
		remove_sitemap(ref_doctype=self.doc.doctype, docname=self.doc.name)
		
	def update_sitemap(self):
		if webnotes.flags.in_install_app:
			return
		
		self.setup_generator()
		
		if self._website_config.condition_field and \
			not self.doc.fields.get(self._website_config.condition_field):
			# condition field failed, remove and return!
			remove_sitemap(ref_doctype=self.doc.doctype, docname=self.doc.name)
			return
				
		self.add_or_update_sitemap()
		
	def add_or_update_sitemap(self):
		page_name = self.get_page_name()
		
		existing_page_name = webnotes.conn.get_value("Website Sitemap", {"ref_doctype": self.doc.doctype,
			"docname": self.doc.name})
			
		opts = webnotes._dict({
			"page_or_generator": "Generator",
			"ref_doctype":self.doc.doctype, 
			"docname": self.doc.name,
			"page_name": page_name,
			"link_name": self._website_config.name,
			"lastmod": webnotes.utils.get_datetime(self.doc.modified).strftime("%Y-%m-%d"),
			"parent_website_sitemap": self.doc.parent_website_sitemap,
			"page_title": self.get_page_title() \
				if hasattr(self, "get_page_title") else (self.doc.title or self.doc.name)
		})
		
		if self.meta.get_field("public_read"):
			opts.public_read = self.doc.public_read
			opts.public_write = self.doc.public_write
		else:
			opts.public_read = 1
			
		if existing_page_name:
			if existing_page_name != page_name:
				webnotes.rename_doc("Website Sitemap", existing_page_name, page_name, ignore_permissions=True)
			update_sitemap(page_name, opts)
		else:
			add_to_sitemap(opts)
		
	def get_page_name(self):
		if not self.doc.fields.get(self._website_config.page_name_field):
			new_page_name = cleanup_page_name(self.get_page_title() \
				if hasattr(self, "get_page_title") else (self.doc.title or self.doc.name))
	
			webnotes.conn.set(self.doc, self._website_config.page_name_field, new_page_name)
			
		return self.doc.fields.get(self._website_config.page_name_field)
		
def cleanup_page_name(title):
	"""make page name from title"""
	import re
	name = title.lower()
	name = re.sub('[~!@#$%^&*+()<>,."\'\?]', '', name)
	name = re.sub('[:/]', '-', name)

	name = '-'.join(name.split())

	# replace repeating hyphens
	name = re.sub(r"(-)\1+", r"\1", name)
	
	return name

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

def render_blocks(context):
	"""returns a dict of block name and its rendered content"""
	from jinja2.utils import concat
	out = {}
	template = context["template"]
	
	# required as per low level API
	context = template.new_context(context)
	
	# render each block individually
	for block, render in template.blocks.items():
		out[block] = concat(render(context))

	return out
