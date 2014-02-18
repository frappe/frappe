// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
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
			expandable: true
		});
		this.set_style();
	},
	get_selected_node: function() {
		return this.$w.find('.tree-link.selected').data('node');
	},
	set_style: function() {
		frappe.dom.set_style("\
			.tree li { list-style: none; }\
			.tree ul { margin-top: 2px; }\
			.tree-link { cursor: pointer; }\
			.tree-hover { background-color: #eee; min-height: 20px; border: 1px solid #ddd; }\
		")
	}
})

frappe.ui.TreeNode = Class.extend({
	init: function(args) {
		var me = this;
		$.extend(this, args);
		this.loaded = false;
		this.expanded = false;
		this.tree.nodes[this.label] = this;
		if(this.parent_label)
			this.parent_node = this.tree.nodes[this.parent_label];
		this.$a = $('<span class="tree-link">')
			.click(function() { 
				if(me.expandable && me.tree.method && !me.loaded) {
					me.load()
				} else {
					me.selectnode();
				}
				if(me.tree.click) me.tree.click(this);
			})
			.bind('reload', function() { me.reload(); })
			.data('label', this.label)
			.data('node', this)
			.appendTo(this.parent);

		this.$ul = $('<ul class="tree-children">')
			.css({"min-height": "5px"})
			.toggle(false).appendTo(this.parent);
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
			
		// label with icon
		var icon_html = '<i class="icon-fixed-width icon-file"></i>';
		if(this.expandable) {
			icon_html = '<i class="icon-fixed-width icon-folder-close"></i>';
		}
		$(icon_html + ' <a class="tree-label">' + this.label + "</a>").
			appendTo(this.$a);
		
		if(this.tree.onrender) {
			this.tree.onrender(this);
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
	selectnode: function() {
		// expand children
		if(this.$ul) {
			this.$ul.toggle();
			
			// open close icon
			this.$a.find('i').removeClass();
			if(this.$ul.css('display').toLowerCase()=='block') {
				this.$a.find('i').addClass('icon-fixed-width icon-folder-open');
			} else {
				this.$a.find('i').addClass('icon-fixed-width icon-folder-close');
			}
		}
		
		// select this link
		this.tree.$w.find('.selected')
			.removeClass('selected');
		this.$a.toggleClass('selected');
		this.expanded = !this.expanded;
	},
	reload: function() {
		if(this.expanded) {
			this.$a.click(); // collapse
		}
		if(this.$ul) {
			this.$ul.empty();
		}
		this.load();
	},
	load: function() {
		var me = this;
		args = $.extend(this.tree.args || {}, {
			parent: this.data ? this.data.value : null
		});

		$(me.$a).set_working();

		return frappe.call({
			method: this.tree.method,
			args: args,
			callback: function(r) {
				$(me.$a).done_working();

				if (r.message) {
					$.each(r.message, function(i, v) {
						node = me.addnode(v);
						node.$a
							.data('node-data', v)
							.data('node', node);
					});
				}
				
				me.loaded = true;
				
				// expand
				me.selectnode();
			}
		})
	}
})