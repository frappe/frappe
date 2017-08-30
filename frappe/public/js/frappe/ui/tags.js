// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.TagEditor = Class.extend({
	init: function(opts) {
		/* docs:
		Arguments

		- parent
		- user_tags
		- doctype
		- docname
		*/
		$.extend(this, opts);
		var me = this;
		this.wrapper = $('<div class="tag-line" style="position: relative">').appendTo(this.parent)
		if(!this.wrapper.length) return;
		var id = frappe.dom.set_unique_id(this.wrapper);
		this.taggle = new Taggle(id, {
			placeholder: __('Add a tag') + "...",
			onTagAdd: function(e, tag) {
				if(me.initialized && !me.refreshing) {
					tag = toTitle(tag);
					return frappe.call({
						method: 'frappe.desk.tags.add_tag',
						args: me.get_args(tag),
						callback: function(r) {
							var user_tags = me.user_tags ? me.user_tags.split(",") : [];
							user_tags.push(tag)
							me.user_tags = user_tags.join(",");
							me.on_change && me.on_change(me.user_tags);
						}
					});
				}
			},
			onTagRemove: function(e, tag) {
				if(!me.refreshing) {
					return frappe.call({
						method: 'frappe.desk.tags.remove_tag',
						args: me.get_args(tag),
						callback: function(r) {
							var user_tags = me.user_tags.split(",");
							user_tags.splice(user_tags.indexOf(tag), 1);
							me.user_tags = user_tags.join(",");
							me.on_change && me.on_change(me.user_tags);
						}
					});
				}
			}
		});
		if (!this.user_tags) {
			this.user_tags = "";
		}
		this.initialized = true;
		this.refresh(this.user_tags);
		this.setup_awesomplete();
	},
	setup_awesomplete: function() {
		var me = this;
		var $input = this.wrapper.find("input.taggle_input");
		var input = $input.get(0);
		this.awesomplete = new Awesomplete(input, {
			minChars: 0,
			maxItems: 99,
			list: []
		});
		$input.on("awesomplete-open", function(e){
			$input.attr('state', 'open');
		});
		$input.on("awesomplete-close", function(e){
			$input.attr('state', 'closed');
		});
		$input.on("input", function(e) {
			var value = e.target.value;
			frappe.call({
				method:"frappe.desk.tags.get_tags",
				args:{
					doctype: me.frm.doctype,
					txt: value.toLowerCase(),
					cat_tags: me.list_sidebar ?
						JSON.stringify(me.list_sidebar.get_cat_tags()) : '[]'
				},
				callback: function(r) {
					me.awesomplete.list = r.message;
				}
			});
		});
		$input.on("focus", function(e) {
			if($input.attr('state') != 'open') {
				$input.trigger("input");
			}
		});
	},
	get_args: function(tag) {
		return {
			tag: tag,
			dt: this.frm.doctype,
			dn: this.frm.docname,
		}
	},
	refresh: function(user_tags) {
		var me = this;
		if(!me.initialized || me.refreshing)
			return;

		me.refreshing = true;
		try {
			me.taggle.removeAll();
			if(user_tags) {
				me.taggle.add(user_tags.split(','));
			}
		} catch(e) {
			me.refreshing = false;
			// wtf bug
			setTimeout( function() { me.refresh(); }, 100);
		}
		me.refreshing = false;

	}
})
