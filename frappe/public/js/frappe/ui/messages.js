// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.messages");

import './dialog';

frappe.messages.waiting = function(parent, msg) {
	return $(frappe.messages.get_waiting_message(msg))
		.appendTo(parent);
};

frappe.messages.get_waiting_message = function(msg) {
	return repl('<div class="msg-box" style="width: 63%; margin: 30px auto;">\
		<p class="text-center">%(msg)s</p></div>', { msg: msg });
}

frappe.throw = function(msg) {
	if(typeof msg==='string') {
		msg = {message: msg, title: __('Error')};
	}
	if(!msg.indicator) msg.indicator = 'red';
	frappe.msgprint(msg);
	throw new Error(msg.message);
}

frappe.confirm = function(message, ifyes, ifno) {
	var d = new frappe.ui.Dialog({
		title: __("Confirm"),
		fields: [
			{fieldtype:"HTML", options:`<p class="frappe-confirm-message">${message}</p>`}
		],
		primary_action_label: __("Yes"),
		primary_action: function() {
			if(ifyes) ifyes();
			d.hide();
		},
		secondary_action_label: __("No")
	});
	d.show();

	// flag, used to bind "okay" on enter
	d.confirm_dialog = true;

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

	if($.isPlainObject(msg)) {
		var data = msg;
	} else {
		// passed as JSON
		if(typeof msg==='string' && msg.substr(0,1)==='{') {
			var data = JSON.parse(msg);
		} else {
			var data = {'message': msg, 'title': title};
		}
	}

	if(!data.indicator) {
		data.indicator = 'blue';
	}

	if(data.message instanceof Array) {
		data.message.forEach(function(m) {
			frappe.msgprint(m);
		});
		return;
	}

	if(data.alert) {
		frappe.show_alert(data);
		return;
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

		msg_dialog.indicator = msg_dialog.header.find('.indicator');
	}

	if(data.message==null) {
		data.message = '';
	}

	if(data.message.search(/<br>|<p>|<li>/)==-1) {
		msg = frappe.utils.replace_newlines(data.message);
	}

	var msg_exists = false;
	if(data.clear) {
		msg_dialog.msg_area.empty();
	} else {
		msg_exists = msg_dialog.msg_area.html();
	}

	if(data.title || !msg_exists) {
		// set title only if it is explicitly given
		// and no existing title exists
		msg_dialog.set_title(data.title || __('Message'));
	}

	// show / hide indicator
	if(data.indicator) {
		msg_dialog.indicator.removeClass().addClass('indicator ' + data.indicator);
	} else {
		msg_dialog.indicator.removeClass().addClass('hidden');
	}

	if(msg_exists) {
		msg_dialog.msg_area.append("<hr>");
	// append a <hr> if another msg already exists
	}

	msg_dialog.msg_area.append(data.message);
	msg_dialog.loading_indicator.addClass("hide");

	msg_dialog.show_loading = function() {
		msg_dialog.loading_indicator.removeClass("hide");
	}

	// make msgprint always appear on top
	msg_dialog.$wrapper.css("z-index", 2000);
	msg_dialog.show();

	return msg_dialog;
}

window.msgprint = frappe.msgprint;

frappe.hide_msgprint = function(instant) {
	// clear msgprint
	if(msg_dialog && msg_dialog.msg_area) {
		msg_dialog.msg_area.empty();
	}
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

frappe.show_progress = function(title, count, total=100, description) {
	if(frappe.cur_progress && frappe.cur_progress.title === title && frappe.cur_progress.is_visible) {
		var dialog = frappe.cur_progress;
	} else {
		var dialog = new frappe.ui.Dialog({
			title: title,
		});
		dialog.progress = $(`<div>
			<div class="progress">
				<div class="progress-bar"></div>
			</div>
			<p class="description text-muted small"></p>
		</div`).appendTo(dialog.body);
		dialog.progress_bar = dialog.progress.css({"margin-top": "10px"})
			.find(".progress-bar");
		dialog.$wrapper.removeClass("fade");
		dialog.show();
		frappe.cur_progress = dialog;
	}
	if (description) {
		dialog.progress.find('.description').text(description);
	}
	dialog.percent = cint(flt(count) * 100 / total);
	dialog.progress_bar.css({"width": dialog.percent + "%" });
	return dialog;
}

frappe.hide_progress = function() {
	if(frappe.cur_progress) {
		frappe.cur_progress.hide();
		frappe.cur_progress = null;
	}
}

// Floating Message
frappe.show_alert = function(message, seconds=7, actions={}) {
	if(typeof message==='string') {
		message = {
			message: message
		};
	}
	if(!$('#dialog-container').length) {
		$('<div id="dialog-container"><div id="alert-container"></div></div>').appendTo('body');
	}

	let body_html;

	if (message.body) {
		body_html = message.body;
	}

	const div = $(`
		<div class="alert desk-alert">
			<div class="alert-message"></div>
			<div class="alert-body" style="display: none"></div>
			<a class="close">&times;</a>
		</div>`);

	div.find('.alert-message').append(message.message);

	if(message.indicator) {
		div.find('.alert-message').addClass('indicator '+ message.indicator);
	}

	if (body_html) {
		div.find('.alert-body').show().html(body_html);
	}

	div.hide().appendTo("#alert-container").show()
		.css('transform', 'translateX(0)');

	div.find('.close, button').click(function() {
		div.remove();
		return false;
	});

	Object.keys(actions).map(key => {
		div.find(`[data-action=${key}]`).on('click', actions[key]);
	});

	div.delay(seconds * 1000).fadeOut(300);
	return div;
}

// Proxy for frappe.show_alert
Object.defineProperty(window, 'show_alert', {
	get: function() {
		console.warn('Please use `frappe.show_alert` instead of `show_alert`. It will be deprecated soon.');
		return frappe.show_alert;
	}
});
