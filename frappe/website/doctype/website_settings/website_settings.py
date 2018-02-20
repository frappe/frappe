# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import get_request_site_address, encode
from frappe.model.document import Document
from six.moves.urllib.parse import quote
from frappe.website.router import resolve_route
from frappe.website.doctype.website_theme.website_theme import add_website_theme

class WebsiteSettings(Document):
	def validate(self):
		self.validate_top_bar_items()
		self.validate_footer_items()
		self.validate_home_page()

	def validate_home_page(self):
		if frappe.flags.in_install:
			return
		if self.home_page and not resolve_route(self.home_page):
			frappe.msgprint(_("Invalid Home Page") + " (Standard pages - index, login, products, blog, about, contact)")
			self.home_page = ''

	def validate_top_bar_items(self):
		"""validate url in top bar items"""
		for top_bar_item in self.get("top_bar_items"):
			if top_bar_item.parent_label:
				parent_label_item = self.get("top_bar_items", {"label": top_bar_item.parent_label})

				if not parent_label_item:
					# invalid item
					frappe.throw(_("{0} does not exist in row {1}").format(top_bar_item.parent_label, top_bar_item.idx))

				elif not parent_label_item[0] or parent_label_item[0].url:
					# parent cannot have url
					frappe.throw(_("{0} in row {1} cannot have both URL and child items").format(top_bar_item.parent_label,
						top_bar_item.idx))

	def validate_footer_items(self):
		"""validate url in top bar items"""
		for footer_item in self.get("footer_items"):
			if footer_item.parent_label:
				parent_label_item = self.get("footer_items", {"label": footer_item.parent_label})

				if not parent_label_item:
					# invalid item
					frappe.throw(_("{0} does not exist in row {1}").format(footer_item.parent_label, footer_item.idx))

				elif not parent_label_item[0] or parent_label_item[0].url:
					# parent cannot have url
					frappe.throw(_("{0} in row {1} cannot have both URL and child items").format(footer_item.parent_label,
						footer_item.idx))

	def on_update(self):
		self.clear_cache()

	def clear_cache(self):
		# make js and css
		# clear web cache (for menus!)
		from frappe.sessions import clear_cache
		clear_cache('Guest')

		from frappe.website.render import clear_cache
		clear_cache()

		# clears role based home pages
		frappe.clear_cache()

def get_website_settings():
	hooks = frappe.get_hooks()
	context = frappe._dict({
		'top_bar_items': get_items('top_bar_items'),
		'footer_items': get_items('footer_items'),
		"post_login": [
			{"label": _("My Account"), "url": "/me"},
#			{"class": "divider"},
			{"label": _("Logout"), "url": "/?cmd=web_logout"}
		]
	})

	settings = frappe.get_single("Website Settings")
	for k in ["banner_html", "brand_html", "copyright", "twitter_share_via",
		"facebook_share", "google_plus_one", "twitter_share", "linked_in_share",
		"disable_signup", "hide_footer_signup", "head_html", "title_prefix",
		"navbar_search"]:
		if hasattr(settings, k):
			context[k] = settings.get(k)

	if settings.address:
		context["footer_address"] = settings.address

	for k in ["facebook_share", "google_plus_one", "twitter_share", "linked_in_share",
		"disable_signup"]:
		context[k] = int(context.get(k) or 0)

	if frappe.request:
		context.url = quote(str(get_request_site_address(full_address=True)), safe="/:")

	context.encoded_title = quote(encode(context.title or ""), str(""))

	for update_website_context in hooks.update_website_context or []:
		frappe.get_attr(update_website_context)(context)

	context.web_include_js = hooks.web_include_js or []

	context.web_include_css = hooks.web_include_css or []

	via_hooks = frappe.get_hooks("website_context")
	for key in via_hooks:
		context[key] = via_hooks[key]
		if key not in ("top_bar_items", "footer_items", "post_login") \
			and isinstance(context[key], (list, tuple)):
			context[key] = context[key][-1]

	add_website_theme(context)

	if not context.get("favicon"):
		context["favicon"] = "/assets/frappe/images/favicon.png"

	if settings.favicon and settings.favicon != "attach_files:":
		context["favicon"] = settings.favicon

	return context

def get_items(parentfield):
	all_top_items = frappe.db.sql("""\
		select * from `tabTop Bar Item`
		where parent='Website Settings' and parentfield= %s
		order by idx asc""", parentfield, as_dict=1)

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
	return top_items

