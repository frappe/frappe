from __future__ import unicode_literals
from frappe import _

def get_data():
	return [
		{
			"label": _("Web Site"),
			"icon": "fa fa-star",
			"items": [
				{
					"type": "doctype",
					"name": "Web Page",
					"description": _("Content web page."),
				},
				{
					"type": "doctype",
					"name": "Web Form",
					"description": _("User editable form on Website."),
				},
				{
					"type": "doctype",
					"name": "Website Sidebar",
				},
				{
					"type": "doctype",
					"name": "Website Slideshow",
					"description": _("Embed image slideshows in website pages."),
				},
			]
		},
		{
			"label": _("Blog"),
			"items": [
				{
					"type": "doctype",
					"name": "Blog Post",
					"description": _("Single Post (article)."),
				},
				{
					"type": "doctype",
					"name": "Blog Settings",
					"description": _("Write titles and introductions to your blog."),
				},
				{
					"type": "doctype",
					"name": "Blog Category",
					"description": _("Categorize blog posts."),
				},
			]
		},
		{
			"label": _("Setup"),
			"icon": "fa fa-cog",
			"items": [
				{
					"type": "doctype",
					"name": "Website Settings",
					"description": _("Setup of top navigation bar, footer and logo."),
				},
				{
					"type": "doctype",
					"name": "Website Theme",
					"description": _("List of themes for Website."),
				},
				{
					"type": "doctype",
					"name": "Website Script",
					"description": _("Javascript to append to the head section of the page."),
				},
				{
					"type": "doctype",
					"name": "About Us Settings",
					"description": _("Settings for About Us Page."),
				},
				{
					"type": "doctype",
					"name": "Contact Us Settings",
					"description": _("Settings for Contact Us Page."),
				},
			]
		},
		{
			"label": _("Portal"),
			"items": [
				{
					"type": "doctype",
					"name": "Portal Settings",
					"label": _("Portal Settings"),
				}
			]
		},
		{
			"label": _("Knowledge Base"),
			"items": [
				{
					"type": "doctype",
					"name": "Help Category",
				},
				{
					"type": "doctype",
					"name": "Help Article",
				},
			]
		},

	]
