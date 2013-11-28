// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for license information please see license.txt

// constructor: parent, label, method, args
wn.ui.Tree = Class.extend({
	init: function(args) {
		$.extend(this, args);
		this.nodes = {};
		this.$w = $('<div class="tree">').appendTo(this.parent);
		this.rootnode = new wn.ui.TreeNode({
			tree: this, 
			parent: this.$w, 
			label: this.label, 
			expandable: true
		});
		this.set_style();
	},
	set_style: function() {
		wn.dom.set_style("\
			.tree li { list-style: none; }\
			.tree ul { margin-top: 2px; }\
			.tree-link { cursor: pointer; }\
		")
	}
})

wn.ui.TreeNode = Class.extend({
	init: function(args) {
		var me = this;
		$.extend(this, args);
		this.loaded = false;
		this.expanded = false;
		this.tree.nodes[this.label] = this;
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
			.appendTo(this.parent);
		
		// label with icon
		var icon_html = '<i class="icon-file"></i>';
		if(this.expandable) {
			icon_html = '<i class="icon-folder-close"></i>';
		}
		$(icon_html + ' <a class="tree-label">' + this.label + "</a>").
			appendTo(this.$a);
		
		if(this.tree.onrender) {
			this.tree.onrender(this);
		}
	},
	selectnode: function() {
		// expand children
		if(this.$ul) {
			this.$ul.toggle();
			
			// open close icon
			this.$a.find('i').removeClass();
			if(this.$ul.css('display').toLowerCase()=='block') {
				this.$a.find('i').addClass('icon-folder-open');
			} else {
				this.$a.find('i').addClass('icon-folder-close');				
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
	addnode: function(data) {
		if(!this.$ul) {
			this.$ul = $('<ul>').toggle(false).appendTo(this.parent);
		}
		return new wn.ui.TreeNode({
			tree:this.tree, 
			parent: $('<li>').appendTo(this.$ul), 
			label: data.value, 
			expandable: data.expandable,
			data: data
		});
	},
	load: function() {
		var me = this;
		args = $.extend(this.tree.args, {
			parent: this.label
		});

		$(me.$a).set_working();

		return wn.call({
			method: this.tree.method,
			args: args,
			callback: function(r) {
				$(me.$a).done_working();

				if (r.message) {
					$.each(r.message, function(i, v) {
						node = me.addnode(v);
						node.$a.data('node-data', v);
					});
				}
				
				me.loaded = true;
				
				// expand
				me.selectnode();
			}
		})
	}	
})