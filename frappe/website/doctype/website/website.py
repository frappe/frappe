# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import get_request_site_address, encode
from frappe.model.document import Document
from six.moves.urllib.parse import quote
from frappe.website.router import resolve_route
from frappe.website.doctype.website_theme.website_theme import add_website_theme
from frappe.website.utils import get_website_name

class Website(Document):
	def validate(self):
		if not self.is_default:
			self.validate_previously_default()
			self.validate_hostnames()
		else:
			self.hostnames = []

		self.validate_top_bar_items()
		self.validate_footer_items()
		self.validate_home_page()

	def validate_hostnames(self):
		if not self.hostnames:
			frappe.msgprint(_('Warning: No hostnames were added to website.'))
			return

		for d in self.hostnames:
			existing = frappe.get_all('Website Hostname', fields='parent',
				filters={"hostname": d.hostname, "name": ("!=", d.name)})
			if existing:
				frappe.throw(_("Hostname {0} already exists in Website {1}").format(
					d.hostname, existing[0].get('parent')))

	def validate_previously_default(self):
			if frappe.db.get_value(self.doctype, self.name, 'is_default'):
				frappe.throw(_('At least one website must be default. \
					Please set another website as default first.'))

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
		if self.is_default:
			self.remove_default_from_other_sites()
		self.clear_cache()

	def remove_default_from_other_sites(self):
		for website in frappe.get_all('Website', 
			{'is_default': 1, 'name': ("!=", self.name)}):
			frappe.db.set_value('Website', website.name, 'is_default', 0)
			frappe.msgprint(_('Website {0} is no longer default, please add \
				hostnames for it.').format(
					'<strong>' + website.name + '</strong>'))
			

	def clear_cache(self):
		# make js and css
		# clear web cache (for menus!)
		frappe.clear_cache(user = 'Guest')

		from frappe.website.render import clear_cache
		clear_cache()

		# clears role based home pages
		frappe.clear_cache()

	def on_trash(self):
		if self.is_default:
			frappe.throw(_('Default Website cannot be deleted'))

def get_website_context():
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

	website = frappe.get_doc('Website', get_website_name())
	for k in ["banner_html", "brand_html", "copyright", "twitter_share_via",
		"facebook_share", "google_plus_one", "twitter_share", "linked_in_share",
		"disable_signup", "hide_footer_signup", "head_html", "title_prefix",
		"navbar_search"]:
		if hasattr(website, k):
			context[k] = website.get(k)

	if website.address:
		context["footer_address"] = website.address

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

	if website.favicon and website.favicon != "attach_files:":
		context["favicon"] = website.favicon

	return context

def get_items(parentfield):
	all_top_items = frappe.db.sql("""\
		select * from `tabTop Bar Item`
		where parent=%s and parentfield= %s
		order by idx asc""", (get_website_name(), parentfield), as_dict=1)

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

@frappe.whitelist(allow_guest=True)
def is_chat_enabled():
	return bool(frappe.db.get_value('Website', get_website_name(), 'chat_enable'))