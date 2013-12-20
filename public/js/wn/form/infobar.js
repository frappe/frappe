// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.ui.form.InfoBar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.refresh();
	},
	make: function() {
		var me = this;

		this.appframe.iconbar.clear(2);
		this.$reload = this.appframe.add_icon_btn("2", "icon-refresh", wn._("Reload Page"), 
			function() { me.frm.reload_doc(); })


		this.$timestamp = this.appframe.add_icon_btn("2", "icon-user", wn._("Creation / Modified By"), 
			function() { })

		this.$comments = this.appframe.add_icon_btn("2", "icon-comments", wn._("Comments"), function() {
				me.scroll_to(".form-comments");
			});
			
		this.$attachments = this.appframe.add_icon_btn("2", "icon-paper-clip", wn._("Attachments"),  function() {
				me.scroll_to(".form-attachments");
			});

		this.$assignments = this.appframe.add_icon_btn("2", "icon-flag", wn._("Assignments"),  function() {
				me.scroll_to(".form-attachments");
			});		


		this.$links = this.appframe.add_icon_btn("2", "icon-link", wn._("Linked With"), 
				function() { me.frm.toolbar.show_linked_with(); });
		
		// link to user restrictions
		if(wn.model.can_restrict(me.frm.doctype, me.frm)) {
			this.$user_properties = this.appframe.add_icon_btn("2", "icon-shield", 
				wn._("User Permission Restrictions"), function() {
					wn.route_options = {
						property: me.frm.doctype,
						restriction: me.frm.docname
					};
					wn.set_route("user-properties");
				});
		}

		if(wn.model.can_print(me.frm.doctype, me.frm)) {
			this.$print = this.appframe.add_icon_btn("2", "icon-print", wn._("Print"), 
				function() { me.frm.print_doc(); });
		}

		if(wn.model.can_email(me.frm.doctype, me.frm)) {
			this.$print = this.appframe.add_icon_btn("2", "icon-envelope", wn._("Email"), 
				function() { me.frm.email_doc(); });
		}
		
		if(!this.frm.meta.issingle) {
			this.$prev = this.appframe.add_icon_btn("2", "icon-arrow-left", wn._("Previous Record"), 
				function() { me.go_prev_next(true); });
		
			this.$next = this.appframe.add_icon_btn("2", "icon-arrow-right", wn._("Next Record"), 
				function() { me.go_prev_next(false); });
		}
		
	},
	
	refresh: function() {		
		if(!this.frm.doc.__islocal) {
			this.docinfo = wn.model.docinfo[this.frm.doctype][this.frm.docname];
			// highlight comments
			this.highlight_items();
		}
	},
	
	highlight_items: function() {
		var me = this;
		
		this.$timestamp
			.popover("destroy")
			.popover({
				title: "Created and Modified By",
				content: "Created By: " + wn.user.full_name(me.frm.doc.owner) + "<br>" +
					"Created On: " + dateutil.str_to_user(me.frm.doc.creation) + "<br>" +
					"Last Modified By: " + wn.user.full_name(me.frm.doc.modified_by) + "<br>" +
					"Last Modifed On: " + dateutil.str_to_user(me.frm.doc.modified),
				trigger:"hover",
				html: true,
				placement: "bottom"
			})

		this.$comments
			.popover("destroy")
		
		if(this.docinfo.comments.length) {
			var last = this.docinfo.comments[0];
			this.$comments
				.popover({
					title: "Last Comment",
					content: last.comment 
						+ '<p class="text-muted small">By '
						+ wn.user_info(last.comment_by).fullname 
						+ " / " + comment_when(last.creation)
						+ '</p>',
					trigger:"hover",
					html: true,
					placement: "bottom"
				});
		}
		
		$.each(["comments", "attachments", "assignments"], function(i, v) {
			if(me.docinfo[v].length)
				me["$" + v].addClass("appframe-iconbar-active");
			else
				me["$" + v].removeClass("appframe-iconbar-active");
		})
	},

	scroll_to: function(cls) {
		$('html, body').animate({
			scrollTop: $(this.frm.wrapper).find(cls).offset().top
		}, 1000);
	},
	
	go_prev_next: function(prev) {
		var me = this;
		return wn.call({
			method: "webnotes.widgets.form.utils.get_next",
			args: {
				doctype: me.frm.doctype,
				name: me.frm.docname,
				prev: prev ? 1 : 0
			},
			callback: function(r) {
				if(r.message)
					wn.set_route("Form", me.frm.doctype, r.message);
			}
		});
	},
})