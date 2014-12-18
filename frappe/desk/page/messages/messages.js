// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.desk.pages.messages');

frappe.pages.messages.onload = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Messages"
	});

	$('<div style="margin-bottom: 15px;">\
		<span class="avatar" style="margin-top: -10px;"><img id="avatar-image" src=""></span>\
		<h3 style="display: inline-block" id="message-title">' + __("Everyone") + '</h3>\
	</div>\
	<div id="post-message">\
	<textarea class="form-control" style="height: 80px; margin-bottom: 15px;"></textarea>\
	<div class="checkbox">\
		<label>\
			<input type="checkbox" id="messages-email" checked="checked">\
				<span class="text-muted small">'+__('Send Email')+'</span>\
		</label></div>\
	<div><button class="btn btn-default">'+__('Post')+'</button></div><hr>\
	</div>\
	<div class="all-messages"></div><br>').appendTo($(wrapper).find('.layout-main-section'));

	frappe.add_breadcrumbs("Messages");

	frappe.desk.pages.messages = new frappe.desk.pages.messages(wrapper);
}

$(frappe.pages.messages).bind('show', function() {
	// remove alerts
	$('#alert-container .alert').remove();

	frappe.desk.pages.messages.show();
	setTimeout("frappe.desk.pages.messages.refresh()", 5000);
})

frappe.desk.pages.messages = Class.extend({
	init: function(wrapper) {
		this.wrapper = wrapper;
		this.show_active_users();
		this.make_post_message();
		this.make_list();
		//this.update_messages('reset'); //Resets notification icons
	},
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
	make_list: function() {
		this.list = new frappe.ui.Listing({
			parent: $(this.wrapper).find('.all-messages'),
			method: 'frappe.desk.page.messages.messages.get_list',
			args: {
				contact: null
			},
			hide_refresh: true,
			no_loading: true,
			render_row: function(wrapper, data) {
				$(wrapper).removeClass('list-row');

				data.creation = comment_when(data.creation);
				data.comment_by_fullname = frappe.user_info(data.owner).fullname;
				data.image = frappe.utils.get_file_link(frappe.user_info(data.owner).image);
				data.info = "";

				data.reply_html = '';
				if(data.owner==user) {
					data.comment_by_fullname = 'You';
				}

				// delete
				data.delete_html = "";
				if(data.owner==user || data.comment.indexOf("assigned to")!=-1) {
					data.delete_html = repl('<a class="close" \
						onclick="frappe.desk.pages.messages.delete(this)"\
						data-name="%(name)s">&times;</a>', data);
				}

				if(data.owner==data.comment_docname && data.parenttype!="Assignment") {
					data.info = '<span class="label label-success">Public</span>'
				}

				$(wrapper)
					.addClass("media").addClass(data.cls);
				wrapper.innerHTML = repl('<span class="pull-left avatar avatar-small">\
							<img class="media-object" src="%(image)s">\
						</span>\
						<div class="media-body">\
							%(comment)s\
							%(delete_html)s\
							<div class="text-muted" style="margin-right: 60px;">\
								<span class="small">by <strong>%(comment_by_fullname)s</strong>, \
								%(creation)s</span> %(info)s</div>\
						</div>', data);
			}
		});
	},
	delete: function(ele) {
		$(ele).parent().css('opacity', 0.6);
		return frappe.call({
			method: 'frappe.desk.page.messages.messages.delete',
			args: {name : $(ele).attr('data-name')},
			callback: function() {
				$(ele).parent().toggle(false);
			}
		});
	},
	show_active_users: function() {
		var me = this;
		return frappe.call({
			module:'frappe.desk',
			page:'messages',
			method:'get_active_users',
			callback: function(r,rt) {
				var $body = $(me.wrapper).find('.layout-side-section');
				$('<h4>' + __("Users") + '</h4><hr>\
					<div id="show-everyone">\
						<a href="#messages/'+user+'" class="btn btn-default">\
							' + __("Messages from everyone") + '</a><hr></div>\
				').appendTo($body);

				$("#show-everyone").toggle(me.contact!==user);

				r.message.sort(function(a, b) { return b.has_session - a.has_session; });
				for(var i in r.message) {
					var p = r.message[i];
					if(p.name != user) {
						p.fullname = frappe.user_info(p.name).fullname;
						p.image = frappe.utils.get_file_link(frappe.user_info(p.name).image);
						p.name = p.name.replace('@', '__at__');
						p.status_color = p.has_session ? "green" : "#ddd";
						p.status = p.has_session ? "Online" : "Offline";
						$(repl('<p>\
							<span class="avatar avatar-small" \
								title="%(status)s"><img src="%(image)s" /></span>\
							<a href="#!messages/%(name)s">%(fullname)s</a>\
							</p>', p))
							.appendTo($body);
					}
				}
			}
		});
	}
});


