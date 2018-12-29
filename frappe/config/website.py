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
					"name": "Website",
					"description": _("Setup of top navigation bar, footer and logo."),
				},
				{
					"type": "doctype",
					"name": "Website Theme",
					"description": _("List of themes for Website."),
				},
			]
		},
		{
			"label": _("Portal"),
			"items": [
				{
					"type": "doctype",
					"name": "Portal",
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
