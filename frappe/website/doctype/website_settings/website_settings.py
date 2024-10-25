# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re
from urllib.parse import quote

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, encode, get_request_site_address
from frappe.website.utils import get_boot_data


class WebsiteSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from frappe.website.doctype.top_bar_item.top_bar_item import TopBarItem
		from frappe.website.doctype.website_route_redirect.website_route_redirect import (
			WebsiteRouteRedirect,
		)

		address: DF.SmallText | None
		app_logo: DF.AttachImage | None
		app_name: DF.Data | None
		auto_account_deletion: DF.Int
		banner_html: DF.Code | None
		banner_image: DF.AttachImage | None
		brand_html: DF.Code | None
		call_to_action: DF.Data | None
		call_to_action_url: DF.Data | None
		copyright: DF.Data | None
		disable_signup: DF.Check
		enable_google_indexing: DF.Check
		enable_view_tracking: DF.Check
		favicon: DF.Attach | None
		footer_items: DF.Table[TopBarItem]
		footer_logo: DF.AttachImage | None
		footer_powered: DF.SmallText | None
		footer_template: DF.Link | None
		footer_template_values: DF.Code | None
		google_analytics_anonymize_ip: DF.Check
		google_analytics_id: DF.Data | None
		head_html: DF.Code | None
		hide_footer_signup: DF.Check
		hide_login: DF.Check
		home_page: DF.Data | None
		indexing_authorization_code: DF.Data | None
		indexing_refresh_token: DF.Data | None
		navbar_search: DF.Check
		navbar_template: DF.Link | None
		navbar_template_values: DF.Code | None
		robots_txt: DF.Code | None
		route_redirects: DF.Table[WebsiteRouteRedirect]
		show_account_deletion_link: DF.Check
		show_footer_on_login: DF.Check
		show_language_picker: DF.Check
		splash_image: DF.AttachImage | None
		subdomain: DF.SmallText | None
		title_prefix: DF.Data | None
		top_bar_items: DF.Table[TopBarItem]
		website_theme: DF.Link | None
		website_theme_image_link: DF.Code | None
	# end: auto-generated types

	def validate(self) -> None:
		self.validate_top_bar_items()
		self.validate_footer_items()
		self.validate_home_page()
		self.validate_google_settings()
		self.validate_redirects()

	def validate_home_page(self) -> None:
		if frappe.flags.in_install:
			return
		from frappe.website.path_resolver import PathResolver

		if self.home_page and not PathResolver(self.home_page).is_valid_path():
			frappe.msgprint(
				_("Invalid Home Page") + " (Standard pages - home, login, products, blog, about, contact)"
			)
			self.home_page = ""

	def validate_top_bar_items(self) -> None:
		"""validate url in top bar items"""
		for top_bar_item in self.get("top_bar_items"):
			if top_bar_item.parent_label:
				parent_label_item = self.get("top_bar_items", {"label": top_bar_item.parent_label})

				if not parent_label_item:
					# invalid item
					frappe.throw(
						_("{0} does not exist in row {1}").format(top_bar_item.parent_label, top_bar_item.idx)
					)

				elif not parent_label_item[0] or parent_label_item[0].url:
					# parent cannot have url
					frappe.throw(
						_("{0} in row {1} cannot have both URL and child items").format(
							top_bar_item.parent_label, top_bar_item.idx
						)
					)

	def validate_footer_items(self) -> None:
		"""validate url in top bar items"""
		for footer_item in self.get("footer_items"):
			if footer_item.parent_label:
				parent_label_item = self.get("footer_items", {"label": footer_item.parent_label})

				if not parent_label_item:
					# invalid item
					frappe.throw(
						_("{0} does not exist in row {1}").format(footer_item.parent_label, footer_item.idx)
					)

				elif not parent_label_item[0] or parent_label_item[0].url:
					# parent cannot have url
					frappe.throw(
						_("{0} in row {1} cannot have both URL and child items").format(
							footer_item.parent_label, footer_item.idx
						)
					)

	def validate_google_settings(self) -> None:
		if self.enable_google_indexing and not frappe.db.get_single_value("Google Settings", "enable"):
			frappe.throw(_("Enable Google API in Google Settings."))

	def validate_redirects(self) -> None:
		for idx, row in enumerate(self.route_redirects):
			try:
				source = row.source.strip("/ ") + "$"
				re.compile(source)
				re.sub(source, row.target, "")
			except Exception as e:
				if not frappe.flags.in_migrate:
					frappe.throw(_("Invalid redirect regex in row #{}: {}").format(idx, str(e)))

	def on_update(self) -> None:
		self.clear_cache()

	def clear_cache(self) -> None:
		# make js and css
		# clear web cache (for menus!)
		frappe.clear_cache(user="Guest")

		from frappe.website.utils import clear_cache

		clear_cache()

		# clears role based home pages
		frappe.clear_cache()

	def get_access_token(self):
		from frappe.integrations.google_oauth import GoogleOAuth

		if not self.indexing_refresh_token:
			button_label = frappe.bold(_("Allow API Indexing Access"))
			raise frappe.ValidationError(_("Click on {0} to generate Refresh Token.").format(button_label))

		oauth_obj = GoogleOAuth("indexing")
		res = oauth_obj.refresh_access_token(
			self.get_password(fieldname="indexing_refresh_token", raise_exception=False)
		)

		return res.get("access_token")


def get_website_settings(context=None):
	hooks = frappe.get_hooks()
	context = frappe._dict(context or {})
	settings: "WebsiteSettings" = frappe.get_cached_doc("Website Settings")

	context = context.update(
		{
			"top_bar_items": modify_header_footer_items(settings.top_bar_items),
			"footer_items": modify_header_footer_items(settings.footer_items),
			"post_login": [
				{"label": _("My Account"), "url": "/me"},
				{"label": _("Log out"), "url": "/?cmd=web_logout"},
			],
		}
	)

	for k in [
		"banner_html",
		"banner_image",
		"brand_html",
		"copyright",
		"twitter_share_via",
		"facebook_share",
		"google_plus_one",
		"twitter_share",
		"linked_in_share",
		"disable_signup",
		"hide_footer_signup",
		"head_html",
		"title_prefix",
		"navbar_template",
		"footer_template",
		"navbar_search",
		"enable_view_tracking",
		"footer_logo",
		"call_to_action",
		"call_to_action_url",
		"show_language_picker",
		"footer_powered",
	]:
		if setting_value := settings.get(k):
			context[k] = setting_value

	for k in [
		"facebook_share",
		"google_plus_one",
		"twitter_share",
		"linked_in_share",
		"disable_signup",
	]:
		context[k] = cint(context.get(k))

	if settings.address:
		context["footer_address"] = settings.address

	if frappe.request:
		context.url = quote(str(get_request_site_address(full_address=True)), safe="/:")

	context.encoded_title = quote(encode(context.title or ""), "")

	context.web_include_js = hooks.web_include_js or []
	context.web_include_css = hooks.web_include_css or []
	context.web_include_icons = hooks.web_include_icons or []

	via_hooks = hooks.website_context or []
	for key in via_hooks:
		context[key] = via_hooks[key]
		if key not in ("top_bar_items", "footer_items", "post_login") and isinstance(
			context[key], list | tuple
		):
			context[key] = context[key][-1]

	if context.disable_website_theme:
		context.theme = frappe._dict()

	else:
		from frappe.website.doctype.website_theme.website_theme import get_active_theme

		context.theme = get_active_theme() or frappe._dict()

	if not context.get("favicon"):
		context["favicon"] = "/assets/frappe/images/frappe-favicon.svg"

	if settings.favicon and settings.favicon != "attach_files:":
		context["favicon"] = settings.favicon

	context["hide_login"] = settings.hide_login

	if settings.splash_image:
		context["splash_image"] = settings.splash_image

	context.read_only_mode = frappe.flags.read_only
	context.boot = get_boot_data()

	return context


def get_items(parentfield: str) -> list[dict]:
	_items = frappe.get_all(
		"Top Bar Item",
		filters={"parent": "Website Settings", "parentfield": parentfield},
		order_by="idx asc",
		fields="*",
	)
	return modify_header_footer_items(_items)


def modify_header_footer_items(items: list):
	top_items = items.copy()
	# attach child items to top bar
	for item in items:
		if not item.parent_label:
			continue

		for top_bar_item in top_items:
			if top_bar_item.label != item.parent_label:
				continue

			if not top_bar_item.get("child_items"):
				top_bar_item.child_items = []

			top_bar_item.child_items.append(item)
			break

	return top_items


@frappe.whitelist(allow_guest=True)
def get_auto_account_deletion():
	return frappe.db.get_single_value("Website Settings", "auto_account_deletion")
