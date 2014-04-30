// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.messages")

frappe.messages.waiting = function(parent, msg, bar_percent) {
	if(!bar_percent) bar_percent = '100';
	return $(repl('<div class="well" style="width: 63%; margin: 30px auto;">\
		<p style="text-align: center;">%(msg)s</p>\
		<div class="progress progress-striped active">\
			<div class="progress-bar progress-bar-info" style="width: %(bar_percent)s%"></div></div>', {
				bar_percent: bar_percent,
				msg: msg
			}))
		.appendTo(parent);
};

frappe.throw = function(msg) {
	msgprint(msg);
	throw msg;
}

frappe.confirm = function(message, ifyes, ifno) {
	var d = msgprint("<p>" + message + "</p>\
		<p style='text-align: right'>\
			<button class='btn btn-info btn-yes'>"+__("Yes")+"</button>\
			<button class='btn btn-default btn-no'>"+__("No")+"</button>\
		</p>");
	$(d.wrapper).find(".btn-yes").click(function() {
		d.hide();
		ifyes && ifyes();
	});
	$(d.wrapper).find(".btn-no").click(function() {
		d.hide();
		ifno && ifno();
	});

	return d;
}

frappe.get_value = function(field, callback) {
	var d = new frappe.ui.Dialog({
		fields: [field, {fieldtype:"Button", "label":"Submit"}],
		title: __("Enter Value"),
	})
	d.get_input("submit").on("click", function() {
		var values = d.get_values();
		if(field.reqd && !values[field.fieldname]) {
			// ask to re-enter
		} else {
			d.hide();
			callback(values[field.fieldname]);
		}
	})
	d.show();
}

var msg_dialog=null;
function msgprint(msg, title) {
	if(!msg) return;

	if(msg instanceof Array) {
		$.each(msg, function(i,v) {
			if(v) {
				msgprint(v);
			}
		})
		return;
	}

	if(typeof(msg)!='string')
		msg = JSON.stringify(msg);

	// small message
	if(msg.substr(0,8)=='__small:') {
		show_alert(msg.substr(8)); return;
	}

	if(!msg_dialog) {
		msg_dialog = new frappe.ui.Dialog({
			title: __("Message"),
			onhide: function() {
				if(msg_dialog.custom_onhide) {
					msg_dialog.custom_onhide();
				}
				msg_dialog.msg_area.empty();
			}
		});
		msg_dialog.msg_area = $('<div class="msgprint">')
			.appendTo(msg_dialog.body);
	}

	if(msg.search(/<br>|<p>|<li>/)==-1)
		msg = replace_newlines(msg);

	msg_dialog.set_title(title || __('Message'))

	// append a <hr> if another msg already exists
	if(msg_dialog.msg_area.html()) msg_dialog.msg_area.append("<hr>");

	msg_dialog.msg_area.append(msg);

	// make msgprint always appear on top
	msg_dialog.$wrapper.css("z-index", 2000);
	msg_dialog.show();

	return msg_dialog;
}

// Floating Message
function show_alert(txt, add_class) {
	if(!$('#dialog-container').length) {
		$('<div id="dialog-container">').appendTo('body');
	}
	if(!$('#alert-container').length) {
		$('<div id="alert-container"></div>').appendTo('#dialog-container');
	}

	var div = $('<div class="alert alert-warning">\
		<a class="close">&times;</a>'+ txt +'</div>')
			.appendTo('#alert-container')
	div.find('.close').click(function() {
		$(this).parent().remove();
		return false;
	});
	div.delay(7000).fadeOut(500);
	return div;
}
