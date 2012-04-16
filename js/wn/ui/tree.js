// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
//

// tree with expand on ajax
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
		this.$a = $('<a class="tree-link">')
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
		if(this.expandable) {
			this.$a.append('<i class="icon-folder-close"></i> ' + this.label);
		} else {
			this.$a.append('<i class="icon-file"></i> ' + this.label);
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
		this.tree.$w.find('a.selected')
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
	addnode: function(label, expandable) {
		if(!this.$ul) {
			this.$ul = $('<ul>').toggle(false).appendTo(this.parent);
		}
		return new wn.ui.TreeNode({
			tree:this.tree, 
			parent: $('<li>').appendTo(this.$ul), 
			label: label, 
			expandable: expandable
		});
	},
	load: function() {
		var me = this;
		args = $.extend(this.tree.args, {
			parent: this.label
		});

		$(me.$a).set_working();

		wn.call({
			method: this.tree.method,
			args: args,
			callback: function(r) {
				$(me.$a).done_working();

				$.each(r.message, function(i, v) {
					node = me.addnode(v.value || v, v.expandable);
					node.$a.data('node-data', v);
				});
				
				me.loaded = true;
				
				// expand
				me.selectnode();
			}
		})
	}	
})