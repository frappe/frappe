// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.treeview_settings")

frappe.views.TreeFactory = frappe.views.Factory.extend({
	make: function(route) {
		frappe.model.with_doctype(route[1], function() {
			var options = {
				doctype: route[1]
			};

			if (!frappe.treeview_settings[route[1]] && !frappe.meta.get_docfield(route[1], "is_group")) {
				msgprint(__("Tree view not available for {0}", [route[1]] ));
				return false;
			}
			$.extend(options, frappe.treeview_settings[route[1]] || {});
			new frappe.views.TreeView(options);
		});
	}
});

frappe.views.TreeView = Class.extend({
	init: function(opts) {
		var me = this;

		this.opts = {};
		this.opts.get_tree_root = true;
		$.extend(this.opts, opts);
		this.doctype = opts.doctype;
		this.args = {doctype: me.doctype};
		this.page_name = frappe.get_route_str();
		this.get_tree_nodes =  me.opts.get_tree_nodes || "frappe.desk.treeview.get_children";

		this.get_permissions();
		this.make_page();
		this.make_filters();

		if (me.opts.get_tree_root) {
			this.get_root();
		}

		this.set_menu_item();
		this.set_primary_action();
	},
	get_permissions: function(){
		this.can_read = frappe.model.can_read(this.doctype);
		this.can_create = frappe.boot.user.can_create.indexOf(this.doctype) !== -1 ||
					frappe.boot.user.in_create.indexOf(this.doctype) !== -1;
		this.can_write = frappe.model.can_write(this.doctype);
		this.can_delete = frappe.model.can_delete(this.doctype);
	},
	make_page: function() {
		var me = this;
		this.parent = frappe.container.add_page(this.page_name);
		frappe.ui.make_app_page({parent:this.parent, single_column:true});

		this.page = this.parent.page;
		frappe.container.change_to(this.page_name);
		frappe.breadcrumbs.add(me.opts.breadcrumb || locals.DocType[me.doctype].module);

		this.page.set_title(me.opts.title || __('{0} Tree',[__(this.doctype)]) );
		this.page.main.css({
			"min-height": "300px",
			"padding-bottom": "25px"
		})
	},
	make_filters: function(){
		var me = this;
		$.each(this.opts.filters || [], function(i, filter){
			if(frappe.route_options && frappe.route_options[filter.fieldname]) {
				filter.default = frappe.route_options[filter.fieldname]
			}
			
			me.page.add_field(filter).$input
				.change(function() {
					me.args[$(this).attr("data-fieldname")] = $(this).val();
					me.make_tree();
				})

			if (filter.default) {
				$("[data-fieldname='"+filter.fieldname+"']").trigger("change");
			}
		})
	},
	get_root: function() {
		var me = this;
		frappe.call({
			method: me.get_tree_nodes,
			args: me.args,
			callback: function(r) {
				if (r.message) {
					me.root = r.message[0]["value"];
					me.make_tree();
				}
			}
		})
	},
	make_tree: function() {
		var me = this;
		$(me.parent).find(".tree").remove()
		this.tree = new frappe.ui.Tree({
			parent: $(me.parent).find(".layout-main-section"),
			label: me.args[me.opts.root_label] || me.opts.root_label || me.root,
			args: me.args,
			method: me.get_tree_nodes,
			toolbar: me.get_toolbar(),
			get_label: me.opts.get_label,
			onrender: me.opts.onrender
		});
	},
	get_toolbar: function(){
		var me = this;
		
		var toolbar = [
			{toggle_btn: true},
			{
				label:__("Edit"),
				condition: function(node) {
					return !node.root && me.can_read;
				},
				click: function(node) {
					frappe.set_route("Form", me.doctype, node.label);
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
					frappe.model.rename_doc(me.doctype, node.label, function(new_name) {
						node.$a.html(new_name);
					});
				},
				btnClass: "hidden-xs"
			},
			{
				label:__("Delete"),
				condition: function(node) { return !node.root && me.can_delete; },
				click: function(node) {
					frappe.model.delete_doc(me.doctype, node.label, function() {
						node.parent.remove();
					});
				},
				btnClass: "hidden-xs"
			}
		]
		
		if(this.opts.toolbar && this.opts.extend_toolbar) {
			return toolbar.concat(this.opts.toolbar)
		} else if (this.opts.toolbar && !this.opts.extend_toolbar) {
			return this.opts.toolbar
		} else {
			return toolbar
		}
	},
	new_node: function() {
		var me = this;
		var node = me.tree.get_selected_node();

		if(!(node && node.expandable)) {
			frappe.msgprint(__("Select a group node first."));
			return;
		}

		this.prepare_fields()

		// the dialog
		var d = new frappe.ui.Dialog({
			title: __('New {0}',[__(me.doctype)]),
			fields: me.fields
		})

		d.set_value("is_group", 0);
		// create
		d.set_primary_action(__("Create New"), function() {
			var btn = this;
			var v = d.get_values();
			if(!v) return;

			var node = me.tree.get_selected_node();
			v.parent = node.label;
			v.doctype = me.doctype;

			if(node.root) {
				v.is_root = 1;
				v.parent_account = null;
			} else {
				v.is_root = 0;
				v.root_type = null;
			}

			$.extend(me.args, v)

			return frappe.call({
				method: me.opts.add_tree_node || "frappe.desk.treeview.add_node",
				args: me.args,
				callback: function(r) {
					if(!r.exc) {
						d.hide();
						if(node.expanded) {
							node.toggle_node();
						}
						node.reload();
					}
				}
			});
		});
		d.show();
	},
	prepare_fields: function(){
		var me = this;

		this.fields = [
			{fieldtype:'Data', fieldname: 'name_field',
				label:__('New {0} Name',[__(me.doctype)]), reqd:true},
			{fieldtype:'Check', fieldname:'is_group', label:__('Group Node'),
				description: __("Further nodes can be only created under 'Group' type nodes")}
		]

		if (me.opts.fields) {
			me.fields = me.opts.fields;
		}
	},
	set_primary_action: function(){
		var me = this;
		if (!this.opts.disable_add_node) {
			me.page.set_primary_action(__("New"), function() {
				me.new_node();
			}, "octicon octicon-plus")
		}
	},
	set_menu_item: function(){
		var me = this;

		this.menu_items = [
			{
				label: __('View List'),
				action: function() {
					frappe.set_route('List', me.doctype);
				}
			},
			{
				label: __('Refresh'),
				action: function() {
					me.make_tree();
				}
			},
		]

		if (me.opts.menu_items) {
			me.menu_items.push.apply(me.menu_items, me.opts.menu_items)
		}

		$.each(me.menu_items, function(i, menu_item){
			var has_perm = true;
			if(menu_item["condition"]) {
				has_perm = eval(menu_item["condition"]);
			}

			if (has_perm) {
				me.page.add_menu_item(menu_item["label"], menu_item["action"]);
			}
		})
	}
});








