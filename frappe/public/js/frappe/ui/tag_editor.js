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

		this.setup_tags();

		if (!this.user_tags) {
			this.user_tags = "";
		}
		this.initialized = true;
		this.refresh(this.user_tags);
	},
	setup_tags: function() {
		var me = this;

		// hidden form, does not have parent
		if (!this.parent) {
			return;
		}

		this.wrapper = this.parent;
		if (!this.wrapper.length) return;

		this.tags = new frappe.ui.Tags({
			parent: this.wrapper,
			placeholder: __("Add a tag ..."),
			onTagAdd: (tag) => {
				if(me.initialized && !me.refreshing) {
					return frappe.call({
						method: "frappe.desk.doctype.tag.tag.add_tag",
						args: me.get_args(tag),
						callback: function(r) {
							var user_tags = me.user_tags ? me.user_tags.split(",") : [];
							user_tags.push(tag)
							me.user_tags = user_tags.join(",");
							me.on_change && me.on_change(me.user_tags);
							frappe.tags.utils.fetch_tags();
						}
					});
				}
			},
			onTagRemove: (tag) => {
				if(!me.refreshing) {
					return frappe.call({
						method: "frappe.desk.doctype.tag.tag.remove_tag",
						args: me.get_args(tag),
						callback: function(r) {
							var user_tags = me.user_tags.split(",");
							user_tags.splice(user_tags.indexOf(tag), 1);
							me.user_tags = user_tags.join(",");
							me.on_change && me.on_change(me.user_tags);
							frappe.tags.utils.fetch_tags();
						}
					});
				}
			}
		});
		this.setup_awesomplete();
		this.setup_complete = true;
	},
	setup_awesomplete: function() {
		var me = this;
		var $input = this.wrapper.find("input.tags-input");
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
				method: "frappe.desk.doctype.tag.tag.get_tags",
				args:{
					doctype: me.frm.doctype,
					txt: value.toLowerCase(),
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
		if (!this.initialized || !this.setup_complete || this.refreshing) return;

		me.refreshing = true;
		try {
			me.tags.clearTags();
			if(user_tags) {
				me.user_tags = user_tags;
				me.tags.addTags(user_tags.split(','));
			}
		} catch(e) {
			me.refreshing = false;
			// wtf bug
			setTimeout( function() { me.refresh(); }, 100);
		}
		me.refreshing = false;

	}
})
