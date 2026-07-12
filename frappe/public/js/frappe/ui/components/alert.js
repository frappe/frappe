import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} AlertOpts
 * @property {string} [title] Main message. HTML-escaped.
 * @property {string} [description] Supporting text below the title. HTML-escaped.
 * @property {"yellow"|"blue"|"red"|"green"|"amber"} [theme] Colors the banner and picks its icon ("amber" means yellow). No theme = plain gray, no icon.
 * @property {"subtle"|"outline"} [variant="subtle"]
 * @property {string} [icon] Lucide icon name — overrides the theme's icon (or adds one to a plain alert).
 * @property {Element|JQuery|function} [footer] Content under the message, e.g. action buttons — an element, or a function returning one (element form only).
 * @property {boolean} [dismissible] Shows a close button. It only works in the element form, which removes the alert and calls on_dismiss.
 * @property {function} [on_dismiss] Called after the alert is dismissed (element form only).
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const THEMES = ["yellow", "blue", "red", "green"];
const VARIANTS = ["subtle", "outline"];

// which icon goes with which theme (same set frappe-ui uses)
const THEME_ICONS = {
	yellow: "triangle-alert",
	blue: "info",
	red: "circle-x",
	green: "circle-check",
};

/**
 * Espresso alert (`.es-alert`) as a markup string — a static message banner.
 * @param {AlertOpts} [opts]
 * @returns {string}
 * @example `${frappe.ui.alert.html({ title: __("This document is locked"), theme: "yellow" })}`
 */
function alert_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	// amber and yellow are the same thing here; the enum name comes from frappe-ui
	const theme_name = opts.theme === "amber" ? "yellow" : opts.theme;
	const theme = validated(theme_name, THEMES, "theme", "alert");
	const variant = validated(opts.variant, VARIANTS, "variant", "alert");

	const attrs = ['role="alert"'];
	if (theme) attrs.push(`data-theme="${theme}"`);
	if (variant && variant !== "subtle") attrs.push(`data-variant="${variant}"`);
	attrs.push(...safe_attrs(opts.attrs, "alert"));

	const icon_name = opts.icon || (theme && THEME_ICONS[theme]);
	const icon = icon_name ? frappe.utils.icon(icon_name, "sm", "", "", "", true) : "";
	if (opts.footer && !opts._element_form) {
		console.warn("frappe.ui.alert: footer needs the element form — frappe.ui.alert(opts)");
	}
	const description = opts.description
		? `<p class="es-alert__description">${escape(opts.description)}</p>`
		: "";
	const dismiss = opts.dismissible
		? `<button class="es-alert__dismiss" type="button" aria-label="${escape(
				__("Dismiss")
		  )}">${frappe.utils.icon("x", "sm", "", "", "", true)}</button>`
		: "";

	const classes = escape(["es-alert", opts.css_class].filter(Boolean).join(" "));
	return `<div class="${classes}" ${attrs.join(
		" "
	)}>${icon}<div class="es-alert__content"><span class="es-alert__title">${escape(
		opts.title || ""
	)}</span>${description}</div>${dismiss}</div>`;
}

/**
 * Espresso alert as a jQuery element. The dismiss button removes the alert
 * and calls `on_dismiss`.
 * @param {AlertOpts} [opts]
 * @returns {JQuery}
 * @example frappe.ui.alert({ title: __("Saved"), theme: "green", dismissible: true }).prependTo($section);
 */
frappe.ui.alert = function (opts = {}) {
	const $el = $(alert_html({ ...opts, _element_form: true }));
	if (opts.dismissible) {
		$el.find(".es-alert__dismiss").on("click", () => {
			$el.remove();
			opts.on_dismiss && opts.on_dismiss();
		});
	}
	if (opts.footer) {
		const footer = typeof opts.footer === "function" ? opts.footer() : opts.footer;
		$('<div class="es-alert__footer"></div>').append(footer).appendTo($el);
	}
	return $el;
};

frappe.ui.alert.html = alert_html;

export default frappe.ui.alert;
