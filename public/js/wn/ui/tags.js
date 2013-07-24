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
				if(me.initialized) {
					wn.call({
						method: 'webnotes.widgets.tags.add_tag',
						args: me.get_args(tag.find('.tagit-label').text())
					});					
				}
			},
			onTagRemoved: function(ev, tag) {
				wn.call({
					method: 'webnotes.widgets.tags.remove_tag',
					args: me.get_args(tag.find('.tagit-label').text())
				});
			}
		});	
		this.refresh(this.user_tags);
		this.initialized = true;
	},
	get_args: function(tag) {
		return {
			tag: tag,
			dt: this.doctype,
			dn: this.docname,
		}
	},
	refresh: function(user_tags) {
		var me = this;
		
		if(!user_tags) 
			user_tags = wn.model.get_value(this.doctype, this.docname, "_user_tags");
		
		if(user_tags) {
			$.each(user_tags.split(','), function(i, v) {
				me.$tags.tagit("createTag", v);
			});
		}
	}
})