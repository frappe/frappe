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
		primary_action: function() {
			ifyes();
			d.hide();
		}
	});
	d.show();

	// no if closed without primary action
	if(ifno) {
		d.onhide = function() {
			if(!d.primary_action_fulfilled) {
				ifno();
			}
		};
	}
	return d;
}

frappe.prompt = function(fields, callback, title, primary_label) {
	if (typeof fields === "string") {
		fields = [{
			label: fields,
			fieldname: "value",
			fieldtype: "Data",
			reqd: 1
		}];
	}
	if(!$.isArray(fields)) fields = [fields];
	var d = new frappe.ui.Dialog({
		fields: fields,
		title: title || __("Enter Value"),
	});
	d.set_primary_action(primary_label || __("Submit"), function() {
		var values = d.get_values();
		if(!values) {
			return;
		}
		d.hide();
		callback(values);
	});
	d.show();
	return d;
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

		msg_dialog.loading_indicator = $('<div class="loading-indicator text-center" \
				style="margin: 15px;">\
				<img src="/assets/frappe/images/ui/ajax-loader.gif"></div>')
			.appendTo(msg_dialog.body);

		msg_dialog.clear = function() {
			msg_dialog.msg_area.empty();
		}
	}

	if(msg.search(/<br>|<p>|<li>/)==-1)
		msg = replace_newlines(msg);

	msg_dialog.set_title(title || __('Message'))

	// append a <hr> if another msg already exists
	if(msg_dialog.msg_area.html()) msg_dialog.msg_area.append("<hr>");

	msg_dialog.msg_area.append(msg);
	msg_dialog.loading_indicator.addClass("hide");

	msg_dialog.show_loading = function() {
		msg_dialog.loading_indicator.removeClass("hide");
	}

	// make msgprint always appear on top
	msg_dialog.$wrapper.css("z-index", 2000);
	msg_dialog.show();

	return msg_dialog;
}

frappe.hide_msgprint = function(instant) {
	if(msg_dialog && msg_dialog.$wrapper.is(":visible")) {
		if(instant) {
			msg_dialog.$wrapper.removeClass("fade");
		}
		msg_dialog.hide();
		if(instant) {
			msg_dialog.$wrapper.addClass("fade");
		}
	}
}

// update html in existing msgprint
frappe.update_msgprint = function(html) {
	if(!msg_dialog || (msg_dialog && !msg_dialog.$wrapper.is(":visible"))) {
		frappe.msgprint(html);
	} else {
		msg_dialog.msg_area.html(html);
	}
}

frappe.verify_password = function(callback) {
	frappe.prompt({
		fieldname: "password",
		label: __("Enter your password"),
		fieldtype: "Password",
		reqd: 1
	}, function(data) {
		frappe.call({
			method: "frappe.core.doctype.user.user.verify_password",
			args: {
				password: data.password
			},
			callback: function(r) {
				if(!r.exc) {
					callback();
				}
			}
		});
	}, __("Verify Password"), __("Verify"))
}

var msgprint = frappe.msgprint;

frappe.show_progress = function(title, count, total) {
	if(frappe.cur_progress && frappe.cur_progress.title === title
			&& frappe.cur_progress.$wrapper.is(":visible")) {
		var dialog = frappe.cur_progress;
	} else {
		var dialog = new frappe.ui.Dialog({
			title: title,
		});
		dialog.progress = $('<div class="progress"><div class="progress-bar"></div></div>')
			.appendTo(dialog.body);
			dialog.progress_bar = dialog.progress.css({"margin-top": "10px"})
				.find(".progress-bar");
		dialog.$wrapper.removeClass("fade");
		dialog.show();
		frappe.cur_progress = dialog;
	}
	dialog.progress_bar.css({"width": cint(flt(count) * 100 / total) + "%" });
}

frappe.hide_progress = function() {
	if(frappe.cur_progress) {
		frappe.cur_progress.hide();
		frappe.cur_progress = null;
	}
}

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
