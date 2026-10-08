import { validated } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ToastOpts
 * @property {string} [message] Toast text. HTML-escaped.
 * @property {string} [description] Optional second line. HTML-escaped.
 * @property {"message"|"info"|"success"|"warning"|"error"} [type="message"] "message" is plain — no icon unless you pass one.
 * @property {number} [duration=5000] Auto-dismiss after this many milliseconds; 0 keeps the toast until closed.
 * @property {string} [icon] Lucide icon name — overrides the type's icon.
 * @property {string} [icon_class] Extra classes for the icon, e.g. "text-ink-violet-5" to recolor it.
 * @property {boolean} [closable=true] Shows a close button.
 * @property {Object} [action] Button on the right: { label, onclick }.
 * @property {string} [id] Showing another toast with the same id updates it in place instead of adding a new one.
 */

const TYPES = ["message", "info", "success", "warning", "error"];

// info/success/warning/error use lucide icons; "message" has none
const TYPE_ICONS = {
	info: "info",
	success: "circle-check",
	warning: "triangle-alert",
	error: "circle-x",
};

// live toasts by id, so a repeat id updates instead of stacking
const active = new Map();

function get_container() {
	let container = document.querySelector(".es-toast-container");
	if (!container) {
		container = $('<div class="es-toast-container"></div>').appendTo("body")[0];
	}
	return $(container);
}

function render_content($el, opts) {
	const escape = frappe.utils.escape_html;
	const type = validated(opts.type, TYPES, "type", "toast") || "message";

	$el.attr("data-type", type);
	// errors interrupt politely; everything else waits its turn
	$el.attr("role", type === "error" ? "alert" : "status");

	const icon_name = opts.icon || TYPE_ICONS[type];
	const icon = opts.loading
		? '<span class="es-spinner" aria-hidden="true"></span>'
		: icon_name
		? frappe.utils.icon(icon_name, "sm", "", "", escape(opts.icon_class || ""), true)
		: "";
	const description = opts.description
		? `<div class="es-toast__description">${escape(opts.description)}</div>`
		: "";
	const action = opts.action
		? `<button class="es-toast__action" type="button">${escape(opts.action.label)}</button>`
		: "";
	// the extra "close" class is a legacy hook — old code dismisses the
	// element show_alert returned via .find(".close").click()
	const close =
		opts.closable === false
			? ""
			: `<button class="es-toast__close close" type="button" aria-label="${escape(
					__("Close")
			  )}">${frappe.utils.icon("x", "sm", "", "", "", true)}</button>`;

	$el.html(
		`${icon}<div class="es-toast__content"><div class="es-toast__message">${escape(
			opts.message || ""
		)}</div>${description}</div>${action}${close}`
	);

	if (opts.action && opts.action.onclick) {
		$el.find(".es-toast__action").on("click", opts.action.onclick);
	}
}

/**
 * Show a floating toast, bottom-right.
 * Reusing an `id` updates the existing toast in place (and restarts its
 * timer) — handy for progress flows. See also frappe.ui.toast.promise.
 * @param {ToastOpts} [opts]
 * @returns {{ id: string, $el: JQuery, dismiss: function, update: function }}
 * @example frappe.ui.toast({ message: __("Saved"), type: "success" });
 */
frappe.ui.toast = function (opts = {}) {
	const id = opts.id || frappe.utils.get_random(10);

	// same id: update the existing toast instead of stacking a copy
	const existing = active.get(id);
	if (existing) {
		existing.set(opts);
		return existing.handle;
	}

	const $el = $('<div class="es-toast"></div>');
	let timer = null;

	const dismiss = () => {
		clearTimeout(timer);
		active.delete(id);
		$el.addClass("es-toast--out");
		setTimeout(() => $el.remove(), 250);
	};

	const start_timer = (duration) => {
		clearTimeout(timer);
		if (duration > 0) timer = setTimeout(dismiss, duration);
	};

	const set = (new_opts) => {
		render_content($el, new_opts);
		$el.find(".es-toast__close").on("click", dismiss);
		start_timer(new_opts.duration == null ? 5000 : new_opts.duration);
	};

	// hovering or keyboard-focusing pauses the countdown (so the action
	// button is reachable by tab); leaving restarts it in full
	let current_opts = opts;
	const current_duration = () => (current_opts.duration == null ? 5000 : current_opts.duration);
	$el.on("mouseenter focusin", () => clearTimeout(timer));
	$el.on("mouseleave focusout", () => start_timer(current_duration()));

	const handle = {
		id,
		$el,
		dismiss,
		// partial updates keep everything not mentioned — update({ type })
		// changes the color without losing the message or action
		update: (new_opts) => {
			current_opts = { ...current_opts, ...new_opts };
			set(current_opts);
		},
	};

	active.set(id, { handle, set: handle.update });
	set(current_opts);
	$el.appendTo(get_container());
	return handle;
};

/**
 * Toast that follows a promise: shows a spinner while pending, then flips
 * to success or error. Returns the original promise, so chain as usual.
 * @param {Promise} promise
 * @param {{ loading?: string, success?: string|function, error?: string|function }} [messages]
 * @returns {Promise}
 * @example frappe.ui.toast.promise(frm.save(), { loading: __("Saving..."), success: __("Saved") });
 */
frappe.ui.toast.promise = function (promise, messages = {}) {
	const handle = frappe.ui.toast({
		message: messages.loading || __("Working..."),
		loading: true,
		closable: false,
		duration: 0,
	});
	const text = (value, result) => (typeof value === "function" ? value(result) : value);
	// update() keeps anything not mentioned, so the loading state has to be
	// switched off explicitly — otherwise the spinner and the no-timer
	// setting from the pending toast would stick around
	const settle = (message, type) =>
		handle.update({
			message,
			type,
			loading: false,
			closable: true,
			duration: messages.duration == null ? 5000 : messages.duration,
		});
	promise.then(
		(result) => settle(text(messages.success, result) || __("Done"), "success"),
		(err) => settle(text(messages.error, err) || __("Something went wrong"), "error")
	);
	return promise;
};

export default frappe.ui.toast;
