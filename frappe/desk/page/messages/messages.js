// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// TODO
// new message popup

frappe.provide('frappe.desk.pages.messages');

frappe.pages.messages.on_page_load = function(parent) {
	var page = frappe.ui.make_app_page({
		parent: parent,
	});

	page.set_title('<span class="hidden-xs">' + __("Messages") + '</span>'
		+ '<span class="hidden-sm hidden-md hidden-lg message-to"></span>');

	$(".navbar-center").html(__("Messages"));

	frappe.desk.pages.messages = new frappe.desk.pages.Messages(parent);
}

frappe.pages.messages.on_page_show = function() {
	// clear title prefix
	frappe.utils.set_title_prefix("");
}

frappe.desk.pages.Messages = Class.extend({
	init: function(wrapper, page) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.make();
		this.page.sidebar.addClass("col-sm-3");
		this.page.wrapper.find(".layout-main-section-wrapper").addClass("col-sm-9");
		this.page.wrapper.find(".page-title").removeClass("col-xs-6").addClass("col-xs-12");
		this.page.wrapper.find(".page-actions").removeClass("col-xs-6").addClass("hidden-xs");
		this.setup_realtime();
	},

	make: function() {
		this.make_sidebar();
	},

	setup_realtime: function() {
		var me = this;
    	frappe.realtime.on('new_message', function(comment) {
			if(comment.modified_by !== user) {
	    		frappe.utils.notify(__("Message from {0}", [comment.comment_by_fullname]), comment.comment);
			}
    		if (frappe.get_route()[0] === 'messages') {
    			var current_contact = $(cur_page.page).find('[data-contact]').data('contact');
    			var on_broadcast_page = current_contact === user;
    			if ((current_contact == comment.owner) || (on_broadcast_page && comment.broadcast)) {
    				me.prepend_comment(comment);
    			}
    		}
    	});
	},

	prepend_comment: function(comment) {
		var $row = $('<div class="list-row"/>');
		frappe.desk.pages.messages.list.data.unshift(comment);
		frappe.desk.pages.messages.list.render_row($row, comment);
		frappe.desk.pages.messages.list.$w.prepend($row);
	},

	make_sidebar: function() {
		var me = this;
		return frappe.call({
			module:'frappe.desk',
			page:'messages',
			method:'get_active_users',
			callback: function(r,rt) {
				// sort
				r.message.sort(function(a, b) { return cint(b.has_session) - cint(a.has_session); });

				// render
				me.page.sidebar.html(frappe.render_template("messages_sidebar", {data: r.message}));

				// bind click
				me.page.sidebar.find("a").on("click", function() {
					var li = $(this).parents("li:first");
					if (li.hasClass("active"))
						return false;

					var contact = li.attr("data-user");

					// active
					me.page.sidebar.find("li.active").removeClass("active");
					me.page.sidebar.find('[data-user="'+ contact +'"]').addClass("active");

					me.make_messages(contact);
				});

				$(me.page.sidebar.find("a")[0]).click();
			}
		});
	},

	make_messages: function(contact) {
		var me = this;

		this.page.main.html($(frappe.render_template("messages_main", { "contact": contact })));

		this.page.main.find(".messages-textarea").on("focusout", function() {
			// on touchscreen devices, scroll to top
			// so that static navbar and page head don't overlap the textarea
			if (frappe.dom.is_touchscreen()) {
				frappe.ui.scroll($(this).parents(".message-box"));
			}
		});

		this.page.main.find(".btn-post").on("click", function() {
			var btn = $(this);
			var message_box = btn.parents(".message-box");
			var textarea = message_box.find("textarea");
			var contact = btn.attr("data-contact");
			var txt = textarea.val();
			var send_email = message_box.find('input[type="checkbox"]:checked').length > 0;

			if(txt) {
				return frappe.call({
					module: 'frappe.desk',
					page:'messages',
					method:'post',
					args: {
						txt: txt,
						contact: contact,
						notify: send_email ? 1 : 0
					},
					callback:function(r,rt) {
						textarea.val('');
						if (!r.exc) {
							me.prepend_comment(r.message);
						}
					},
					btn: this
				});
			}
		});

		this.page.wrapper.find(".page-head .message-to").html(frappe.user.full_name(contact));

		this.make_message_list(contact);

		this.list.run();

		scroll(0, 0);
	},

	make_message_list: function(contact) {
		var me = this;

		this.list = new frappe.ui.Listing({
			parent: this.page.main.find(".message-list"),
			page: this.page,
			method: 'frappe.desk.page.messages.messages.get_list',
			args: {
				contact: contact
			},
			hide_refresh: true,
			freeze: false,
			render_row: function(wrapper, data) {
				if(data.parenttype==="Assignment" || data.comment_type==="Shared") {
					data.is_system_message = 1;
				}
				var row = $(frappe.render_template("messages_row", {
					data: data
				})).appendTo(wrapper);
				row.find(".avatar, .indicator").tooltip();
			}

		});
	},

	delete: function(ele) {
		$(ele).parent().css('opacity', 0.6);
		return frappe.call({
			method: 'frappe.desk.page.messages.messages.delete',
			args: {name : $(ele).attr('data-name')},
			callback: function() {
				$(ele).parents(".list-row:first").toggle(false);
			}
		});
	},

	refresh: function() {},

	get_contact: function() {
		var route = location.hash;
		if(route.indexOf('/')!=-1) {
			var name = decodeURIComponent(route.split('/')[1]);
			if(name.indexOf('__at__')!=-1) {
				name = name.replace('__at__', '@');
			}
			return name;
		}
	},



});
