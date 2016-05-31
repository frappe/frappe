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
		this.wrapper = $('<div class="tag-line">').appendTo(this.parent)
		this.$tags = $('<ul>').prependTo(this.wrapper);
		this.$tags.tagit({
			animate: false,
			allowSpaces: true,
			placeholderText: __('Add a tag') + "...",
			onTagAdded: function(ev, tag) {
				if(me.initialized && !me.refreshing) {
					tag.find('.tagit-label').text(toTitle(tag.find('.tagit-label').text()));
					var tag = tag.find('.tagit-label').text();
					return frappe.call({
						method: 'frappe.desk.tags.add_tag',
						args: me.get_args(tag),
						callback: function(r) {
							var user_tags = me.user_tags.split(",");
							user_tags.push(tag)
							me.user_tags = user_tags.join(",");
							me.on_change && me.on_change(me.user_tags);
						}
					});
				}
			},
			onTagRemoved: function(ev, tag) {
				if(!me.refreshing) {
					var tag = tag.find('.tagit-label').text();
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
		this.setup_autocomplete();
	},
	setup_autocomplete: function() {
		var me = this;
		this.wrapper.find("input").autocomplete({
			minLength: 0,
			minChars: 0,
			source: function(request, response) {
				frappe.call({
					method:"frappe.desk.tags.get_tags",
					args:{
						doctype: me.frm.doctype,
						txt: request.term.toLowerCase(),
						cat_tags:JSON.stringify(me.sidebar_stats.get_cat_tags())
					},
					callback: function(r) {
						response(r.message);
					}
				});
			},
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
			me.$tags.tagit("removeAll");

			if(user_tags) {
				$.each(user_tags.split(','), function(i, v) {
					if(v) { me.$tags.tagit("createTag", v); }
				});
			}
		} catch(e) {
			me.refreshing = false;
			// wtf bug
			setTimeout( function() { me.refresh(); }, 100);
		}
		me.refreshing = false;

	}
})
