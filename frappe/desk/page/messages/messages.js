// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// TODO
// Everyone
// Text Box
// Email + Post Message
// new message popup

frappe.provide('frappe.desk.pages.messages');

frappe.pages.messages.onload = function(parent) {
	frappe.ui.make_app_page({
		parent: parent,
		title: "Messages"
	});

	frappe.add_breadcrumbs("Messages");

	frappe.desk.pages.messages = new frappe.desk.pages.messages(parent);
}

$(frappe.pages.messages).bind('show', function() {
	return;

	// remove alerts
	$('#alert-container .alert').remove();

	frappe.desk.pages.messages.show();
	setTimeout("frappe.desk.pages.messages.refresh()", 5000);
})

frappe.desk.pages.messages = Class.extend({
	init: function(wrapper, page) {
		this.wrapper = wrapper;
		this.page = wrapper.page;
		this.make();

		return;
		this.show_active_users();
		this.make_post_message();
		this.make_list();
		//this.update_messages('reset'); //Resets notification icons
	},

	make: function() {
		this.make_sidebar();
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
				$(frappe.render_template("messages_sidebar", {data: r.message})).appendTo(me.page.sidebar);

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
		this.list = new frappe.ui.Listing({
			parent: this.page.main,
			method: 'frappe.desk.page.messages.messages.get_list',
			args: {
				contact: contact
			},
			hide_refresh: true,
			no_loading: true,
			render_row: function(wrapper, data) {
				$(frappe.render_template("messages_row", {
					data: data
				})).appendTo(wrapper);

				return;

				// todo

				if(data.owner==data.comment_docname && data.parenttype!="Assignment") {
					data.info = '<span class="label label-success">Public</span>'
				}
			}

		});

		this.list.run();
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

	////

	make_post_message: function() {
		var me = this;

		$('#post-message .btn').click(function() {
			var txt = $('#post-message textarea').val();
			if(txt) {
				return frappe.call({
					module: 'frappe.desk',
					page:'messages',
					method:'post',
					args: {
						txt: txt,
						contact: me.contact,
						notify: $('#messages-email').prop("checked") ? 1 : 0
					},
					callback:function(r,rt) {
						$('#post-message textarea').val('')
						me.list.run();
					},
					btn: this
				});
			}
		});
	},
	show: function() {
		var contact = this.get_contact() || this.contact || user;

		$('#message-title').html(contact===user ? "Everyone" :
			frappe.user_info(contact).fullname)

		$('#avatar-image').attr("src", frappe.utils.get_file_link(frappe.user_info(contact).image));

		$("#show-everyone").toggle(contact!==user);

		$("#post-message button").text(contact==user ? __("Post Publicly") : __("Post to user"))

		this.contact = contact;
		this.list.opts.args.contact = contact;
		this.list.run();

	},
	// check for updates every 5 seconds if page is active
	refresh: function() {
		setTimeout("frappe.desk.pages.messages.refresh()", 5000);
		if(frappe.container.page.label != 'Messages')
			return;
		if(!frappe.session_alive)
			return;
		this.show();
	},
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


