// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.treeview_settings");
frappe.provide("frappe.views.trees");
window.cur_tree = null;

frappe.views.TreeFactory = class TreeFactory extends frappe.views.Factory {
	make(route) {
		frappe.model.with_doctype(route[1], function () {
			var options = {
				doctype: route[1],
				meta: frappe.get_meta(route[1]),
			};

			if (
				!frappe.treeview_settings[route[1]] &&
				!frappe.meta.get_docfield(route[1], "is_group")
			) {
				frappe.msgprint(__("Tree view is not available for {0}", [route[1]]));
				return false;
			}
			$.extend(options, frappe.treeview_settings[route[1]] || {});
			frappe.views.trees[options.doctype] = new frappe.views.TreeView(options);
		});
	}

	on_show() {
		/**
		 * On back-navigation the framework re-shows the existing treeview
		 * element instead of rebuilding it, so the expanded nodes are kept
		 * as the user left them. Point cur_tree back at this tree; use the
		 * Refresh menu item to reload data when it may have changed.
		 */
		let route = frappe.get_route();
		let treeview = frappe.views.trees[route[1]];
		if (treeview && treeview.tree) {
			cur_tree = treeview.tree;
			if (treeview.scroll_position) {
				frappe.utils.scroll_to(treeview.scroll_position, false, 0, $(".main-section"));
			}
		}
	}

	get view_name() {
		return "Tree";
	}
};

/**
 * The standard view switcher, mounted on the tree page header so Tree keeps
 * the same header anatomy as the list-family views (and switching back
 * doesn't require digging through the ... menu).
 */
frappe.views.TreeViewSelect = class TreeViewSelect extends frappe.views.ListViewSelect {
	set_current_view() {
		// tree routes are ["Tree", doctype], not [doctype, "view", <name>],
		// so the route-based detection in ListViewSelect would report "List"
		this.current_view = "Tree";
	}

	set_route(view, calendar_name) {
		// the tree page has no search box, so unlike the list switcher don't
		// carry cur_list's search params — cur_list here is whatever list was
		// visited last, possibly another doctype's
		const route = [this.slug(), "view", view];
		if (calendar_name) route.push(calendar_name);
		frappe.set_route(route);
	}
};

frappe.views.TreeView = class TreeView {
	constructor(opts) {
		var me = this;

		this.opts = {};
		this.opts.get_tree_root = true;
		this.opts.show_expand_all = true;
		$.extend(this.opts, opts);
		this.doctype = opts.doctype;
		this.args = { doctype: me.doctype };
		this.page_name = frappe.get_route_str();
		this.get_tree_nodes = me.opts.get_tree_nodes || "frappe.desk.treeview.get_children";

		this.get_permissions();

		this.make_page();
		this.make_filters();
		this.root_value = null;
		if (me.opts.get_tree_root) {
			this.get_root();
		}

		this.onload();

		if (!this.opts.do_not_setup_menu) {
			this.set_menu_item();
		}

		this.set_primary_action();
	}
	get_permissions() {
		this.can_read = frappe.model.can_read(this.doctype);
		this.can_create =
			frappe.boot.user.can_create.indexOf(this.doctype) !== -1 ||
			frappe.boot.user.in_create.indexOf(this.doctype) !== -1;
		this.can_write = frappe.model.can_write(this.doctype);
		this.can_delete = frappe.model.can_delete(this.doctype);
	}
	make_page() {
		var me = this;
		if (!this.opts || !this.opts.do_not_make_page) {
			this.parent = frappe.container.add_page(this.page_name);
			$(this.parent).addClass("treeview");
			$(".main-section").on("scroll.treeview_" + this.page_name, () => {
				if (frappe.get_route_str() === me.page_name) {
					me.scroll_position = $(".main-section").scrollTop();
				}
			});
			frappe.ui.make_app_page({ parent: this.parent, single_column: true });
			this.page = this.parent.page;
			frappe.container.change_to(this.page_name);
			frappe.breadcrumbs.add(
				me.opts.breadcrumb || locals.DocType[me.doctype].module,
				me.doctype
			);

			this.set_title();
			this.setup_view_switcher();

			// same reload affordance as the list views' default secondary action
			this.page.add_action_icon(
				"refresh-cw",
				() => {
					this.make_tree();
				},
				"",
				__("Reload Tree")
			);

			this.page.main.css({
				"min-height": "300px",
			});

			this.make_tree_toolbar();

			if (this.opts.view_template) {
				var row = $('<div class="row"><div>').appendTo(this.page.main);
				this.body = $('<div class="col-sm-6 col-xs-12"></div>').appendTo(row);
				this.node_view = $('<div class="col-sm-6 hidden-xs"></div>').appendTo(row);
			} else {
				this.body = $('<div class="tree-view-body"></div>').appendTo(this.page.main);
			}
		} else {
			this.page = this.opts.page;
			$(this.page[0]).addClass("frappe-card");
			this.body = this.page.main;
		}
	}
	make_tree_toolbar() {
		var me = this;

		// same filter-bar anatomy as the list views: page_form holding a
		// .standard-filter-section, fields added through page.add_field
		this.page.page_form.removeClass("row").addClass("flex");
		this.$filter_area = $('<div class="standard-filter-section flex"></div>').appendTo(
			this.page.page_form
		);

		// the same name filter every list view leads with
		let search_field = this.page.add_field(
			{
				fieldtype: "Data",
				fieldname: "tree_search",
				label: __("ID"),
			},
			this.$filter_area
		);
		this.$search_input = search_field.$input;
		this.$search_input.on(
			"input",
			frappe.utils.debounce(() => this.apply_search(search_field.get_value()), 300)
		);

		if (this.opts.show_expand_all) {
			let $actions = $(
				'<div class="tree-toolbar-actions ms-auto flex items-center gap-1 py-1"></div>'
			).appendTo(this.page.page_form);
			frappe.ui.dropdown({
				button: { label: __("Expand/Collapse"), icon_right: "chevron-down" },
				align: "end",
				options: () => {
					const state = this.tree ? this.tree.get_expansion_state() : "none";
					return [
						{
							label: __("Expand All"),
							icon: "copy-plus",
							disabled: !(state === "collapsed" || state === "partial"),
							onclick: () => {
								this.tree.load_children(this.tree.root_node, true);
							},
						},
						{
							label: __("Collapse All"),
							icon: "copy-minus",
							disabled: !(state === "expanded" || state === "partial"),
							onclick: () => {
								this.tree.load_children(this.tree.root_node, false);
							},
						},
					];
				},
			}).appendTo($actions);
		}
	}
	set_title() {
		this.page.set_title(this.opts.title || __("{0} Tree", [__(this.doctype)]));
	}
	setup_view_switcher() {
		if (
			!frappe.boot.desk_settings.view_switcher ||
			this.opts.meta?.force_re_route_to_default_view
		) {
			return;
		}
		// ListViewSelect only needs meta and settings from its list_view —
		// hand it a minimal adapter since there is no list view on this page
		this.views_list = new frappe.views.TreeViewSelect({
			doctype: this.doctype,
			page: this.page,
			list_view: {
				meta: this.opts.meta || frappe.get_meta(this.doctype),
				settings: frappe.listview_settings[this.doctype] || {},
			},
			icon_map: frappe.views.view_icon_map,
			label_map: frappe.views.get_view_label_map(),
		});
	}
	onload() {
		var me = this;
		this.opts.onload && this.opts.onload(me);
	}
	make_filters() {
		var me = this;
		$.each(this.opts.filters || [], function (i, filter) {
			if (frappe.route_options && frappe.route_options[filter.fieldname]) {
				filter.default = frappe.route_options[filter.fieldname];
			}

			if (!filter.disable_onchange) {
				filter.change = function () {
					filter.onchange && filter.onchange();
					var val = this.get_value();
					me.args[filter.fieldname] = val;
					if (val) {
						me.root_label = val;
					} else {
						me.root_label = me.opts.root_label;
					}
					me.set_title();
					me.make_tree();
				};
			}

			// every filter renders in the tree filter bar; render_on_toolbar is
			// accepted for backward compatibility but no longer changes
			// placement. Fields still register in page.fields_dict, which
			// apps read (e.g. page.fields_dict.company.get_value()).
			var field = me.page.add_field(filter, me.$filter_area || me.page.filters);

			if (filter.default) {
				if (field && field.$input) {
					field.$input.trigger("change");
				} else {
					$("[data-fieldname='" + filter.fieldname + "']").trigger("change");
				}
			}
		});

		// disabled records toggle — a checkbox in the filter bar, the way
		// list views render Check standard filters
		if (!this.opts.do_not_make_page && frappe.meta.has_field(this.doctype, "disabled")) {
			let field = me.page.add_field(
				{
					fieldname: "include_disabled",
					fieldtype: "Check",
					label: __("Show all (including disabled)"),
					change: function () {
						me.args["include_disabled"] = cint(field.get_value());
						me.make_tree();
					},
				},
				me.$filter_area
			);
		}
	}
	get_root() {
		var me = this;

		frappe.call({
			method: me.get_tree_nodes,
			args: me.args,
			callback: function (r) {
				if (r.message) {
					if (r.message.length == 1) {
						me.root_label = r.message[0]["value"];
						me.root_value = me.root_label;
					} else {
						me.root_label = me.doctype;
						me.root_value = "";
					}

					me.make_tree();
				}
			},
		});
	}
	show_tree_skeleton() {
		if (!this.body || this.opts.do_not_make_page) return;
		this.hide_tree_skeleton();
		const row = (indent, width) => `
			<div class="flex items-center gap-2.5" style="height: 32px; padding-left: ${indent}px">
				${frappe.ui.skeleton.html({ width: "14px", height: "14px" })}
				${frappe.ui.skeleton.html({ width: width, height: "13px" })}
			</div>`;
		this.$tree_skeleton = $(`
			<div class="tree-skeleton p-1" aria-busy="true" aria-label="${__("Loading")}">
				${row(8, "90px")}
				${row(32, "220px")}
				${row(32, "180px")}
				${row(32, "240px")}
				${row(32, "160px")}
			</div>
		`).appendTo(this.body);
	}
	hide_tree_skeleton() {
		this.$tree_skeleton && this.$tree_skeleton.remove();
		this.$tree_skeleton = null;
		this.tree && this.tree.wrapper.show();
	}
	make_tree() {
		// remember open nodes across rebuilds (see restore_expanded_nodes)
		this._expanded_labels = this.tree
			? Object.values(this.tree.nodes)
					.filter((node) => node.expanded && !node.is_root)
					.map((node) => node.label)
			: [];

		$(this.parent).find(".tree").remove();
		this.reset_search();
		this.show_tree_skeleton();

		var use_label = this.args[this.opts.root_label] || this.root_label || this.opts.root_label;
		var use_value = this.root_value;
		if (use_value == null) {
			use_value = use_label;
		}

		this.tree = new frappe.ui.Tree({
			parent: this.body,
			label: use_label,
			root_value: use_value,
			expandable: true,
			use_row_actions: !this.opts.do_not_make_page,
			row_style: this.opts.row_style,

			args: this.args,
			method: this.get_tree_nodes,

			// array of button props: {label, condition, click, btnClass, icon}
			toolbar: this.get_toolbar(),

			get_label: this.opts.get_label,
			on_render: this.opts.onrender,
			on_get_node: this.opts.on_get_node,
			on_node_render: (node, deep) => {
				this.hide_tree_skeleton();
				this.restore_expanded_nodes();
				this.opts.on_node_render && this.opts.on_node_render(node, deep);
			},
			on_click: (node) => {
				this.select_node(node);
			},
		});

		// the skeleton stands in until the first render
		if (this.$tree_skeleton) {
			this.tree.wrapper.hide();
		}

		cur_tree = this.tree;
		cur_tree.view_name = "Tree";
		this.post_render();
	}
	restore_expanded_nodes() {
		if (!this._expanded_labels?.length || !this.tree) return;
		this._expanded_labels = this._expanded_labels.filter((label) => {
			const node = this.tree.nodes[label];
			// not rendered yet — it may appear when an ancestor opens
			if (!node) return true;
			if (!node.expandable || node.expanded) return false;
			if (!document.body.contains(node.$tree_link[0])) return true;
			this.tree.load_children(node);
			return false;
		});
	}
	reset_search() {
		this.search_deep_loaded = false;
		this.$search_input && this.$search_input.val("");
		this.$search_empty_state && this.$search_empty_state.remove();
		this.tree && this.tree.wrapper.removeClass("tree-searching");
	}
	apply_search(txt) {
		txt = (txt || "").trim().toLowerCase();
		this.search_text = txt;
		if (!this.tree) return;

		this.$search_empty_state && this.$search_empty_state.remove();

		if (!txt) {
			this.tree.filter_nodes("");
			return;
		}

		const run = () => {
			// a newer keystroke superseded this one while the deep load ran
			if (this.search_text !== txt) return;

			const matches = this.tree.filter_nodes(txt);

			if (matches === 0) {
				this.$search_empty_state = $(
					frappe.ui.empty_state({
						icon: "search",
						title: __("No matching records"),
						description: __("Try a different search."),
					})
				).appendTo(this.body);
			}
		};

		if (this.search_deep_loaded) {
			run();
			return;
		}
		frappe.dom.freeze(__("Loading full tree..."));
		Promise.resolve(this.tree.load_children(this.tree.root_node, true))
			.then(() => {
				this.search_deep_loaded = true;
				run();
			})
			.finally(() => frappe.dom.unfreeze());
	}
	rebuild_tree() {
		let me = this;
		frappe.call({
			method: "frappe.utils.nestedset.rebuild_tree_for_doctype",
			args: {
				doctype: me.doctype,
			},
			callback: function (r) {
				if (!r.exc) {
					me.make_tree();
				}
			},
		});
	}

	post_render() {
		var me = this;
		me.opts.post_render && me.opts.post_render(me);
	}

	select_node(node) {
		var me = this;
		if (this.opts.click) {
			this.opts.click(node);
		}
		if (this.opts.view_template) {
			this.node_view.empty();
			$(
				frappe.render_template(me.opts.view_template, {
					data: node.data,
					doctype: me.doctype,
				})
			).appendTo(this.node_view);
		}
	}
	get_toolbar() {
		var me = this;

		var toolbar = [
			{
				label: __(me.can_write ? "Edit" : "Details"),
				icon: "pencil",
				// renders as the hover icon-button beside the label, so it
				// stays out of the row's ... menu
				inline: true,
				condition: function (node) {
					return !node.is_root && me.can_read;
				},
				click: function (node) {
					frappe.set_route("Form", me.doctype, node.label);
				},
			},
			{
				label: __("Add Child"),
				icon: "plus",
				condition: function (node) {
					return me.can_create && node.expandable && !node.hide_add;
				},
				click: function (node) {
					me.new_node();
				},
				btnClass: "hidden-xs",
			},
			{
				label: __("Move to..."),
				icon: "corner-down-right",
				condition: function (node) {
					return !node.is_root && me.can_write;
				},
				click: function (node) {
					me.move_node(node);
				},
			},
			{
				label: __("Rename"),
				icon: "text-cursor-input",
				// doctype-level allow_rename and user permission are constant
				// for every node — hide instead of repeating a disabled row
				condition: function (node) {
					return me.can_write && frappe.get_meta(me.doctype)?.allow_rename != 0;
				},
				get_disabled_reason: function (node) {
					if (node.is_root) return __("Root records can't be renamed");
				},
				click: function (node) {
					frappe.model.rename_doc(me.doctype, node.label, function (new_name) {
						node.$tree_link.find("a").text(new_name);
						node.label = new_name;
						me.tree.refresh();
					});
				},
				btnClass: "hidden-xs",
			},
			{
				label: __("Delete"),
				icon: "trash-2",
				danger: true,
				condition: function (node) {
					return me.can_delete;
				},
				get_disabled_reason: function (node) {
					if (node.is_root) return __("Root records can't be deleted");
				},
				click: function (node) {
					frappe.model.delete_doc(me.doctype, node.label, function () {
						node.parent.remove();
					});
				},
				btnClass: "hidden-xs",
			},
		];

		if (this.opts.toolbar && this.opts.extend_toolbar) {
			toolbar = toolbar.filter((btn) => {
				return !me.opts.toolbar.find((d) => d["label"] == btn["label"]);
			});
			return toolbar.concat(this.opts.toolbar);
		} else if (this.opts.toolbar && !this.opts.extend_toolbar) {
			return this.opts.toolbar;
		} else {
			return toolbar;
		}
	}
	move_node(node) {
		var me = this;

		// exclude the node's own subtree from the picker (a cycle otherwise);
		// the server's validate_loop stays the backstop
		let excluded = [node.label];
		const fetch_descendants = !node.expandable
			? Promise.resolve()
			: frappe.db.get_value(me.doctype, node.label, ["lft", "rgt"]).then((r) => {
					const { lft, rgt } = r.message || {};
					if (lft == null) return;
					return frappe.db
						.get_list(me.doctype, {
							filters: { lft: [">", lft], rgt: ["<", rgt] },
							limit: 0,
						})
						.then((rows) => {
							excluded = excluded.concat(rows.map((row) => row.name));
						});
			  });

		fetch_descendants.then(() => me.show_move_dialog(node, excluded));
	}
	show_move_dialog(node, excluded) {
		var me = this;
		// mirror the server (frappe.desk.treeview): nested sets may use a
		// custom parent field (e.g. Employee's reports_to)
		const parent_fieldname =
			frappe.get_meta(me.doctype)?.nsm_parent_field ||
			"parent_" + me.doctype.toLowerCase().replace(/ /g, "_").replace(/-/g, "_");

		const dialog = new frappe.ui.Dialog({
			title: __("Move {0}", [node.label]),
			fields: [
				{
					fieldtype: "Link",
					fieldname: "new_parent",
					label: __("New Parent"),
					options: me.doctype,
					reqd: 1,
					// half-typed text on close must not toast; submitted
					// values are validated server-side
					ignore_link_validation: 1,
					get_query: () => {
						// only groups (where the doctype has them), never the
						// node or its subtree
						const filters = { name: ["not in", excluded] };
						if (frappe.meta.has_field(me.doctype, "is_group")) {
							filters.is_group = 1;
						}
						Object.keys(me.args).forEach((key) => {
							if (
								key !== "doctype" &&
								me.args[key] &&
								frappe.meta.has_field(me.doctype, key)
							) {
								filters[key] = me.args[key];
							}
						});
						return { filters };
					},
				},
			],
			primary_action_label: __("Move"),
			primary_action(values) {
				dialog.hide();
				frappe.dom.freeze(__("Moving {0}", [node.label]));
				frappe.call({
					method: "frappe.client.set_value",
					args: {
						doctype: me.doctype,
						name: node.label,
						fieldname: parent_fieldname,
						value: values.new_parent,
					},
					callback: function (r) {
						if (r.exc) return;
						// re-render the branch it left and the one it joined
						node.parent_node && me.tree.load_children(node.parent_node);
						const target = me.tree.nodes[values.new_parent];
						if (target && target !== node.parent_node && target.loaded) {
							me.tree.load_children(target);
						}
						frappe.show_alert({
							message: __("{0} moved under {1}", [node.label, values.new_parent]),
							indicator: "green",
						});
					},
					always: function () {
						frappe.dom.unfreeze();
					},
				});
			},
		});
		dialog.show();
	}
	new_node() {
		var me = this;
		var node = me.tree.get_selected_node();

		if (!(node && node.expandable)) {
			frappe.msgprint(__("Select a group {0} first.", [__(me.doctype)]));
			return;
		}

		this.prepare_fields();

		// the dialog
		var d = new frappe.ui.Dialog({
			title: __("New {0}", [__(me.doctype)]),
			fields: me.fields,
		});

		var args = $.extend({}, me.args);
		args["parent_" + me.doctype.toLowerCase().replace(/ /g, "_").replace(/-/g, "_")] =
			me.args["parent"];

		d.set_value("is_group", 0);
		d.set_values(args);

		// create
		d.set_primary_action(__("Create New"), function () {
			var btn = this;
			var v = d.get_values();
			if (!v) return;

			v.parent = node.label;
			v.doctype = me.doctype;

			if (node.is_root) {
				v["is_root"] = node.is_root;
			} else {
				v["is_root"] = false;
			}

			d.hide();
			frappe.dom.freeze(__("Creating {0}", [me.doctype]));

			$.extend(args, v);
			return frappe.call({
				method: me.opts.add_tree_node || "frappe.desk.treeview.add_node",
				args: args,
				callback: function (r) {
					if (!r.exc) {
						me.tree.load_children(node);
					}
				},
				always: function () {
					frappe.dom.unfreeze();
				},
			});
		});
		d.show();
	}
	prepare_fields() {
		var me = this;

		this.fields = [
			{
				fieldtype: "Check",
				fieldname: "is_group",
				label: __("Is Group"),
				description: __(
					"Further sub-groups can only be created under records marked as 'Group'"
				),
			},
		];

		if (this.opts.fields) {
			// copy: the append below must not accumulate into app settings
			this.fields = this.opts.fields.slice();
		}

		this.ignore_fields = this.opts.ignore_fields || [];

		var mandatory_fields = $.map(me.opts.meta.fields, function (d) {
			return d.reqd || (d.bold && !d.read_only && !!d.is_virtual) ? d : null;
		});

		var opts_field_names = this.fields.map(function (d) {
			return d.fieldname;
		});

		mandatory_fields.map(function (d) {
			if (
				$.inArray(d.fieldname, me.ignore_fields) === -1 &&
				$.inArray(d.fieldname, opts_field_names) === -1
			) {
				me.fields.push(d);
			}
		});
	}
	print_tree() {
		if (!frappe.model.can_print(this.doctype)) {
			frappe.msgprint(__("You are not allowed to print this report"));
			return false;
		}
		// clone so the interactive chrome (hover action buttons) can be
		// stripped without touching the live tree — a static print page has
		// no use for buttons
		var $print_tree = $(".tree:visible").clone();
		$print_tree.find(".tree-actions").remove();
		var tree = $print_tree.html();
		var me = this;
		frappe.ui.get_print_settings(false, function (print_settings) {
			var title = __(me.docname || me.doctype);
			frappe.render_tree({ title: title, tree: tree, print_settings: print_settings });
			frappe.call({
				method: "frappe.core.doctype.access_log.access_log.make_access_log",
				args: {
					doctype: me.doctype,
					report_name: me.page_name,
					page: tree,
					method: "Print",
				},
			});
		});
	}
	set_primary_action() {
		var me = this;
		if (!this.opts.disable_add_node && this.can_create) {
			// same primary action as the list views: "Add {doctype}", short
			// "Add" below the md breakpoint, ctrl+b shortcut
			const primary_action = () => me.new_node();
			me.page.set_primary_action(
				{
					label: __("Add {0}", [__(this.doctype)], "Primary action in tree view"),
					short_label: __("Add"),
				},
				primary_action,
				"plus"
			);
			frappe.ui.keys.add_shortcut({
				shortcut: "ctrl+b",
				action: () => {
					primary_action();
					return true;
				},
				description: __(
					"Create a new document",
					null,
					"Description of a tree view shortcut"
				),
				page: this.page,
			});
		}
	}
	set_menu_item() {
		var me = this;

		this.menu_items = [
			{
				label: __("Print"),
				action: function () {
					me.print_tree();
				},
			},
		];

		// the view switcher covers navigation and the header icon covers
		// reload; only fall back to menu items when the switcher is disabled
		if (!this.views_list) {
			this.menu_items.unshift({
				label: __("View List"),
				action: function () {
					frappe.set_route(["List", me.doctype, "List"]);
				},
			});
		}

		if (
			frappe.user.has_role("System Manager") &&
			frappe.meta.has_field(me.doctype, "lft") &&
			frappe.meta.has_field(me.doctype, "rgt")
		) {
			this.menu_items.push({
				label: __("Rebuild Tree"),
				action: function () {
					me.rebuild_tree();
				},
			});
		}

		if (me.opts.menu_items) {
			me.menu_items.push.apply(me.menu_items, me.opts.menu_items);
		}

		$.each(me.menu_items, function (i, menu_item) {
			var has_perm = true;
			if (menu_item["condition"]) {
				// apps historically pass condition as an eval'd string; new
				// code should pass a function
				has_perm =
					typeof menu_item["condition"] === "function"
						? menu_item["condition"]()
						: eval(menu_item["condition"]);
			}

			if (has_perm) {
				me.page.add_menu_item(menu_item["label"], menu_item["action"]);
			}
		});
	}
};
