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

frappe.warn = function(title, message_html, proceed_action, primary_label) {
	const d = new frappe.ui.Dialog({
		title: title,
		indicator: 'red',
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'warning_message',
				options: `<div class="frappe-warning-message">${message_html}</div>`
			}
		],
		primary_action_label: primary_label,
		primary_action: () => {
			if (proceed_action) proceed_action();
			d.hide();
		},
		secondary_action_label: __("Cancel"),
	});

	d.buttons.find('.btn-primary').removeClass('btn-primary').addClass('btn-danger');
	const modal_footer = $(`<div class="modal-footer"></div>`).insertAfter($(d.modal_body));
	modal_footer.html(d.buttons);

	d.show();
	return d;
};

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

frappe.msgprint = function(msg, title, is_minimizable) {
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

	if(!frappe.msg_dialog) {
		frappe.msg_dialog = new frappe.ui.Dialog({
			title: __("Message"),
			onhide: function() {
				if(frappe.msg_dialog.custom_onhide) {
					frappe.msg_dialog.custom_onhide();
				}
				frappe.msg_dialog.msg_area.empty();
			},
			minimizable: data.is_minimizable || is_minimizable
		});

		// class "msgprint" is used in tests
		frappe.msg_dialog.msg_area = $('<div class="msgprint">')
			.appendTo(frappe.msg_dialog.body);

		frappe.msg_dialog.clear = function() {
			frappe.msg_dialog.msg_area.empty();
		}

		frappe.msg_dialog.indicator = frappe.msg_dialog.header.find('.indicator');
	}

	// setup and bind an action to the primary button
	if (data.primary_action) {
		if (data.primary_action.server_action && typeof data.primary_action.server_action === 'string') {
			data.primary_action.action = () => {
				frappe.call({
					method: data.primary_action.server_action,
					args: {
						args: data.primary_action.args
					},
					callback() {
						if (data.primary_action.hide_on_success) {
							frappe.hide_msgprint();
						}
					}
				});
			}
		}

		if (data.primary_action.client_action && typeof data.primary_action.client_action === 'string') {
			let parts = data.primary_action.client_action.split('.');
			let obj = window;
			for (let part of parts) {
				obj = obj[part];
			}
			data.primary_action.action = () => {
				if (typeof obj === 'function') {
					obj(data.primary_action.args);
				}
			}
		}

		frappe.msg_dialog.set_primary_action(
			__(data.primary_action.label || "Done"),
			data.primary_action.action
		);
	} else {
		if (frappe.msg_dialog.has_primary_action) {
			frappe.msg_dialog.get_primary_btn().addClass('hide');
			frappe.msg_dialog.has_primary_action = false;
		}
	}

	if (data.secondary_action) {
		frappe.msg_dialog.set_secondary_action(data.secondary_action.action);
		frappe.msg_dialog.set_secondary_action_label(__(data.secondary_action.label || "Close"));
	}

	if(data.message==null) {
		data.message = '';
	}

	if(data.message.search(/<br>|<p>|<li>/)==-1) {
		msg = frappe.utils.replace_newlines(data.message);
	}

	var msg_exists = false;
	if(data.clear) {
		frappe.msg_dialog.msg_area.empty();
	} else {
		msg_exists = frappe.msg_dialog.msg_area.html();
	}

	if(data.title || !msg_exists) {
		// set title only if it is explicitly given
		// and no existing title exists
		frappe.msg_dialog.set_title(data.title || __('Message'));
	}

	// show / hide indicator
	if(data.indicator) {
		frappe.msg_dialog.indicator.removeClass().addClass('indicator ' + data.indicator);
	} else {
		frappe.msg_dialog.indicator.removeClass().addClass('hidden');
	}

	// width
	if (data.wide) {
		// msgprint should be narrower than the usual dialog
		if (frappe.msg_dialog.wrapper.classList.contains('msgprint-dialog')) {
			frappe.msg_dialog.wrapper.classList.remove('msgprint-dialog');
		}
	} else {
		// msgprint should be narrower than the usual dialog
		frappe.msg_dialog.wrapper.classList.add('msgprint-dialog');
	}

	if (data.scroll) {
		// limit modal height and allow scrolling instead
		frappe.msg_dialog.body.classList.add('msgprint-scroll');
	} else {
		if (frappe.msg_dialog.body.classList.contains('msgprint-scroll')) {
			frappe.msg_dialog.body.classList.remove('msgprint-scroll');
		}
	}


	if(msg_exists) {
		frappe.msg_dialog.msg_area.append("<hr>");
	// append a <hr> if another msg already exists
	}

	frappe.msg_dialog.msg_area.append(data.message);

	// make msgprint always appear on top
	frappe.msg_dialog.$wrapper.css("z-index", 2000);
	frappe.msg_dialog.show();

	return frappe.msg_dialog;
}

window.msgprint = frappe.msgprint;

frappe.hide_msgprint = function(instant) {
	// clear msgprint
	if(frappe.msg_dialog && frappe.msg_dialog.msg_area) {
		frappe.msg_dialog.msg_area.empty();
	}
	if(frappe.msg_dialog && frappe.msg_dialog.$wrapper.is(":visible")) {
		if(instant) {
			frappe.msg_dialog.$wrapper.removeClass("fade");
		}
		frappe.msg_dialog.hide();
		if(instant) {
			frappe.msg_dialog.$wrapper.addClass("fade");
		}
	}
}

// update html in existing msgprint
frappe.update_msgprint = function(html) {
	if(!frappe.msg_dialog || (frappe.msg_dialog && !frappe.msg_dialog.$wrapper.is(":visible"))) {
		frappe.msgprint(html);
	} else {
		frappe.msg_dialog.msg_area.html(html);
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
			<div class="alert-message small"></div>
			<div class="alert-body" style="display: none"></div>
			<a class="close">&times;</a>
		</div>`);

	if(message.indicator) {
		div.find('.alert-message').append(`<span class="indicator ${message.indicator}"></span>`);
	}

	div.find('.alert-message').append(message.message);

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
