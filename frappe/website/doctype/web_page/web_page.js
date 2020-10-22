// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.on('Web Page', {
	title: function(frm) {
		if (frm.doc.title && !frm.doc.route) {
			frm.set_value('route', frappe.scrub(frm.doc.title, '-'));
		}
	},
	layout: function(frm) {
		if (frm.is_new()) {
			if (frm.doc.insert_code) {
				if (!frm.doc.javascript) {
					frm.set_value('javascript', `frappe.ready(() => {\n\t\n});`);
				}
			}
		}
	},
	insert_code: function(frm) {
		frm.events.layout(frm);
	},
	onload: function(frm) {
		frm.set_query('web_template', 'page_blocks', function() {
			return {
				filters: {
					"type": 'Section'
				}
			};
		});
	},
	refresh: function(frm) {
		if (frm.doc.template_path) {
			frm.set_read_only();
		} else {
			frm.events.layout(frm);
		}
	},
	published: function(frm) {
		// If current date is before end date,
		// and web page is manually unpublished,
		// set end date to current date.
		if (!frm.doc.published && frm.doc.end_date) {
			var end_date = frappe.datetime.str_to_obj(frappe.datetime.now_datetime());

			// Set date a few seconds in the future to avoid throwing
			// start and end date validation error
			end_date.setSeconds(end_date.getSeconds() + 5);

			frm.set_value('end_date', end_date);
		}
	},
	set_meta_tags(frm) {
		frappe.utils.set_meta_tag(frm.doc.route);
	}
});

frappe.ui.form.on("Web Page Block", {
	edit_values(frm, cdt, cdn) {
		let row = frm.selected_doc;
		let values = JSON.parse(row.web_template_values || "{}");
		open_web_template_values_editor(row.web_template, values)
			.then(new_values => {
				frappe.model.set_value(cdt, cdn, "web_template_values", JSON.stringify(new_values));
			});
	},
});

frappe.tour['Web Page'] = [
	{
		fieldname: "title",
		title: __("Title of the page"),
		description: __("This title will be used as the title of the webpage as well as in meta tags"),
	},
	{
		fieldname: "published",
		title: __("Makes the page public"),
		description: __("Checking this will publish the page on your website and it'll be visible to everyone."),
	},
	{
		fieldname: "route",
		title: __("URL of the page"),
		description: __("This will be automatically generated when you publish the page, you can also enter a route yourself if you wish"),
	},
	{
		fieldname: "content_type",
		title: __("Content type for building the page"),
		description: `${__('You can select one from the following,')} <br>
					<ul>
						<li><b>${__('Rich Text')}</b>: ${__('Standard rich text editor with controls')}</li>
						<li><b>${__('Markdown')}</b>: ${__('Github flavoured markdown syntax')}</li>
						<li><b>${__('HTML')}</b>: ${__('HTML with jinja support')}</li>
						<li><b>${__('Page Builder')}</b>: ${__('Frappe page builder using components')}</li>
					</ul>
					`
	},
	{
		fieldname: "insert_code",
		title: __("Client Script"),
		description: __("Checking this will show a text area where you can write custom javascript that will run on this page."),
	},
	{
		fieldname: "meta_title",
		title: __("Meta title for SEO"),
		description: __("By default the title is used as meta title, adding a value here will override it."),
	},
	{
		fieldname: "meta_title",
		title: __("Meta Title"),
		description: __("By default the title is used as meta title, adding a value here will override it."),
	},
	{
		fieldname: "meta_description",
		title: __("Meta Description"),
		description: __("The meta description is an HTML attribute that provides a brief summary of a web page. Search engines such as Google often display the meta description in search results, which can influence click-through rates.")
	},
	{
		fieldname: "meta_image",
		title: __("Meta Image"),
		description: __("The meta image is unique image representing the content of the page. Images for this Card should be at least 280px in width, and at least 150px in height.")
	},
];
