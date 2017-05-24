// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.pages.chat.on_page_load = function(parent) {
	var page = frappe.ui.make_app_page({
		parent: parent,
	});

	page.set_title('<span class="hidden-xs">' + __("Chat") + '</span>'
		+ '<span class="hidden-sm hidden-md hidden-lg message-to"></span>');

	$(".navbar-center").html(__("Chat"));

	frappe.pages.chat.chat = new frappe.Chat(parent);
}

frappe.pages.chat.on_page_show = function() {
	// clear title prefix
	frappe.utils.set_title_prefix("");

	frappe.breadcrumbs.add("Desk");
}

frappe.Chat = Class.extend({
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
			if(comment.modified_by !== frappe.session.user || comment.communication_type === 'Bot') {
				if(frappe.get_route()[0] === 'chat') {
					var current_contact = $(cur_page.page).find('[data-contact]').data('contact');
					var on_broadcast_page = current_contact === frappe.session.user;
					if ((current_contact == comment.owner)
						|| (on_broadcast_page && comment.broadcast)
						|| current_contact === 'Bot' && comment.communication_type === 'Bot') {

						setTimeout(function() { me.prepend_comment(comment); }, 1000);
					}
				} else {
					frappe.utils.notify(__("Message from {0}", [frappe.user_info(comment.owner).fullname]), comment.content);
				}
			}
		});
	},

	prepend_comment: function(comment) {
		frappe.pages.chat.chat.list.data.unshift(comment);
		this.render_row(comment, true);
	},

	make_sidebar: function() {
		var me = this;
		return frappe.call({
			module:'frappe.desk',
			page:'chat',
			method:'get_active_users',
			callback: function(r,rt) {
				// sort
				r.message.sort(function(a, b) { return cint(b.has_session) - cint(a.has_session); });

				// render
				me.page.sidebar.html(frappe.render_template("chat_sidebar", {data: r.message}));

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

		this.page.main.html($(frappe.render_template("chat_main", { "contact": contact })));

		var text_area = this.page.main.find(".messages-textarea").on("focusout", function() {
			// on touchscreen devices, scroll to top
			// so that static navbar and page head don't overlap the textarea
			if (frappe.dom.is_touchscreen()) {
				frappe.utils.scroll_to($(this).parents(".message-box"));
			}
		});


		var post_btn = this.page.main.find(".btn-post").on("click", function() {
			var btn = $(this);
			var message_box = btn.parents(".message-box");
			var textarea = message_box.find("textarea");
			var contact = btn.attr("data-contact");
			var txt = textarea.val();
			var send_email = message_box.find('input[type="checkbox"]:checked').length > 0;

			if(txt) {
				return frappe.call({
					module: 'frappe.desk',
					page:'chat',
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

		text_area.keydown("meta+return ctrl+return", function(e) {
			post_btn.trigger("click");
		});

		this.page.wrapper.find(".page-head .message-to").html(frappe.user.full_name(contact));

		this.make_message_list(contact);

		this.list.run();

		frappe.utils.scroll_to();
	},

	make_message_list: function(contact) {
		var me = this;

		this.list = new frappe.ui.BaseList({
			parent: this.page.main.find(".message-list"),
			page: this.page,
			method: 'frappe.desk.page.chat.chat.get_list',
			args: {
				contact: contact
			},
			hide_refresh: true,
			freeze: false,
			render_view: function (values) {
				values.map(function (value) {
					me.render_row(value);
				});
			},
		});
	},

	render_row: function(value, prepend) {
		this.prepare(value)

		var wrapper = $('<div class="list-row">')
			.data("data", this.meta)

		if(!prepend)
			wrapper.appendTo($(".result-list")).get(0);
		else
			wrapper.prependTo($(".result-list")).get(0);

		var row = $(frappe.render_template("chat_row", {
			data: value
		})).appendTo(wrapper)
		row.find(".avatar, .indicator").tooltip();
	},

	delete: function(ele) {
		$(ele).parent().css('opacity', 0.6);
		return frappe.call({
			method: 'frappe.desk.page.chat.chat.delete',
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

	prepare: function(data) {
		if(data.communication_type==="Notification" || data.comment_type==="Shared") {
			data.is_system_message = 1;
		}

		if(data.owner==data.reference_name
			&& data.communication_type!=="Notification"
			&& data.comment_type!=="Bot") {
			data.is_public = true;
		}

		if(data.owner==data.reference_name && data.communication_type !== "Bot") {
			data.is_mine = true;
		}

		if(data.owner==data.reference_name && data.communication_type === "Bot") {
			data.owner = 'bot';
		}

		data.content = frappe.markdown(data.content.substr(0, 1000));
	}



});
