from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint

def execute():
	frappe.reload_doc("website", "doctype", "website_theme")
	frappe.reload_doc("website", "website_theme", "standard")
	frappe.reload_doctype("Website Settings")
	migrate_style_settings()
	frappe.delete_doc("website", "doctype", "style_settings")

def migrate_style_settings():
	style_settings = frappe.db.get_singles_dict("Style Settings")
	standard_website_theme = frappe.get_doc("Website Theme", "Standard")

	website_theme = frappe.copy_doc(standard_website_theme)
	website_theme.custom = 1
	website_theme.theme = _("Custom")

	if style_settings:
		map_color_fields(style_settings, website_theme)
		map_other_fields(style_settings, website_theme)

	website_theme.no_sidebar = cint(frappe.db.get_single_value("Website Settings", "no_sidebar"))

	website_theme.save()
	website_theme.set_as_default()

def map_color_fields(style_settings, website_theme):
	color_fields_map = {
		"page_text": "text_color",
		"page_links": "link_color",
		"top_bar_background": "top_bar_color",
		"top_bar_foreground": "top_bar_text_color",
		"footer_background": "footer_color",
		"footer_color": "footer_text_color",
	}

	for from_fieldname, to_fieldname in color_fields_map.items():
		from_value = style_settings.get(from_fieldname)

		if from_value:
			website_theme.set(to_fieldname, "#{0}".format(from_value))

def map_other_fields(style_settings, website_theme):
	other_fields_map = {
		"heading_text_as": "heading_style",
		"google_web_font_for_heading": "heading_webfont",
		"google_web_font_for_text": "text_webfont",
		"add_css": "css"
	}

	for from_fieldname, to_fieldname in other_fields_map.items():
		website_theme.set(to_fieldname, style_settings.get(from_fieldname))

	for fieldname in ("apply_style", "background_image", "background_color",
		"font_size"):
		website_theme.set(fieldname, style_settings.get(fieldname))
