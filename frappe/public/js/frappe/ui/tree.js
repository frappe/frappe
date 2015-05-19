// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for license information please see license.txt

// constructor: parent, label, method, args
frappe.ui.Tree = Class.extend({
	init: function(args) {
		$.extend(this, args);
		this.nodes = {};
		this.$w = $('<div class="tree">').appendTo(this.parent);
		this.rootnode = new frappe.ui.TreeNode({
			tree: this,
			parent: this.$w,
			label: this.label,
			parent_label: null,
			expandable: true,
			root: true,
			data: {
				value: this.label,
				expandable: true
			}
		});
		this.rootnode.toggle();
	},
	get_selected_node: function() {
		return this.selected_node;
	},
	toggle: function() {
		this.get_selected_node().toggle();
	}
})

frappe.ui.TreeNode = Class.extend({
	init: function(args) {
		$.extend(this, args);
		this.loaded = false;
		this.expanded = false;
		this.tree.nodes[this.label] = this;
		if(this.parent_label)
			this.parent_node = this.tree.nodes[this.parent_label];

		this.make();
		this.setup_drag_drop();

		if(this.tree.onrender) {
			this.tree.onrender(this);
		}
	},
	make: function() {
		var me = this;
		this.$a = $('<span class="tree-link">')
			.click(function(event) {
				me.tree.selected_node = me;
				me.tree.$w.find(".tree-link.active").removeClass("active");
				me.$a.addClass("active");
				if(me.tree.toolbar) {
					me.show_toolbar();
				}
				if(me.toggle_on_click) {
					me.toggle();
				}
				if(me.tree.click)
					me.tree.click(this);
			})
			.bind('reload', function() { me.reload(); })
			.data('label', this.label)
			.data('node', this)
			.appendTo(this.parent);

		this.$ul = $('<ul class="tree-children">')
			.toggle(false).appendTo(this.parent);

		this.make_icon();

	},
	make_icon: function() {
		// label with icon
		var me= this;
		var icon_html = '<i class="icon-fixed-width octicon octicon-primitive-dot text-extra-muted"></i>';
		if(this.expandable) {
			icon_html = '<i class="icon-fixed-width icon-folder-close text-muted"></i>';
		}
		$(icon_html + ' <a class="tree-label grey h6">' + __(this.label) + "</a>").
			appendTo(this.$a);

		this.$a.find('i').click(function() {
			setTimeout(function() { me.toolbar.find(".btn-expand").click(); }, 100);
		});
	},
	toggle: function(callback) {
		if(this.expandable && this.tree.method && !this.loaded) {
			this.load(callback)
		} else {
			this.toggle_node(callback);
		}
	},
	show_toolbar: function() {
		if(this.tree.cur_toolbar)
			$(this.tree.cur_toolbar).toggle(false);

		if(!this.toolbar)
			this.make_toolbar();

		this.tree.cur_toolbar = this.toolbar;
		this.toolbar.toggle(true);
	},
	make_toolbar: function() {
		var me = this;
		this.toolbar = $('<span class="tree-node-toolbar btn-group"></span>').insertAfter(this.$a);

		$.each(this.tree.toolbar, function(i, item) {
			if(item.toggle_btn) {
				item = {
					condition: function() { return me.expandable; },
					get_label: function() { return me.expanded ? __("Collapse") : __("Expand") },
					click:function(node, btn) {
						node.toggle(function() {
							$(btn).html(node.expanded ? __("Collapse") : __("Expand"));
						});
					},
					btnClass: "btn-expand"
				}
			}
			if(item.condition) {
				if(!item.condition(me)) return;
			}
			var label = item.get_label ? item.get_label() : item.label;
			var link = $("<button class='btn btn-default btn-xs'></button>")
				.html(label)
				.appendTo(me.toolbar)
				.click(function() { item.click(me, this); return false; });

			if(item.btnClass) link.addClass(item.btnClass);
		})

	},
	setup_drag_drop: function() {
		// experimental
		var me = this;
		if(this.tree.drop && this.parent_label) {
			this.$ul.droppable({
				hoverClass: "tree-hover",
				greedy: true,
				drop: function(event, ui) {
					event.preventDefault();
					var dragged_node = $(ui.draggable).find(".tree-link:first").data("node");
					var dropped_node = $(this).parent().find(".tree-link:first").data("node");
					me.tree.drop(dragged_node, dropped_node, $(ui.draggable), $(this));
					return false;
				}
			});
		}

	},
	addnode: function(data) {
		var $li = $('<li class="tree-node">');
		if(this.tree.drop) $li.draggable({revert:true});
		return new frappe.ui.TreeNode({
			tree:this.tree,
			parent: $li.appendTo(this.$ul),
			parent_label: this.label,
			label: data.value,
			expandable: data.expandable,
			data: data
		});
	},
	toggle_node: function(callback) {
		// expand children
		if(this.$ul) {
			if(this.$ul.children().length) {
				this.$ul.toggle(!this.expanded);
			}

			// open close icon
			this.$a.find('i').removeClass();
			if(!this.expanded) {
				this.$a.find('i').addClass('icon-fixed-width icon-folder-open text-muted');
			} else {
				this.$a.find('i').addClass('icon-fixed-width icon-folder-close text-muted');
			}
		}

		// select this link
		this.tree.$w.find('.selected')
			.removeClass('selected');
		this.$a.toggleClass('selected');
		this.expanded = !this.expanded;
		if(callback) callback();
	},
	reload: function() {
		this.load();
	},
	load: function(callback) {
		var me = this;
		args = $.extend(this.tree.args || {}, {
			parent: this.data ? this.data.value : null
		});

		return frappe.call({
			method: this.tree.method,
			args: args,
			callback: function(r) {
				me.$ul.empty();
				if (r.message) {
					$.each(r.message, function(i, v) {
						node = me.addnode(v);
						node.$a
							.data('node-data', v)
							.data('node', node);
					});
				}

				if(!me.expanded)
					me.toggle_node(callback);
				me.loaded = true;

			}
		})
	}
})
