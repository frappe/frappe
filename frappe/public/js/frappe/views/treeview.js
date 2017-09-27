// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.treeview_settings");
frappe.provide('frappe.views.trees');
cur_tree = null;

frappe.views.TreeFactory = frappe.views.Factory.extend({
	make: function(route) {
		frappe.model.with_doctype(route[1], function() {
			var options = {
				doctype: route[1],
				meta: frappe.get_meta(route[1])
			};

			if (!frappe.treeview_settings[route[1]] && !frappe.meta.get_docfield(route[1], "is_group")) {
				frappe.msgprint(__("Tree view not available for {0}", [route[1]] ));
				return false;
			}
			$.extend(options, frappe.treeview_settings[route[1]] || {});
			frappe.views.trees[options.doctype] = new frappe.views.TreeView(options);
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
		});

		this.page.add_inner_button(__('Expand All'), function() {
			me.tree.rootnode.load_all();
		});

		if(this.opts.view_template) {
			var row = $('<div class="row"><div>').appendTo(this.page.main);
			this.body = $('<div class="col-sm-6 col-xs-12"></div>').appendTo(row);
			this.node_view = $('<div class="col-sm-6 hidden-xs"></div>').appendTo(row);
		} else {
			this.body = this.page.main;
		}
	},
	make_filters: function(){
		var me = this;
		frappe.treeview_settings.filters = []
		$.each(this.opts.filters || [], function(i, filter) {
			if(frappe.route_options && frappe.route_options[filter.fieldname]) {
				filter.default = frappe.route_options[filter.fieldname]
			}

			me.page.add_field(filter).$input
				.on('change', function() {
					var val = $(this).val();
					if(val) {
						me.args[$(this).attr("data-fieldname")] = val;
						frappe.treeview_settings.filters = me.args;
						me.make_tree();
						me.page.set_title(val);
					}
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
			parent: me.body,
			label: me.args[me.opts.root_label] || me.opts.root_label || me.root,
			args: me.args,
			method: me.get_tree_nodes,
			toolbar: me.get_toolbar(),
			get_label: me.opts.get_label,
			onrender: me.opts.onrender,
			onclick: function(node) { me.select_node(node) },
		});
		cur_tree = this.tree;
	},
	select_node: function(node) {
		var me = this;
		if(this.opts.click) {
			this.opts.click(node);
		}
		if(this.opts.view_template) {
			this.node_view.empty();
			$(frappe.render_template(me.opts.view_template,
				{data:node.data, doctype:me.doctype})).appendTo(this.node_view);
		}
	},
	get_toolbar: function() {
		var me = this;

		var toolbar = [
			{toggle_btn: true},
			{
				label:__(me.can_write? "Edit": "Details"),
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
						node.tree_link.find('a').text(new_name);
						node.label = new_name;
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

		this.prepare_fields();

		// the dialog
		var d = new frappe.ui.Dialog({
			title: __('New {0}',[__(me.doctype)]),
			fields: me.fields
		});

		var args = $.extend({}, me.args);
		args["parent_"+me.doctype.toLowerCase().replace(/ /g,'_')] = me.args["parent"];

		d.set_value("is_group", 0);
		d.set_values(args);

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

			$.extend(args, v)
			return frappe.call({
				method: me.opts.add_tree_node || "frappe.desk.treeview.add_node",
				args: args,
				callback: function(r) {
					if(!r.exc) {
						d.hide();
						if(node.expanded) {
							node.toggle_node();
						}
						node.load_all();
					}
				}
			});
		});
		d.show();
	},
	prepare_fields: function(){
		var me = this;

		this.fields = [
			{fieldtype:'Check', fieldname:'is_group', label:__('Group Node'),
				description: __("Further nodes can be only created under 'Group' type nodes")}
		]

		if (this.opts.fields) {
			this.fields = this.opts.fields;
		}

		this.ignore_fields = this.opts.ignore_fields || [];

		var mandatory_fields = $.map(me.opts.meta.fields, function(d) {
			return (d.reqd || d.bold && !d.read_only) ? d : null });

		var opts_field_names = this.fields.map(function(d) {
			return d.fieldname
		})

		mandatory_fields.map(function(d) {
			if($.inArray(d.fieldname, me.ignore_fields) === -1 && $.inArray(d.fieldname, opts_field_names) === -1) {
				me.fields.push(d)
			}
		})
	},
	print_tree: function() {
		if(!frappe.model.can_print(this.doctype)) {
			frappe.msgprint(__("You are not allowed to print this report"));
			return false;
		}
		var tree = $(".tree:visible").html();
		var me = this;
		frappe.ui.get_print_settings(false, function(print_settings) {
			var title =  __(me.docname || me.doctype);
			frappe.render_tree({title: title, tree: tree, print_settings:print_settings});
		});
	},
	set_primary_action: function(){
		var me = this;
		if (!this.opts.disable_add_node && this.can_create) {
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
				label: __('Print'),
				action: function() {
					me.print_tree();
				}

			},
			{
				label: __('Refresh'),
				action: function() {
					me.make_tree();
				}
			},
		];

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
		});

		// last menu item
		me.page.add_menu_item(__('Add to Desktop'), () => {
			const label = me.doctype === 'Account' ?
				__('Chart of Accounts') :
				__(me.doctype);
			frappe.add_to_desktop(label, me.doctype);
		});
	}
});








