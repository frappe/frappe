// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.messages");

import "./dialog";
import { has_unsafe_scheme } from "./components/utils.js";

frappe.messages.waiting = function (parent, msg) {
	return $(frappe.messages.get_waiting_message(msg)).appendTo(parent);
};

frappe.messages.get_waiting_message = function (msg) {
	return repl(
		'<div class="msg-box" style="width: 63%; margin: 30px auto;">\
		<p class="text-center">%(msg)s</p></div>',
		{ msg: msg }
	);
};

frappe.throw = function (msg) {
	if (typeof msg === "string") {
		msg = { message: msg, title: __("Error") };
	}
	if (!msg.indicator) msg.indicator = "red";
	frappe.msgprint(msg);
	throw new Error(msg.message);
};

frappe.confirm = function (
	message,
	confirm_action,
	reject_action,
	primary_label,
	secondary_label
) {
	var d = new frappe.ui.Dialog({
		title: __("Confirm", null, "Title of confirmation dialog"),
		primary_action_label: __(primary_label || "Yes", null, "Approve confirmation dialog"),
		primary_action: () => {
			confirm_action && confirm_action();
			d.hide();
		},
		secondary_action_label: __(secondary_label || "No", null, "Dismiss confirmation dialog"),
		secondary_action: () => d.hide(),
	});

	d.$body.append(`<p class="frappe-confirm-message">${message}</p>`);
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

frappe.warn = function (
	title,
	message_html,
	proceed_action,
	primary_label,
	is_minimizable,
	secondary_label
) {
	const d = new frappe.ui.Dialog({
		title: title,
		indicator: "red",
		primary_action_label: primary_label,
		primary_action: () => {
			if (proceed_action) proceed_action();
			d.hide();
		},
		// "Cancel" reads wrong when the ACTION is cancelling something —
		// those callers pass "No" instead
		secondary_action_label:
			secondary_label || __("Cancel", null, "Secondary button in warning dialog"),
		secondary_action: () => d.hide(),
		minimizable: is_minimizable,
	});

	// flag, used to bind "okay" on enter
	d.confirm_dialog = true;

	d.$body.append(`<div class="frappe-confirm-message">${message_html}</div>`);
	// destructive confirm: the es-button red theme replaces the old
	// btn-primary → btn-danger class swap
	d.get_primary_btn().attr("data-theme", "red");

	d.show();
	return d;
};

frappe.prompt = function (fields, callback, title, primary_label) {
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
	var d = new frappe.ui.Dialog({
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

frappe.msgprint = function (msg, title, is_minimizable, re_route) {
	if (!msg) return;
	let data;
	if ($.isPlainObject(msg)) {
		data = msg;
	} else {
		// passed as JSON
		if (typeof msg === "string" && msg.substr(0, 1) === "{") {
			data = JSON.parse(msg);
		} else {
			data = { message: msg, title: title, re_route: re_route };
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
			frappe.msgprint(m);
		});
		return;
	}

	if (data.alert || data.toast) {
		frappe.show_alert(data);
		return;
	}

	if (frappe.msg_dialog && data.re_route) {
		frappe.msg_dialog.custom_onhide = function () {
			frappe.route_flags.replace_route = true;
			let prev_route = frappe.get_prev_route();
			if (prev_route.length == 0) frappe.set_route("");
			frappe.set_route(prev_route);
		};
	}
	if (!frappe.msg_dialog) {
		frappe.msg_dialog = new frappe.ui.Dialog({
			title: __("Message"),
			onhide: function () {
				if (frappe.msg_dialog.custom_onhide) {
					frappe.msg_dialog.custom_onhide();
					delete frappe.msg_dialog.custom_onhide;
				}
				frappe.msg_dialog.msg_area.empty();
			},
			minimizable: data.is_minimizable || is_minimizable,
		});

		// class "msgprint" is used in tests
		frappe.msg_dialog.msg_area = $('<div class="msgprint">').appendTo(frappe.msg_dialog.body);

		frappe.msg_dialog.clear = function () {
			frappe.msg_dialog.msg_area.empty();
		};

		frappe.msg_dialog.indicator = frappe.msg_dialog.header.find(".indicator");
	}

	// setup and bind an action to the primary button
	if (data.primary_action) {
		if (
			data.primary_action.server_action &&
			typeof data.primary_action.server_action === "string"
		) {
			data.primary_action.action = () => {
				return frappe.call({
					method: data.primary_action.server_action,
					args: data.primary_action.args,
					callback() {
						if (data.primary_action.hide_on_success) {
							frappe.hide_msgprint();
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

		frappe.msg_dialog.set_primary_action(
			__(data.primary_action.label) || __(data.primary_action_label) || __("Done"),
			data.primary_action.action
		);
	} else {
		if (frappe.msg_dialog.has_primary_action) {
			frappe.msg_dialog.get_primary_btn().addClass("hide");
			frappe.msg_dialog.has_primary_action = false;
		}
	}

	if (data.secondary_action) {
		frappe.msg_dialog.set_secondary_action(data.secondary_action.action);
		frappe.msg_dialog.set_secondary_action_label(
			__(data.secondary_action.label) || __("Close")
		);
	}

	if (data.message == null) {
		data.message = "";
	}

	if (data.message.search(/<br>|<p>|<li>/) == -1) {
		msg = frappe.utils.replace_newlines(data.message);
	}

	var msg_exists = false;
	if (data.clear) {
		frappe.msg_dialog.msg_area.empty();
	} else {
		msg_exists = frappe.msg_dialog.msg_area.html();
	}

	if (data.title || !msg_exists) {
		// set title only if it is explicitly given
		// and no existing title exists
		frappe.msg_dialog.set_title(
			data.title || __("Message", null, "Default title of the message dialog")
		);
	}

	// show / hide indicator
	if (data.indicator) {
		frappe.msg_dialog.indicator.removeClass().addClass("indicator " + data.indicator);
	} else {
		frappe.msg_dialog.indicator.removeClass().addClass("hidden");
	}

	// width
	if (data.wide) {
		// msgprint should be narrower than the usual dialog
		if (frappe.msg_dialog.wrapper.classList.contains("msgprint-dialog")) {
			frappe.msg_dialog.wrapper.classList.remove("msgprint-dialog");
		}
	} else {
		// msgprint should be narrower than the usual dialog
		frappe.msg_dialog.wrapper.classList.add("msgprint-dialog");
	}

	if (msg_exists) {
		frappe.msg_dialog.msg_area.append("<hr>");
		// append a <hr> if another msg already exists
	}

	frappe.msg_dialog.msg_area.append(data.message);

	// make msgprint always appear on top
	frappe.msg_dialog.$wrapper.css("z-index", 2000);
	frappe.msg_dialog.show();

	return frappe.msg_dialog;
};

window.msgprint = frappe.msgprint;

frappe.hide_msgprint = function (instant) {
	// clear msgprint
	if (frappe.msg_dialog && frappe.msg_dialog.msg_area) {
		frappe.msg_dialog.msg_area.empty();
	}
	if (frappe.msg_dialog && frappe.msg_dialog.$wrapper.is(":visible")) {
		if (instant) {
			frappe.msg_dialog.$wrapper.removeClass("fade");
		}
		frappe.msg_dialog.hide();
		if (instant) {
			frappe.msg_dialog.$wrapper.addClass("fade");
		}
	}
};

// update html in existing msgprint
frappe.update_msgprint = function (html) {
	if (!frappe.msg_dialog || (frappe.msg_dialog && !frappe.msg_dialog.$wrapper.is(":visible"))) {
		frappe.msgprint(html);
	} else {
		frappe.msg_dialog.msg_area.html(html);
	}
};

frappe.verify_password = function (callback) {
	frappe.prompt(
		{
			fieldname: "password",
			label: __("Enter your password"),
			fieldtype: "Password",
			reqd: 1,
		},
		function (data) {
			frappe.call({
				method: "frappe.core.doctype.user.user.verify_password",
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

frappe.show_progress = (title, count, total = 100, description, hide_on_completion = false) => {
	let dialog;
	if (
		frappe.cur_progress &&
		frappe.cur_progress.title === title &&
		frappe.cur_progress.is_visible
	) {
		dialog = frappe.cur_progress;
	} else {
		dialog = new frappe.ui.Dialog({
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
		frappe.cur_progress = dialog;
	}
	if (description) {
		dialog.progress.find(".description").text(description);
	}
	dialog.percent = cint((flt(count) * 100) / total);
	dialog.progress_bar.css({ width: dialog.percent + "%" });
	if (hide_on_completion && dialog.percent === 100) {
		// timeout to avoid abrupt hide
		setTimeout(frappe.hide_progress, 500);
	}
	frappe.cur_progress.$wrapper.css("z-index", 2000);
	return dialog;
};

frappe.hide_progress = function () {
	if (frappe.cur_progress) {
		frappe.cur_progress.hide();
		frappe.cur_progress = null;
	}
};

// Floating Message
frappe.show_alert = frappe.toast = function (message, seconds = 7, actions = {}) {
	if (typeof message === "string") {
		message = { message: message };
	}

	const type_map = {
		green: "success",
		red: "error",
		orange: "warning",
		yellow: "warning",
		blue: "info",
	};
	const indicator = (message.indicator || "blue").toLowerCase();

	const handle = frappe.ui.toast({
		type: type_map[indicator] || "info",
		duration: seconds * 1000,
	});

	// legacy messages may contain html (e.g. an inline Undo link) — keep the
	// tags, strip the script vectors
	const sane = (html) => frappe.utils.xss_sanitise(String(html), { strategies: ["js"] });
	// xss_sanitise doesn't remove on*-handler attributes or javascript: links
	// (its own TODO says so) — strip those from the real DOM after inserting.
	// has_unsafe_scheme normalizes the value the way the browser does before
	// checking, so a scheme hidden behind "java&#9;script:" or a leading
	// control char can't slip past (see components/utils.js).
	const harden = ($root) => {
		$root.find("*").each(function () {
			for (const attr of Array.from(this.attributes)) {
				if (/^on/i.test(attr.name)) this.removeAttribute(attr.name);
				else if (
					["href", "src", "action", "formaction"].includes(attr.name) &&
					has_unsafe_scheme(attr.value)
				) {
					this.removeAttribute(attr.name);
				}
			}
		});
		return $root;
	};
	// legacy alerts could also pass a DOM element or jQuery for any of these
	// channels (e.g. success_action's next-action buttons) — append those as
	// they are, with their event bindings intact; stringifying them would
	// print "[object Object]". Strings go through sanitise + harden as before.
	const fill = ($target, content) => {
		if (content && (content.jquery || content.nodeType)) {
			return $target.append(content);
		}
		return harden($target.html(sane(content)));
	};
	fill(handle.$el.find(".es-toast__message"), message.message || "");
	if (message.subtitle) {
		fill(
			$('<div class="es-toast__description"></div>').appendTo(
				handle.$el.find(".es-toast__content")
			),
			message.subtitle
		);
	}
	if (message.body) {
		fill(
			$('<div class="es-toast__body"></div>').appendTo(
				handle.$el.find(".es-toast__content")
			),
			message.body
		);
	}

	Object.keys(actions).map((key) => {
		handle.$el.find(`[data-action=${key}]`).on("click", actions[key]);
	});

	// old callers hold the element to dismiss it later
	return handle.$el;
};
