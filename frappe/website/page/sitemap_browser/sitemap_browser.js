// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt"

frappe.pages['sitemap-browser'].onload = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Sitemap Browser',
	});
	wrapper.appframe.add_module_icon("Website")

	wrapper.appframe.set_title_right('Refresh', function() {
		frappe.website.sitemap.tree.rootnode.reload();
	});

	$(wrapper)
		.find(".layout-side-section")
		.html('<div class="text-muted">'+
			__('Click on a link to get options') + '</div>')

	frappe.website.sitemap = new frappe.website.SitemapBrowser(
		$(wrapper)
			.find(".layout-main-section")
			.css({
				"min-height": "300px",
				"padding-bottom": "25px"
			}));
}

frappe.provide("frappe.website");

frappe.website.SitemapBrowser = Class.extend({
	init: function(parent) {
		$(parent).empty();
		var me = this;
		this.tree = new frappe.ui.Tree({
			parent: $(parent),
			label: "Sitemap",
			method: 'frappe.website.page.sitemap_browser.sitemap_browser.get_children',
			toolbar: [
				{
					toggle_btn: true,
				},
				{
					label: __("Open"),
					click: function(node, btn) {
						frappe.set_route("Form", node.data.ref_doctype, node.data.docname);
					}
				}
			]

			// drop: function(dragged_node, dropped_node, dragged_element, dropped_element) {
			// 	frappe.website.sitemap.update_parent(dragged_node.label, dropped_node.label, function(r) {
			// 		if(!r.exc) {
			// 			dragged_element.remove();
			// 			dropped_node.reload();
			// 		}
			// 	});
			// }
		});
		this.tree.rootnode.$a
			.data('node-data', {value: "Sitemap", expandable:1})
			.click();
	},
	selected_node: function() {
		return this.tree.$w.find('.tree-link.selected');
	},
	open: function() {
		var node = this.selected_node();
		frappe.set_route("Form", "Website Route", node.data("label"));
	},
});
