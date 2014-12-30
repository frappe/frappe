// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// TODO
// new message popup

frappe.provide('frappe.desk.pages.messages');

frappe.pages.messages.onload = function(parent) {
	frappe.ui.make_app_page({
		parent: parent,
		title: "Messages"
	});

	frappe.desk.pages.messages = new frappe.desk.pages.messages(parent);
}

frappe.desk.pages.messages = Class.extend({
	init: function(wrapper, page) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.make();
	},

	make: function() {
		this.make_sidebar();
		this.set_next_refresh();
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
						me.list.run();
					},
					btn: this
				});
			}
		});

		this.make_message_list(contact);

		this.list.run();
	},

	make_message_list: function(contact) {
		var me = this;

		this.list = new frappe.ui.Listing({
			parent: this.page.main.find(".message-list"),
			method: 'frappe.desk.page.messages.messages.get_list',
			args: {
				contact: contact
			},
			hide_refresh: true,
			no_loading: true,
			render_row: function(wrapper, data) {
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

	refresh: function() {
		// check for updates every 5 seconds if page is active
		this.set_next_refresh();

		if(!frappe.session_alive)
			return;

		if (this.list) {
			this.list.run();
		}
	},

	set_next_refresh: function() {
		// 30 seconds
		setTimeout("frappe.desk.pages.messages.refresh()", 30000);
	},

	////

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


