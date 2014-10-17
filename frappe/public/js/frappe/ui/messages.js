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
	throw new Error(msg);
}

frappe.confirm = function(message, ifyes, ifno) {
	var d = new frappe.ui.Dialog({
		title: __("Confirm"),
		fields: [
			{fieldtype:"HTML", options:"<p class='frappe-confirm-message'>" + message + "</p>"}
		],
		primary_action: function() { d.hide(); ifyes(); }
	});
	d.show();
	if(ifno) {
		d.$wrapper.find(".modal-footer .btn-default").click(ifno);
	}
	return d;
}

frappe.get_value = function(field, callback) {
	var d = new frappe.ui.Dialog({
		fields: [field, {fieldtype:"Button", "label":__("Submit")}],
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
function show_alert(txt, seconds) {
	if(!$('#dialog-container').length) {
		$('<div id="dialog-container">').appendTo('body');
	}
	if(!$('#alert-container').length) {
		$('<div id="alert-container"></div>').appendTo('#dialog-container');
	}

	var div = $('<div class="alert alert-warning" style="box-shadow: 0px 0px 2px rgba(0,0,0,0.5)">\
		<a class="close" style="margin-left: 10px;">&times;</a>'+ txt +'</div>')
			.appendTo('#alert-container')
	div.find('.close').click(function() {
		$(this).parent().remove();
		return false;
	});
	div.delay(seconds ? seconds * 1000 : 3000).fadeOut(300);
	return div;
}
