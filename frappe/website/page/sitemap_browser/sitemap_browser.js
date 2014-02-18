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
			}
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
		node_links.push('<a onclick="frappe.website.sitemap.move();">'+frappe._('Move')+'</a>');
		node_links.push('<a onclick="frappe.website.sitemap.up_or_down(\'up\');">'+frappe._('Up')+'</a>');
		node_links.push('<a onclick="frappe.website.sitemap.up_or_down(\'down\');">'+frappe._('Down')+'</a>');

		// if(data.expandable) {
		// 	node_links.push('<a onclick="frappe.website.sitemap.new_node();">' + frappe._('Add Child') + '</a>');
		// }
		// 	
		// node_links.push('<a onclick="frappe.website.sitemap.delete()">' + frappe._('Delete') + '</a>');
		
		link.toolbar.append(node_links.join(" | "));
	},
	new_node: function() {
		var me = this;
		
		var fields = [
			{fieldtype:'Data', fieldname: 'name_field', 
				label:'New ' + me.ctype + ' Name', reqd:true},
			{fieldtype:'Select', fieldname:'is_group', label:'Group Node', options:'No\nYes', 
				description: frappe._("Further nodes can be only created under 'Group' type nodes")}, 
			{fieldtype:'Button', fieldname:'create_new', label:'Create New' }
		]
		
		if(me.ctype == "Sales Person") {
			fields.splice(-1, 0, {fieldtype:'Link', fieldname:'employee', label:'Employee',
				options:'Employee', description: frappe._("Please enter Employee Id of this sales parson")});
		}
		
		// the dialog
		var d = new frappe.ui.Dialog({
			title: frappe._('New ') + frappe._(me.ctype),
			fields: fields
		})		
	
		d.set_value("is_group", "No");
		// create
		$(d.fields_dict.create_new.input).click(function() {
			var btn = this;
			$(btn).set_working();
			var v = d.get_values();
			if(!v) return;
			
			var node = me.selected_node();
			
			v.parent = node.data('label');
			v.ctype = me.ctype;
			
			return frappe.call({
				method: 'erpnext.selling.page.sales_browser.sales_browser.add_node',
				args: v,
				callback: function() {
					$(btn).done_working();
					d.hide();
					node.trigger('reload');
				}	
			})			
		});
		d.show();		
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
				(node.parent_node || node).reload();
			}
		});
	},
	move: function() {
		var me = this;
		var node = this.selected_node();
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
				var values = me.move_dialog.get_values();
				if(!values) return;
				frappe.call({
					method: "frappe.website.page.sitemap_browser.sitemap_browser.update_parent",
					args: {
						"name": node.data("label"),
						"new_parent": values.new_parent
					},
					callback: function(r) {
						me.move_dialog.hide();
						me.tree.rootnode.reload();
					}
				});
			});
		}
		this.move_dialog.show();
		this.move_dialog.get_input("new_parent").val("");
		
	}
});