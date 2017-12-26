// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.ui');

frappe.ui.Tree = class {
	constructor({
		parent, label, icon_set, toolbar, expandable,

		get_nodes,
		get_nodes_args,
		get_label,
		on_render,
		on_click
	}) {
		$.extend(this, arguments[0]);
		this.setup_treenode_class();
		this.nodes = {};
		this.wrapper = $('<div class="tree">').appendTo(this.parent);
		this.root_node = new this.TreeNode({
			parent: this.wrapper,
			label: this.label,
			parent_label: null,
			expandable: true,
			is_root: true,
			data: {
				value: this.label
			}
		});
		this.expand_node(this.root_node);
	}

	setup_treenode_class() {
		let tree = this;
		this.TreeNode = class {
			constructor({
				parent, label,
				parent_label,
				expandable,
				is_root,
				data
			}) {
				$.extend(this, arguments[0]);
				this.loaded = 0;
				this.expanded = 0;
				if(this.parent_label){
					this.parent_node = tree.nodes[this.parent_label];
				}

				tree.nodes[this.label] = this;
				tree.make_node_element(this);
				tree.on_render && tree.on_render(this);
			}
		}
	}

	make_node_element(node) {
		node.$tree_link = $('<span class="tree-link">')
			.attr('data-label', node.label)
			.data('node', node)
			.appendTo(node.parent);

		node.$ul = $('<ul class="tree-children">')
			.hide().appendTo(node.parent);

		this.make_icon_and_label(node);
		if(this.toolbar) {
			node.$toolbar = this.get_toolbar(node).insertAfter(node.$tree_link);
		}
	}

	toggle_node(node) {
		if(node.expandable && this.get_nodes && !node.loaded) {
			return this.load_children(node);
		}

		// expand children
		if(node.$ul) {
			if(node.$ul.children().length) {
				node.$ul.toggle(!node.expanded);
			}

			// open close icon
			node.$tree_link.find('i').removeClass();
			if(!node.expanded) {
				node.$tree_link.find('i').addClass('fa fa-fw fa-folder-open text-muted');
			} else {
				node.$tree_link.find('i').addClass('fa fa-fw fa-folder text-muted');
			}
		}
	}

	add_node(node, data) {
		var $li = $('<li class="tree-node">');
		// if(this.drop) $li.draggable({revert:true});

		return new this.TreeNode({
			parent: $li.appendTo(node.$ul),
			parent_label: node.label,
			label: data.value,
			title: data.title,
			expandable: data.expandable,
			data: data
		});
	}

	reload_node(node) {
		this.load_children(node);
	}

	refresh() {
		this.selected_node.parent_node &&
			this.load_children_deep(this.selected_node.parent_node);
	}

	load_children(node, deep=false) {
		deep ? this.load_children_deep(node)
		: this.load_children_shallow(node);
	}

	load_children_shallow(node) {
		var args = $.extend(this.get_nodes_args || {}, {
			parent: node.data.value
		});

		args.is_root = node.is_root;

		return new Promise(resolve => {
			frappe.call({
				method: this.get_nodes,
				args: args,
				callback: (r) => {
					this.render_node_children(node, r.message);
					resolve();
				}
			})
		});
	}

	load_children_deep(node) {
		let args = $.extend({}, this.get_nodes_args);

		args.is_root = node.is_root;
		args.parent = node.data.value;
		args.tree_method = this.get_nodes;

		return new Promise(resolve => {
			frappe.call({
				method: 'frappe.desk.treeview.get_all_nodes',
				args: args,
				callback: (r) => {
					$.each(r.message, (i, d) => {
						this.render_node_children(this.nodes[d.parent], d.data);
					});
					resolve();
				}
			})
		});
	}

	render_node_children(node, data_set) {
		if(node.$ul.is(':empty')) {
			node.$ul.empty();
			if (data_set) {
				$.each(data_set, (i, data) => {
					var child_node = this.add_node(node, data);
					child_node.$tree_link
						.data('node-data', data)
						.data('node', child_node);
				});
			}
		}

		node.expanded = false;

		// As children loaded
		node.loaded = true;
		this.expand_node(node);
	}

	get_selected_node() {
		return this.selected_node;
	}

	set_selected_node(node) {
		this.selected_node = node;
		this.on_click && this.on_click();
	}

	on_node_click(node) {
		this.expand_node(node);

		// Activate
		frappe.ui.utils.activate(this.wrapper, node.$tree_link, 'tree-link');
		if(node.$toolbar) this.show_toolbar(node);
	}

	expand_node(node) {
		this.set_selected_node(node);
		if(node.expandable) {
			this.toggle_node(node);
		}
		this.select_link(node);
	}

	select_link(node) {
		// select this link
		this.wrapper.find('.selected')
			.removeClass('selected');
		node.$tree_link.toggleClass('selected');
		node.expanded = !node.expanded;

		node.parent.toggleClass('opened', node.expanded);
	}

	show_toolbar(node) {
		if(this.cur_toolbar)
			$(this.cur_toolbar).hide();
		this.cur_toolbar = node.$toolbar;
			node.$toolbar.show();
	}

	toggle() {
		this.get_selected_node().toggle();
	}

	get_node_label(node) {
		if(this.get_label) {
			return this.get_label(node);
		}
		if (node.title && node.title != node.label) {
			return __(node.title) + ` <span class='text-muted'>(${node.label})</span>`;
		} else {
			return __(node.title || node.label);
		}
	}

	make_icon_and_label(node) {
		let icon_html = '';
		if(this.icon_set) {
			if(node.expandable) {
				icon_html = `<i class="${this.icon_set.closed} text-muted" style="font-size: 14px;"></i>`;
			} else {
				icon_html = `<i class="${this.icon_set.leaf} text-extra-muted"></i>`;
			}
		};

		$(icon_html).appendTo(node.$tree_link);
		$(`<a class="tree-label grey h6"> ${this.get_node_label(node)}</a>`).appendTo(node.$tree_link);

		node.$tree_link.on('click', () => {
			setTimeout(() => {this.on_node_click(node);}, 100);
		});
	}

	get_toolbar(node) {
		let $toolbar = $('<span class="tree-node-toolbar btn-group"></span>').hide();

		Object.keys(this.toolbar).map(key => {
			obj = this.toolbar[key];
			if(!obj.label) return;
			if(obj.condition && !obj.condition(node)) return;

			var label = obj.get_label ? obj.get_label() : obj.label;
			var $link = $("<button class='btn btn-default btn-xs'></button>")
				.html(label)
				.addClass('tree-toolbar-button ' + (obj.btnClass || ''))
				.appendTo($toolbar);
			$link.on('click', () => { obj.click($link, node); return false; });
		});

		return $toolbar;
	}
}
