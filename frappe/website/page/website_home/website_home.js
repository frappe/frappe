// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt"

frappe.module_page["Website"] = [
	{
		title: frappe._("Web Content"),
		icon: "icon-copy",
		top: true,
		items: [
			{
				label: frappe._("Web Page"),
				description: frappe._("Content web page."),
				doctype:"Web Page"
			},
			{
				label: frappe._("Website Group"),
				description: frappe._("Web Site Forum Page."),
				doctype:"Website Group"
			},
			{
				label: frappe._("Blog Post"),
				description: frappe._("Single Post (article)."),
				doctype:"Blog Post"
			},
		]
	},
	{
		title: frappe._("Documents"),
		icon: "icon-edit",
		items: [
			{
				label: frappe._("Website Slideshow"),
				description: frappe._("Embed image slideshows in website pages."),
				doctype:"Website Slideshow"
			},
			{
				label: frappe._("Blogger"),
				description: frappe._("Profile of a blog writer."),
				doctype:"Blogger"
			},
			{
				label: frappe._("Blog Category"),
				description: frappe._("Categorize blog posts."),
				doctype:"Blog Category"
			},
			{
				label: frappe._("Blog Settings"),
				description: frappe._("Write titles and introductions to your blog."),
				doctype:"Blog Settings",
				route: "Form/Blog Settings"
			},
			{
				label: frappe._("Website Page Permission"),
				description: frappe._("Define read, write, admin permissions for a Website Page."),
				doctype:"Website Route Permission",
			},
		]
	},

	{
		title: frappe._("Website Overall Settings"),
		icon: "icon-wrench",
		right: true,
		items: [
			{
				"route":"sitemap-browser",
				"label":frappe._("Sitemap Browser"),
				"description":frappe._("View or manage Website Route tree."),
				doctype:"Website Settings",
				icon: "icon-sitemap"
			},
			{
				"route":"Form/Website Settings",
				"label":frappe._("Website Settings"),
				"description":frappe._("Setup of top navigation bar, footer and logo."),
				doctype:"Website Settings"
			},
			{
				"route":"Form/Style Settings",
				"label":frappe._("Style Settings"),
				"description":frappe._("Setup of fonts and background."),
				doctype:"Style Settings"
			},
		]
	},
	{
		title: frappe._("Special Page Settings"),
		icon: "icon-wrench",
		right: true,
		items: [
			{
				"route":"Form/About Us Settings",
				"label":frappe._("About Us Settings"),
				"description":frappe._("Settings for About Us Page."),
				doctype:"About Us Settings"
			},
			{
				"route":"Form/Contact Us Settings",
				"label":frappe._("Contact Us Settings"),
				"description":frappe._("Settings for Contact Us Page."),
				doctype:"Contact Us Settings"
			},
		]
	},
	{
		title: frappe._("Advanced Scripting"),
		icon: "icon-wrench",
		right: true,
		items: [
			{
				"route":"Form/Website Script",
				"label":frappe._("Website Script"),
				"description":frappe._("Javascript to append to the head section of the page."),
				doctype:"Website Script"
			},
		]
	}
]

pscript['onload_website-home'] = function(wrapper) {
	frappe.views.moduleview.make(wrapper, "Website");
}