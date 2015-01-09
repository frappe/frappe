// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.InfoBar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
		this.refresh();
	},
	make: function() {
		var me = this;

		this.page.iconbar.clear(2);
		this.$reload = this.page.add_icon_btn("2", "icon-refresh", __("Reload Page"),
			function() { me.frm.reload_doc(); })


		this.$timestamp = this.page.add_icon_btn("2", "icon-user", __("Creation / Modified By"),
			function() {
				msgprint("Created By: " + frappe.user.full_name(me.frm.doc.owner) + "<br>" +
					"Created On: " + comment_when(me.frm.doc.creation) + "<br>" +
					"Last Modified By: " + frappe.user.full_name(me.frm.doc.modified_by) + "<br>" +
					"Last Modifed On: " + comment_when(me.frm.doc.modified))
			});

		this.$comments = this.page.add_icon_btn("2", "icon-comments", __("Comments"), function() {
				me.scroll_to(".form-comments .btn-go");
			});

		this.$attachments = this.page.add_icon_btn("2", "icon-paper-clip", __("Attachments"),  function() {
				me.scroll_to(".form-attachments");
			});

		this.$assignments = this.page.add_icon_btn("2", "icon-flag", __("Assignments"),  function() {
				me.scroll_to(".form-assignments");
			});

		this.$links = this.page.add_icon_btn("2", "icon-link", __("Linked With"),
				function() { me.frm.toolbar.show_linked_with(); });

		this.$star = this.page.add_icon_btn("2", "icon-star star-action", __("Star this document"),
				function() {
					frappe.ui.toggle_star(me.$star, me.frm.doctype,
						me.frm.doc.name) }).find(".star-action");

		// link to user permissions
		if(!me.frm.meta.issingle && frappe.model.can_set_user_permissions(me.frm.doctype, me.frm)) {
			this.$user_properties = this.page.add_icon_btn("2", "icon-shield",
				__("User Permissions Manager"), function() {
					frappe.route_options = {
						doctype: me.frm.doctype,
						name: me.frm.docname
					};
					frappe.set_route("user-permissions");
				});
		}

		if(frappe.model.can_print(me.frm.doctype, me.frm)) {
			this.$print = this.page.add_icon_btn("2", "icon-print", __("Print"),
				function() { me.frm.print_doc(); });
		}

		if(frappe.model.can_email(me.frm.doctype, me.frm)) {
			this.$print = this.page.add_icon_btn("2", "icon-envelope", __("Email"),
				function() { me.frm.email_doc(); });
		}

		if(!this.frm.meta.issingle) {
			this.$prev = this.page.add_icon_btn("2", "icon-arrow-left", __("Previous Record"),
				function() { me.go_prev_next(true); });

			this.$next = this.page.add_icon_btn("2", "icon-arrow-right", __("Next Record"),
				function() { me.go_prev_next(false); });
		}

	},

	refresh: function() {
		if(!this.frm.doc.__islocal) {
			this.docinfo = frappe.model.docinfo[this.frm.doctype][this.frm.docname];
			// highlight comments
			this.highlight_items();
		}
	},

	highlight_items: function() {
		var me = this;

		this.$comments
			.popover("destroy")

		if(this.docinfo.comments && this.docinfo.comments.length) {
			var last = this.docinfo.comments[this.docinfo.comments.length - 1];
			this.$comments
				.popover({
					title: __("Last Comment"),
					content: last.comment
						+ '<p class="text-muted small">By '
						+ frappe.user_info(last.comment_by).fullname
						+ " / " + comment_when(last.creation)
						+ '</p>',
					trigger:"hover",
					html: true,
					placement: "bottom"
				});
		}

		$.each(["comments", "attachments", "assignments"], function(i, v) {
			if(me.docinfo[v] && me.docinfo[v].length)
				me["$" + v].addClass("page-toolbar-active");
			else
				me["$" + v].removeClass("page-toolbar-active");
		});

		// toggle star icon
		this.$star
			.attr("data-name", me.frm.doc.name)
			.removeClass("icon-star")
			.removeClass("icon-star-empty")
			.addClass("icon-star" + ((me.frm.doc._starred_by || "").indexOf(user)===-1 ? "-empty" : ""))
	},

	scroll_to: function(cls) {
		$('html, body').animate({
			scrollTop: $(this.frm.wrapper).find(cls).offset().top - 100
		}, 100);
	},

	go_prev_next: function(prev) {
		var me = this,
			filters = null,
			order_by = "modified desc",
			doclistview_page = frappe.pages["List/" + me.frm.doctype];

		// filters / order defined in listview

		if(doclistview) {
			// if existing list, move according to the list
			var doclistview = doclistview_page.doclistview;
			for(var i=0, l=doclistview.data.length; i<l-1; i++) {
				if(doclistview.data[i].name==me.frm.doc.name) {
					frappe.set_route("Form", me.frm.doctype, doclistview.data[i+1].name);
					return;
				}
			}

			// not in list, apply the same filters
			filters = doclistview.filter_list.get_filters();
			if(doclistview.listview.order_by) {
				order_by = doclistview.listview.order_by;
			}
		}

		return frappe.call({
			method: "frappe.desk.form.utils.get_next",
			args: {
				doctype: me.frm.doctype,
				value: me.frm.doc[order_by.split(" ")[0]],
				prev: prev ? 1 : 0,
				filters: filters,
				order_by: order_by
			},
			callback: function(r) {
				if(r.message)
					frappe.set_route("Form", me.frm.doctype, r.message);
			}
		});
	},
})
