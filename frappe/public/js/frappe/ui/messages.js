// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.messages")

frappe.messages.waiting = function(parent, msg) {
	return $(frappe.messages.get_waiting_message(msg))
		.appendTo(parent);
};

frappe.messages.get_waiting_message = function(msg) {
	return repl('<div class="msg-box" style="width: 63%; margin: 30px auto;">\
		<p class="text-center">%(msg)s</p></div>', { msg: msg });
}

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
		primary_action_label: __("Yes"),
		primary_action: function() { d.hide(); ifyes(); }
	});
	d.show();
	if(ifno) {
		d.$wrapper.find(".modal-footer .btn-default").click(ifno);
	}
	return d;
}

frappe.prompt = function(fields, callback, title, primary_label) {
	if(!$.isArray(fields)) fields = [fields];
	var d = new frappe.ui.Dialog({
		fields: fields,
		title: title || __("Enter Value"),
	})
	d.set_primary_action(primary_label || __("Submit"), function() {
		var values = d.get_values();
		if(!values) {
			return;
		}
		d.hide();
		callback(values);
	})
	d.show();
}

var msg_dialog=null;
frappe.msgprint = function(msg, title) {
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

var msgprint = frappe.msgprint;

// Floating Message
function show_alert(txt, seconds) {
	if(!$('#dialog-container').length) {
		$('<div id="dialog-container"><div id="alert-container"></div></div>').appendTo('body');
	}

	var div = $(repl('<div class="alert desk-alert" style="display: none;">'
			+ '<a class="close">&times;</a><span class="alert-message">%(txt)s</span>'
		+ '</div>', {txt: txt}))
		.appendTo("#alert-container")
		.fadeIn(300);

	div.find('.close').click(function() {
		$(this).parent().remove();
		return false;
	});
	div.delay(seconds ? seconds * 1000 : 3000).fadeOut(300);
	return div;
}
