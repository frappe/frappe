# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import requests
import frappe
from frappe import _
from frappe.utils import get_request_site_address, encode
from frappe.model.document import Document
from six.moves.urllib.parse import quote
from frappe.website.router import resolve_route
from frappe.website.doctype.website_theme.website_theme import add_website_theme
from frappe.integrations.doctype.google_settings.google_settings import get_auth_url

INDEXING_SCOPES = "https://www.googleapis.com/auth/indexing"

class WebsiteSettings(Document):
	def validate(self):
		self.validate_top_bar_items()
		self.validate_footer_items()
		self.validate_home_page()
		self.validate_google_settings()

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

	def validate_google_settings(self):
		if self.enable_google_indexing and not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(_("Enable Google API in Google Settings."))

	def on_update(self):
		self.clear_cache()

	def clear_cache(self):
		# make js and css
		# clear web cache (for menus!)
		frappe.clear_cache(user = 'Guest')

		from frappe.website.render import clear_cache
		clear_cache()

		# clears role based home pages
		frappe.clear_cache()

	def get_access_token(self):
		google_settings = frappe.get_doc("Google Settings")

		if not google_settings.enable:
			frappe.throw(_("Google Integration is disabled."))

		if not self.indexing_refresh_token:
			button_label = frappe.bold(_("Allow API Indexing Access"))
			raise frappe.ValidationError(_("Click on {0} to generate Refresh Token.").format(button_label))

		data = {
			"client_id": google_settings.client_id,
			"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False),
			"refresh_token": self.get_password(fieldname="indexing_refresh_token", raise_exception=False),
			"grant_type": "refresh_token",
			"scope": INDEXING_SCOPES
		}

		try:
			res = requests.post(get_auth_url(), data=data).json()
		except requests.exceptions.HTTPError:
			button_label = frappe.bold(_("Allow Google Indexing Access"))
			frappe.throw(_("Something went wrong during the token generation. Click on {0} to generate a new one.").format(button_label))

		return res.get("access_token")


def get_website_settings(context=None):
	hooks = frappe.get_hooks()
	context = context or frappe._dict()
	context = context.update({
		'top_bar_items': get_items('top_bar_items'),
		'footer_items': get_items('footer_items'),
		"post_login": [
			{"label": _("My Account"), "url": "/me"},
			{"label": _("Logout"), "url": "/?cmd=web_logout"}
		]
	})

	settings = frappe.get_single("Website Settings")
	for k in ["banner_html", "banner_image", "brand_html", "copyright", "twitter_share_via",
		"facebook_share", "google_plus_one", "twitter_share", "linked_in_share",
		"disable_signup", "hide_footer_signup", "head_html", "title_prefix",
		"navbar_search", "enable_view_tracking", "footer_logo", "call_to_action", "call_to_action_url"]:
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

	context["hide_login"] = settings.hide_login

	return context

def get_items(parentfield):
	all_top_items = frappe.db.sql("""\
		select * from `tabTop Bar Item`
		where parent='Website Settings' and parentfield= %s
		order by idx asc""", parentfield, as_dict=1)

	top_items = all_top_items[:]

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
	return bool(frappe.db.get_single_value('Website Settings', 'chat_enable'))
