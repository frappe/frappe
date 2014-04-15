// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

frappe.provide('frappe.core.pages.messages');

frappe.pages.messages.onload = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Messages"
	});
	
	$('<div><div class="avatar avatar-large">\
		<img id="avatar-image" src="assets/frappe/images/ui/avatar.png"></div>\
		<h3 style="display: inline-block" id="message-title">Everyone</h3>\
	</div><hr>\
	<div id="post-message">\
	<textarea class="form-control" rows=3 style="margin-bottom: 15px;"></textarea>\
	<div><button class="btn btn-default">Post</button></div><hr>\
	</div>\
	<div class="all-messages"></div><br>').appendTo($(wrapper).find('.layout-main-section'));

	wrapper.appframe.add_module_icon("Messages");
	
	frappe.core.pages.messages = new frappe.core.pages.messages(wrapper);
}

$(frappe.pages.messages).bind('show', function() {
	// remove alerts
	$('#alert-container .alert').remove();
	
	frappe.core.pages.messages.show();
	setTimeout("frappe.core.pages.messages.refresh()", 5000);
})

frappe.core.pages.messages = Class.extend({
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
					module: 'frappe.core',
					page:'messages',
					method:'post',
					args: {
						txt: txt,
						contact: me.contact
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
		setTimeout("frappe.core.pages.messages.refresh()", 5000);
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
			method: 'frappe.core.page.messages.messages.get_list',
			args: {
				contact: null
			},
			hide_refresh: true,
			no_loading: true,
			render_row: function(wrapper, data) {
				$(wrapper).removeClass('list-row');
				
				data.creation = dateutil.comment_when(data.creation);
				data.comment_by_fullname = frappe.user_info(data.owner).fullname;
				data.image = frappe.utils.get_file_link(frappe.user_info(data.owner).image);
				data.mark_html = "";

				data.reply_html = '';
				if(data.owner==user) {
					data.cls = 'message-self';
					data.comment_by_fullname = 'You';	
				} else {
					data.cls = 'message-other';
				}

				// delete
				data.delete_html = "";
				if(data.owner==user || data.comment.indexOf("assigned to")!=-1) {
					data.delete_html = repl('<a class="close" \
						onclick="frappe.core.pages.messages.delete(this)"\
						data-name="%(name)s">&times;</a>', data);
				}
				
				if(data.owner==data.comment_docname && data.parenttype!="Assignment") {
					data.mark_html = "<div class='message-mark' title='Public'\
						style='background-color: green'></div>"
				}

				wrapper.innerHTML = repl('<div class="message %(cls)s">%(mark_html)s\
						<span class="avatar avatar-small"><img src="%(image)s"></span><b>%(comment)s</b>\
						%(delete_html)s\
						<div class="help">by %(comment_by_fullname)s, %(creation)s</div>\
					</div>\
					<div style="clear: both;"></div>', data);
			}
		});
	},
	delete: function(ele) {
		$(ele).parent().css('opacity', 0.6);
		return frappe.call({
			method: 'frappe.core.page.messages.messages.delete',
			args: {name : $(ele).attr('data-name')},
			callback: function() {
				$(ele).parent().toggle(false);
			}
		});
	},
	show_active_users: function() {
		var me = this;
		return frappe.call({
			module:'frappe.core',
			page:'messages',
			method:'get_active_users',
			callback: function(r,rt) {
				var $body = $(me.wrapper).find('.layout-side-section');
				$('<h4>Users</h4><hr>\
					<div id="show-everyone">\
						<a href="#messages/'+user+'" class="btn btn-default">\
							Messages from everyone</a><hr></div>\
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


