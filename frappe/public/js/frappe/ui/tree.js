// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui");

frappe.ui.Tree = class {
	constructor({
		parent,
		label,
		root_value,
		icon_set,
		toolbar,
		expandable,
		with_skeleton = 1, // eslint-disable-line

		args,
		method,
		get_label,
		on_render,
		on_click, // eslint-disable-line
	}) {
		$.extend(this, arguments[0]);
		if (root_value == null) {
			this.root_value = label;
		}
		this.setup_treenode_class();
		this.nodes = {};
		this.wrapper = $('<div class="tree">').appendTo(this.parent);
		if (with_skeleton) this.wrapper.addClass("with-skeleton");

		if (!icon_set) {
			this.icon_set = {
				open: frappe.utils.icon("folder-open", "md"),
				closed: frappe.utils.icon("folder-normal", "md"),
				leaf: frappe.utils.icon("primitive-dot", "xs"),
			};
		}

		this.setup_root_node();
	}

	get_nodes(value, is_root) {
		var args = Object.assign({}, this.args);
		args.parent = value;
		args.is_root = is_root;

		return new Promise((resolve) => {
			frappe.call({
				method: this.method,
				args: args,
				callback: (r) => {
					this.on_get_node && this.on_get_node(r.message);
					resolve(r.message);
				},
			});
		});
	}

	get_all_nodes(value, is_root, label) {
		var args = Object.assign({}, this.args);
		args.label = label || value;
		args.parent = value;
		args.is_root = is_root;

		args.tree_method = this.method;

		return new Promise((resolve) => {
			frappe.call({
				method: "frappe.desk.treeview.get_all_nodes",
				args: args,
				callback: (r) => {
					this.on_get_node && this.on_get_node(r.message, true);
					resolve(r.message);
				},
			});
		});
	}

	setup_treenode_class() {
		let tree = this;
		this.TreeNode = class {
			constructor({
				parent,
				label,
				parent_label,
				expandable,
				is_root,
				data, // eslint-disable-line
			}) {
				$.extend(this, arguments[0]);
				this.loaded = 0;
				this.expanded = 0;
				if (this.parent_label) {
					this.parent_node = tree.nodes[this.parent_label];
				}

				tree.nodes[this.label] = this;
				tree.make_node_element(this);
				tree.on_render && tree.on_render(this);
			}
		};
	}

	setup_root_node() {
		this.root_node = new this.TreeNode({
			parent: this.wrapper,
			label: this.label,
			parent_label: null,
			expandable: true,
			is_root: true,
			data: {
				value: this.root_value,
			},
		});
		this.expand_node(this.root_node, false);
	}

	refresh() {
		this.selected_node.parent_node && this.load_children(this.selected_node.parent_node, true);
	}

	make_node_element(node) {
		node.$tree_link = $('<span class="tree-link">')
			.attr("data-label", node.label)
			.data("node", node)
			.appendTo(node.parent);

		node.$ul = $('<ul class="tree-children">').hide().appendTo(node.parent);

		this.make_icon_and_label(node);
		if (this.toolbar) {
			node.$toolbar = this.get_toolbar(node).insertAfter(node.$tree_link);
		}
	}

	add_node(node, data) {
		var $li = $('<li class="tree-node">');

		return new this.TreeNode({
			parent: $li.appendTo(node.$ul),
			parent_label: node.label,
			label: data.value,
			title: data.title,
			expandable: data.expandable,
			data: data,
		});
	}

	reload_node(node) {
		return this.load_children(node);
	}

	toggle() {
		this.get_selected_node().toggle();
	}

	get_selected_node() {
		return this.selected_node;
	}

	set_selected_node(node) {
		this.selected_node = node;
	}

	load_children(node, deep = false) {
		const value = node.data.value,
			is_root = node.is_root;

		return deep
			? frappe.run_serially([
					() => this.get_all_nodes(value, is_root, node.label),
					(data_list) => this.render_children_of_all_nodes(data_list),
					() => this.set_selected_node(node),
			  ])
			: frappe.run_serially([
					() => this.get_nodes(value, is_root),
					(data_set) => this.render_node_children(node, data_set),
					() => this.set_selected_node(node),
			  ]);
	}

	render_children_of_all_nodes(data_list) {
		data_list.map((d) => this.render_node_children(this.nodes[d.parent], d.data));
	}

	render_node_children(node, data_set) {
		node.$ul.empty();
		if (data_set) {
			$.each(data_set, (i, data) => {
				var child_node = this.add_node(node, data);
				child_node.$tree_link.data("node-data", data).data("node", child_node);
			});
		}

		node.expanded = false;

		// As children loaded
		node.loaded = true;
		this.expand_node(node);
	}

	on_node_click(node) {
		this.expand_node(node);
		frappe.dom.activate(this.wrapper, node.$tree_link, "tree-link");
		if (node.$toolbar) this.show_toolbar(node);
	}

	expand_node(node, click = true) {
		this.set_selected_node(node);

		if (click) {
			this.on_click && this.on_click(node);
		}

		if (node.expandable) {
			this.toggle_node(node);
		}
		this.select_link(node);

		node.expanded = !node.expanded;
		node.parent.toggleClass("opened", node.expanded);
	}

	toggle_node(node) {
		if (node.expandable && this.get_nodes && !node.loaded) {
			return this.load_children(node);
		}

		// expand children
		if (node.$ul) {
			if (node.$ul.children().length) {
				node.$ul.toggle(!node.expanded);
			}

			// open close icon
			if (this.icon_set) {
				if (!node.expanded) {
					node.$tree_link.find(".icon").parent().html(this.icon_set.open);
				} else {
					node.$tree_link
						.find(".icon")
						.parent()
						.addClass("node-parent")
						.html(this.icon_set.closed);
				}
			}
		}
	}

	select_link(node) {
		this.wrapper.find(".selected").removeClass("selected");
		node.$tree_link.toggleClass("selected");
	}

	show_toolbar(node) {
		if (this.cur_toolbar) $(this.cur_toolbar).hide();
		this.cur_toolbar = node.$toolbar;
		node.$toolbar.show();
	}

	get_node_label(node) {
		if (this.get_label) {
			return this.get_label(node);
		}
		if (node.title && node.title != node.label) {
			return __(node.title) + ` <span class='text-muted'>(${node.label})</span>`;
		} else {
			return __(node.title || node.label);
		}
	}

	make_icon_and_label(node) {
		let icon_html = "";
		if (this.icon_set) {
			if (node.expandable) {
				icon_html = `<span class="node-parent">${this.icon_set.closed}</span>`;
			} else {
				icon_html = `<span>${this.icon_set.leaf}</span>`;
			}
		}

		$(icon_html).appendTo(node.$tree_link);
		$(`<a class="tree-label"> ${this.get_node_label(node)}</a>`).appendTo(node.$tree_link);

		node.$tree_link.on("click", () => {
			setTimeout(() => {
				this.on_node_click(node);
			}, 100);
		});

		node.$tree_link.hover(
			function () {
				$(this).parent().addClass("hover-active");
			},
			function () {
				$(this).parent().removeClass("hover-active");
			}
		);
	}

	get_toolbar(node) {
		let $toolbar = $('<span class="tree-node-toolbar btn-group"></span>').hide();

		Object.keys(this.toolbar).map((key) => {
			let obj = this.toolbar[key];
			if (!obj.label) return;
			if (obj.condition && !obj.condition(node)) return;

			var label = obj.get_label ? obj.get_label() : obj.label;
			var $link = $("<button class='btn btn-default btn-xs'></button>")
				.html(label)
				.addClass("tree-toolbar-button " + (obj.btnClass || ""))
				.appendTo($toolbar);
			$link.on("click", () => {
				obj.click(node);
			});
		});

		return $toolbar;
	}
};
