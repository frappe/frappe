// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.ui.TagEditor = Class.extend({
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
		this.$w = $('<div class="tag-line">').appendTo(this.parent)
		this.$tags = $('<ul>').prependTo(this.$w).tagit({
			animate: false,
			allowSpaces: true,
			placeholderText: 'Add Tag',
			onTagAdded: function(ev, tag) {
				if(me.initialized && !me.refreshing) {
					return wn.call({
						method: 'webnotes.widgets.tags.add_tag',
						args: me.get_args(tag.find('.tagit-label').text())
					});					
				}
			},
			onTagRemoved: function(ev, tag) {
				if(!me.refreshing) {
					return wn.call({
						method: 'webnotes.widgets.tags.remove_tag',
						args: me.get_args(tag.find('.tagit-label').text())
					});
				}
			}
		});	
		this.refresh(this.user_tags);
		this.initialized = true;
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

		me.refreshing = true;
		me.$tags.tagit("removeAll");

		if(!user_tags && this.frm) 
			user_tags = wn.model.get_value(this.frm.doctype, this.frm.docname, "_user_tags");
		
		if(user_tags) {
			$.each(user_tags.split(','), function(i, v) {
				me.$tags.tagit("createTag", v);
			});
		}
		me.refreshing = false;
		
	}
})