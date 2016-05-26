// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.views.TreeFactory = frappe.views.Factory.extend({
	make: function(route) {
		new frappe.views.TreeViewPage(route[1]);
	}
});

frappe.views.TreeViewPage = Class.extend({
	init: function(ctype) {
		var me = this;
		this.ctype = ctype;
		
		this.can_read = frappe.model.can_read(this.ctype);
		this.can_create = frappe.boot.user.can_create.indexOf(this.ctype) !== -1 ||
					frappe.boot.user.in_create.indexOf(this.ctype) !== -1;
		this.can_write = frappe.model.can_write(this.ctype);
		this.can_delete = frappe.model.can_delete(this.ctype);
		
		this.page_name = frappe.get_route_str();
		this.make_page();
		this.get_root();
		me.page.add_menu_item(__('Refresh'), function() {
			me.make_tree();
		});
		
		me.page.set_primary_action(__("New"), function() {
			me.new_node();
		}, "octicon octicon-plus");

	},
	make_page: function() {
		var me = this;
		this.parent = frappe.container.add_page(this.page_name);
		frappe.ui.make_app_page({parent:this.parent, single_column:true});
		this.page = this.parent.page;

		frappe.container.change_to(this.page_name);
		
		frappe.breadcrumbs.add(frappe.breadcrumbs.last_module || "Selling");
		
		this.page.set_title(__('{0} Tree',[__(this.ctype)]));
		
		this.page.main.css({
			"min-height": "300px",
			"padding-bottom": "25px"
		})
	},
	get_root: function() {
		var me = this;
		frappe.call({
			method: 'erpnext.selling.page.sales_browser.sales_browser.get_children',
			args: {ctype: me.ctype},
			callback: function(r) {
				me.root = r.message[0]["value"];
				me.make_tree();
			}
		})
	},
	make_tree: function() {
		var me = this;
		this.tree = new frappe.ui.Tree({
			parent: $(me.parent).find(".layout-main-section"),
			label: __(me.root),
			args: {ctype: me.ctype},
			method: 'erpnext.selling.page.sales_browser.sales_browser.get_children',
			toolbar: [
				{toggle_btn: true},
				{
					label:__("Edit"),
					condition: function(node) {
						return !node.root && me.can_read;
					},
					click: function(node) {
						frappe.set_route("Form", me.ctype, node.label);
					}
				},
				{
					label:__("Add Child"),
					condition: function(node) { return me.can_create && node.expandable; },
					click: function(node) {
						me.new_node();
					},
					btnClass: "hidden-xs"
				},
				{
					label:__("Rename"),
					condition: function(node) { return !node.root && me.can_write; },
					click: function(node) {
						frappe.model.rename_doc(me.ctype, node.label, function(new_name) {
							node.$a.html(new_name);
						});
					},
					btnClass: "hidden-xs"
				},
				{
					label:__("Delete"),
					condition: function(node) { return !node.root && me.can_delete; },
					click: function(node) {
						frappe.model.delete_doc(me.ctype, node.label, function() {
							node.parent.remove();
						});
					},
					btnClass: "hidden-xs"
				}

			]
		});
	}
});



		



// new_node: function() {
// 	var me = this;
// 	var node = me.tree.get_selected_node();
//
// 	if(!(node && node.expandable)) {
// 		frappe.msgprint(__("Select a group node first."));
// 		return;
// 	}
//
// 	var fields = [
// 		{fieldtype:'Data', fieldname: 'name_field',
// 			label:__('New {0} Name',[__(me.ctype)]), reqd:true},
// 		{fieldtype:'Select', fieldname:'is_group', label:__('Group Node'), options:'No\nYes',
// 			description: __("Further nodes can be only created under 'Group' type nodes")}
// 	]
//
// 	if(me.ctype == "Sales Person") {
// 		fields.splice(-1, 0, {fieldtype:'Link', fieldname:'employee', label:__('Employee'),
// 			options:'Employee', description: __("Please enter Employee Id of this sales person")});
// 	}
//
// 	// the dialog
// 	var d = new frappe.ui.Dialog({
// 		title: __('New {0}',[__(me.ctype)]),
// 		fields: fields
// 	})
//
// 	d.set_value("is_group", "No");
// 	// create
// 	d.set_primary_action(__("Create New"), function() {
// 		var btn = this;
// 		var v = d.get_values();
// 		if(!v) return;
//
// 		var node = me.tree.get_selected_node();
//
// 		v.parent = node.label;
// 		v.ctype = me.ctype;
//
// 		return frappe.call({
// 			method: 'erpnext.selling.page.sales_browser.sales_browser.add_node',
// 			args: v,
// 			callback: function(r) {
// 				if(!r.exc) {
// 					d.hide();
// 					if(node.expanded) {
// 						node.toggle_node();
// 					}
// 					node.reload();
// 				}
// 			}
// 		});
// 	});
//
// 	d.show();
// },

