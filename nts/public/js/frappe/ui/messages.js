// Copyright (c) 2015, nts Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

nts.provide("nts.messages");

import "./dialog";

nts.messages.waiting = function (parent, msg) {
	return $(nts.messages.get_waiting_message(msg)).appendTo(parent);
};

nts.messages.get_waiting_message = function (msg) {
	return repl(
		'<div class="msg-box" style="width: 63%; margin: 30px auto;">\
		<p class="text-center">%(msg)s</p></div>',
		{ msg: msg }
	);
};

nts.throw = function (msg) {
	if (typeof msg === "string") {
		msg = { message: msg, title: __("Error") };
	}
	if (!msg.indicator) msg.indicator = "red";
	nts.msgprint(msg);
	throw new Error(msg.message);
};

nts.confirm = function (message, confirm_action, reject_action) {
	var d = new nts.ui.Dialog({
		title: __("Confirm", null, "Title of confirmation dialog"),
		primary_action_label: __("Yes", null, "Approve confirmation dialog"),
		primary_action: () => {
			confirm_action && confirm_action();
			d.hide();
		},
		secondary_action_label: __("No", null, "Dismiss confirmation dialog"),
		secondary_action: () => d.hide(),
	});

	d.$body.append(`<p class="nts-confirm-message">${message}</p>`);
	d.show();

	// flag, used to bind "okay" on enter
	d.confirm_dialog = true;

	// no if closed without primary action
	if (reject_action) {
		d.onhide = () => {
			if (!d.primary_action_fulfilled) {
				reject_action();
			}
		};
	}

	return d;
};

nts.warn = function (title, message_html, proceed_action, primary_label, is_minimizable) {
	const d = new nts.ui.Dialog({
		title: title,
		indicator: "red",
		primary_action_label: primary_label,
		primary_action: () => {
			if (proceed_action) proceed_action();
			d.hide();
		},
		secondary_action_label: __("Cancel", null, "Secondary button in warning dialog"),
		secondary_action: () => d.hide(),
		minimizable: is_minimizable,
	});

	d.$body.append(`<div class="nts-confirm-message">${message_html}</div>`);
	d.standard_actions.find(".btn-primary").removeClass("btn-primary").addClass("btn-danger");

	d.show();
	return d;
};

nts.prompt = function (fields, callback, title, primary_label) {
	if (typeof fields === "string") {
		fields = [
			{
				label: fields,
				fieldname: "value",
				fieldtype: "Data",
				reqd: 1,
			},
		];
	}
	if (!$.isArray(fields)) fields = [fields];
	var d = new nts.ui.Dialog({
		fields: fields,
		title: title || __("Enter Value", null, "Title of prompt dialog"),
	});
	d.set_primary_action(
		primary_label || __("Submit", null, "Primary action of prompt dialog"),
		function () {
			var values = d.get_values();
			if (!values) {
				return;
			}
			d.hide();
			callback(values);
		}
	);
	d.show();
	return d;
};

nts.msgprint = function (msg, title, is_minimizable) {
	if (!msg) return;

	let data;
	if ($.isPlainObject(msg)) {
		data = msg;
	} else {
		// passed as JSON
		if (typeof msg === "string" && msg.substr(0, 1) === "{") {
			data = JSON.parse(msg);
		} else {
			data = { message: msg, title: title };
		}
	}

	if (!data.indicator) {
		data.indicator = "blue";
	}

	if (data.as_list) {
		const list_rows = data.message.map((m) => `<li>${m}</li>`).join("");
		data.message = `<ul style="padding-left: 20px">${list_rows}</ul>`;
	}

	if (data.as_table) {
		const rows = data.message
			.map((row) => {
				const cols = row.map((col) => `<td>${col}</td>`).join("");
				return `<tr>${cols}</tr>`;
			})
			.join("");
		data.message = `<table class="table table-bordered" style="margin: 0;">${rows}</table>`;
	}

	if (data.message instanceof Array) {
		let messages = data.message;
		const exceptions = messages
			.map((m) => {
				if (typeof m == "string") {
					return JSON.parse(m);
				} else {
					return m;
				}
			})
			.filter((m) => m.raise_exception);

		// only show exceptions if any exceptions exist
		if (exceptions.length) {
			messages = exceptions;
		}

		messages.forEach(function (m) {
			nts.msgprint(m);
		});
		return;
	}

	if (data.alert || data.toast) {
		nts.show_alert(data);
		return;
	}

	if (!nts.msg_dialog) {
		nts.msg_dialog = new nts.ui.Dialog({
			title: __("Message"),
			onhide: function () {
				if (nts.msg_dialog.custom_onhide) {
					nts.msg_dialog.custom_onhide();
				}
				nts.msg_dialog.msg_area.empty();
			},
			minimizable: data.is_minimizable || is_minimizable,
		});

		// class "msgprint" is used in tests
		nts.msg_dialog.msg_area = $('<div class="msgprint">').appendTo(nts.msg_dialog.body);

		nts.msg_dialog.clear = function () {
			nts.msg_dialog.msg_area.empty();
		};

		nts.msg_dialog.indicator = nts.msg_dialog.header.find(".indicator");
	}

	// setup and bind an action to the primary button
	if (data.primary_action) {
		if (
			data.primary_action.server_action &&
			typeof data.primary_action.server_action === "string"
		) {
			data.primary_action.action = () => {
				nts.call({
					method: data.primary_action.server_action,
					args: {
						args: data.primary_action.args,
					},
					callback() {
						if (data.primary_action.hide_on_success) {
							nts.hide_msgprint();
						}
					},
				});
			};
		}

		if (
			data.primary_action.client_action &&
			typeof data.primary_action.client_action === "string"
		) {
			let parts = data.primary_action.client_action.split(".");
			let obj = window;
			for (let part of parts) {
				obj = obj[part];
			}
			data.primary_action.action = () => {
				if (typeof obj === "function") {
					obj(data.primary_action.args);
				}
			};
		}

		nts.msg_dialog.set_primary_action(
			__(data.primary_action.label) || __(data.primary_action_label) || __("Done"),
			data.primary_action.action
		);
	} else {
		if (nts.msg_dialog.has_primary_action) {
			nts.msg_dialog.get_primary_btn().addClass("hide");
			nts.msg_dialog.has_primary_action = false;
		}
	}

	if (data.secondary_action) {
		nts.msg_dialog.set_secondary_action(data.secondary_action.action);
		nts.msg_dialog.set_secondary_action_label(
			__(data.secondary_action.label) || __("Close")
		);
	}

	if (data.message == null) {
		data.message = "";
	}

	if (data.message.search(/<br>|<p>|<li>/) == -1) {
		msg = nts.utils.replace_newlines(data.message);
	}

	var msg_exists = false;
	if (data.clear) {
		nts.msg_dialog.msg_area.empty();
	} else {
		msg_exists = nts.msg_dialog.msg_area.html();
	}

	if (data.title || !msg_exists) {
		// set title only if it is explicitly given
		// and no existing title exists
		nts.msg_dialog.set_title(
			data.title || __("Message", null, "Default title of the message dialog")
		);
	}

	// show / hide indicator
	if (data.indicator) {
		nts.msg_dialog.indicator.removeClass().addClass("indicator " + data.indicator);
	} else {
		nts.msg_dialog.indicator.removeClass().addClass("hidden");
	}

	// width
	if (data.wide) {
		// msgprint should be narrower than the usual dialog
		if (nts.msg_dialog.wrapper.classList.contains("msgprint-dialog")) {
			nts.msg_dialog.wrapper.classList.remove("msgprint-dialog");
		}
	} else {
		// msgprint should be narrower than the usual dialog
		nts.msg_dialog.wrapper.classList.add("msgprint-dialog");
	}

	if (msg_exists) {
		nts.msg_dialog.msg_area.append("<hr>");
		// append a <hr> if another msg already exists
	}

	nts.msg_dialog.msg_area.append(data.message);

	// make msgprint always appear on top
	nts.msg_dialog.$wrapper.css("z-index", 2000);
	nts.msg_dialog.show();

	return nts.msg_dialog;
};

window.msgprint = nts.msgprint;

nts.hide_msgprint = function (instant) {
	// clear msgprint
	if (nts.msg_dialog && nts.msg_dialog.msg_area) {
		nts.msg_dialog.msg_area.empty();
	}
	if (nts.msg_dialog && nts.msg_dialog.$wrapper.is(":visible")) {
		if (instant) {
			nts.msg_dialog.$wrapper.removeClass("fade");
		}
		nts.msg_dialog.hide();
		if (instant) {
			nts.msg_dialog.$wrapper.addClass("fade");
		}
	}
};

// update html in existing msgprint
nts.update_msgprint = function (html) {
	if (!nts.msg_dialog || (nts.msg_dialog && !nts.msg_dialog.$wrapper.is(":visible"))) {
		nts.msgprint(html);
	} else {
		nts.msg_dialog.msg_area.html(html);
	}
};

nts.verify_password = function (callback) {
	nts.prompt(
		{
			fieldname: "password",
			label: __("Enter your password"),
			fieldtype: "Password",
			reqd: 1,
		},
		function (data) {
			nts.call({
				method: "nts.core.doctype.user.user.verify_password",
				args: {
					password: data.password,
				},
				callback: function (r) {
					if (!r.exc) {
						callback();
					}
				},
			});
		},
		__("Verify Password"),
		__("Verify")
	);
};

nts.show_progress = (title, count, total = 100, description, hide_on_completion = false) => {
	let dialog;
	if (
		nts.cur_progress &&
		nts.cur_progress.title === title &&
		nts.cur_progress.is_visible
	) {
		dialog = nts.cur_progress;
	} else {
		dialog = new nts.ui.Dialog({
			title: title,
		});
		dialog.progress = $(`<div>
			<div class="progress">
				<div class="progress-bar"></div>
			</div>
			<p class="description text-muted small"></p>
		</div`).appendTo(dialog.body);
		dialog.progress_bar = dialog.progress.css({ "margin-top": "10px" }).find(".progress-bar");
		dialog.$wrapper.removeClass("fade");
		dialog.show();
		nts.cur_progress = dialog;
	}
	if (description) {
		dialog.progress.find(".description").text(description);
	}
	dialog.percent = cint((flt(count) * 100) / total);
	dialog.progress_bar.css({ width: dialog.percent + "%" });
	if (hide_on_completion && dialog.percent === 100) {
		// timeout to avoid abrupt hide
		setTimeout(nts.hide_progress, 500);
	}
	nts.cur_progress.$wrapper.css("z-index", 2000);
	return dialog;
};

nts.hide_progress = function () {
	if (nts.cur_progress) {
		nts.cur_progress.hide();
		nts.cur_progress = null;
	}
};

// Floating Message
nts.show_alert = nts.toast = function (message, seconds = 7, actions = {}) {
	let indicator_icon_map = {
		orange: "solid-warning",
		yellow: "solid-warning",
		blue: "solid-info",
		green: "solid-success",
		red: "solid-error",
	};

	if (typeof message === "string") {
		message = {
			message: message,
		};
	}

	if (!$("#dialog-container").length) {
		$('<div id="dialog-container"><div id="alert-container"></div></div>').appendTo("body");
	}

	let icon;
	if (message.indicator) {
		icon = indicator_icon_map[message.indicator.toLowerCase()] || "solid-" + message.indicator;
	} else {
		icon = "solid-info";
	}

	const indicator = message.indicator || "blue";

	const div = $(`
		<div class="alert desk-alert ${indicator}" role="alert">
			<div class="alert-message-container">
				<div class="alert-title-container">
					<div>${nts.utils.icon(icon, "lg")}</div>
					<div class="alert-message">${message.message}</div>
				</div>
				<div class="alert-subtitle">${message.subtitle || ""}</div>
			</div>
			<div class="alert-body" style="display: none"></div>
			<a class="close">${nts.utils.icon("close-alt")}</a>
		</div>
	`);

	div.hide().appendTo("#alert-container").show();

	if (message.body) {
		div.find(".alert-body").show().html(message.body);
	}

	div.find(".close, button").click(function () {
		div.addClass("out");
		setTimeout(() => div.remove(), 800);
		return false;
	});

	Object.keys(actions).map((key) => {
		div.find(`[data-action=${key}]`).on("click", actions[key]);
	});

	if (seconds > 2) {
		// Delay for animation
		seconds = seconds - 0.8;
	}

	setTimeout(() => {
		div.addClass("out");
		setTimeout(() => div.remove(), 800);
		return false;
	}, seconds * 1000);

	return div;
};
