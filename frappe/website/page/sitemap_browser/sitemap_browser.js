// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt"

frappe.pages['sitemap-browser'].onload = function(wrapper) { 
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Sitemap Browser',
	});					
	wrapper.appframe.add_module_icon("Website")

	wrapper.appframe.set_title_right('Refresh', function() {  
		wrapper.make_tree();
	});

	$(wrapper)
		.find(".layout-side-section")
		.html('<div class="text-muted">'+ 
			frappe._('Click on a link to get options to expand get options ') + 
			frappe._('Add') + ' / ' + frappe._('Edit') + ' / '+ frappe._('Remove') + '.</div>')

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
			click: function(link) {
				if(me.cur_toolbar) 
					$(me.cur_toolbar).toggle(false);

				if(!link.toolbar) 
					me.make_link_toolbar(link);

				if(link.toolbar) {
					me.cur_toolbar = link.toolbar;
					$(me.cur_toolbar).toggle(true);					
				}
			},
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
	make_link_toolbar: function(link) {
		var data = $(link).data('node-data');
		if(!data) return;

		link.toolbar = $('<span class="tree-node-toolbar"></span>').insertAfter(link);
		
		// edit
		var node_links = [];
		
		node_links.push('<a onclick="frappe.website.sitemap.open();">'+frappe._('Edit')+'</a>');
		node_links.push('<a onclick="frappe.website.sitemap.update_parent();">'+frappe._('Move')+'</a>');
		node_links.push('<a onclick="frappe.website.sitemap.up_or_down(\'up\');">'+frappe._('Up')+'</a>');
		node_links.push('<a onclick="frappe.website.sitemap.up_or_down(\'down\');">'+frappe._('Down')+'</a>');
		
		link.toolbar.append(node_links.join(" | "));
	},
	selected_node: function() {
		return this.tree.$w.find('.tree-link.selected');
	},
	open: function() {
		var node = this.selected_node();
		frappe.set_route("Form", "Website Sitemap", node.data("label"));
	},
	up_or_down: function(up_or_down) {
		var node = this.tree.get_selected_node();
		frappe.call({
			method: "frappe.website.page.sitemap_browser.sitemap_browser.move",
			args: {
				"name": node.label,
				"up_or_down": up_or_down
			},
			callback: function(r) {
				if(r.message==="ok") {
					node.parent.insertBefore(up_or_down==="up" ? 
						node.parent.prev() : node.parent.next().next());
					//(node.parent_node || node).reload();
				}
			}
		});
	},
	update_parent: function() {
		var me = this;
		if(!this.move_dialog) {
			this.move_dialog = new frappe.ui.Dialog({
				title: frappe._("Move"),
				fields: [
					{ 
						fieldtype: "Link", 
						fieldname: "new_parent",
						label: "New Parent", 
						reqd: 1, 
						options: "Website Sitemap"
					},
					{ 
						fieldtype: "Button", 
						fieldname: "update",
						label: "Update", 
					}
				]
			});
			this.move_dialog.get_input("update").on("click", function() {
				var node = me.tree.get_selected_node();
				var values = me.move_dialog.get_values();
				if(!values) return;
				me.update_parent(node.label, values.new_parent, function(r) {
					me.move_dialog.hide();
					(node.parent_node || node).reload();
				})
			});
		}
		this.move_dialog.show();
		this.move_dialog.get_input("new_parent").val("");
	},
	update_parent: function(name, parent, callback) {
		frappe.call({
			method: "frappe.website.page.sitemap_browser.sitemap_browser.update_parent",
			args: {
				"name": name,
				"new_parent": parent
			},
			callback: function(r) {
				callback(r);
			}
		});
		
	}
});