import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} AlertOpts
 * @property {string} [title] Main message. HTML-escaped.
 * @property {string} [description] Supporting text below the title. HTML-escaped. Stacks the alert: the actions move under the message.
 * @property {"yellow"|"blue"|"red"|"green"|"amber"} [theme] Colors the icon and the inline action's label, and picks the icon ("amber" means yellow). No theme = gray, no icon.
 * @property {"subtle"|"outline"} [variant="subtle"]
 * @property {string} [icon] Lucide icon name — overrides the theme's icon (or adds one to a plain alert).
 * @property {Object} [primary_action] frappe.ui.button options (label, onclick, ...) for the alert's button. It sits inline after the title, or under the message when the alert has a description or a second action (element form only).
 * @property {Object} [secondary_action] frappe.ui.button options for a second button. Stacks the alert (element form only).
 * @property {Element|JQuery|function} [footer] Your own content beside the action buttons — an element, or a function returning one (element form only).
 * @property {boolean} [dismissible] Shows a close button. It only works in the element form, which removes the alert and calls on_dismiss.
 * @property {function} [on_dismiss] Called after the alert is dismissed (element form only).
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const THEMES = ["yellow", "blue", "red", "green"];
const VARIANTS = ["subtle", "outline"];

// the solid status glyphs frappe-ui's Alert uses
const THEME_ICONS = {
	yellow: "triangle-alert-solid",
	blue: "info-solid",
	red: "circle-x-solid",
	green: "circle-check-solid",
};

const is_banner = (opts) => Boolean(opts.description || opts.secondary_action);

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
	const banner = is_banner(opts);

	const attrs = ['role="alert"'];
	if (banner) attrs.push('data-layout="banner"');
	if (theme) attrs.push(`data-theme="${theme}"`);
	if (variant && variant !== "subtle") attrs.push(`data-variant="${variant}"`);
	attrs.push(...safe_attrs(opts.attrs, "alert"));

	const icon_name = opts.icon || (theme && THEME_ICONS[theme]);
	const icon = icon_name ? frappe.utils.icon(icon_name, "sm", "", "", "", true) : "";
	if ((opts.primary_action || opts.secondary_action || opts.footer) && !opts._element_form) {
		console.warn(
			"frappe.ui.alert: actions and footer need the element form — frappe.ui.alert(opts)"
		);
	}
	const title = `<span class="es-alert__title">${escape(opts.title || "")}</span>`;
	const description = opts.description
		? `<p class="es-alert__description">${escape(opts.description)}</p>`
		: "";
	const dismiss = opts.dismissible
		? frappe.ui.button.html({
				icon: "x",
				variant: "ghost",
				size: banner ? "xs" : "sm",
				css_class: "es-alert__dismiss",
				attrs: { "aria-label": __("Dismiss") },
		  })
		: "";
	const content = banner
		? `<div class="es-alert__head">${icon}${title}</div><div class="es-alert__body">${description}</div>`
		: `${icon}${title}`;

	const classes = escape(["es-alert", opts.css_class].filter(Boolean).join(" "));
	return `<div class="${classes}" ${attrs.join(" ")}>${content}${dismiss}</div>`;
}

// The alert's own look (themed label inline, raised button when stacked) is
// keyed off .es-alert__action, which a button the caller restyled does not get.
function action_button(action, defaults) {
	const restyled = action.variant || action.theme;
	return frappe.ui.button({
		...defaults,
		...action,
		css_class: [!restyled && "es-alert__action", action.css_class].filter(Boolean).join(" "),
	});
}

/**
 * Espresso alert as a jQuery element. The dismiss button removes the alert
 * and calls `on_dismiss`.
 * @param {AlertOpts} [opts]
 * @returns {JQuery}
 * @example frappe.ui.alert({ title: __("Saved"), theme: "green", dismissible: true }).prependTo($section);
 * @example frappe.ui.alert({ title: __("Permissions have been customized."), theme: "yellow", primary_action: { label: __("Reset"), onclick: reset } });
 */
frappe.ui.alert = function (opts = {}) {
	const $el = $(alert_html({ ...opts, _element_form: true }));
	const banner = is_banner(opts);
	if (opts.dismissible) {
		$el.find(".es-alert__dismiss").on("click", () => {
			$el.remove();
			opts.on_dismiss && opts.on_dismiss();
		});
	}

	const actions = [];
	if (opts.primary_action) {
		actions.push(
			action_button(
				opts.primary_action,
				banner ? { variant: "outline", size: "md" } : { variant: "ghost" }
			)
		);
	}
	if (opts.secondary_action) {
		actions.push(action_button(opts.secondary_action, { variant: "ghost", size: "md" }));
	}
	if (opts.footer) {
		actions.push(
			...[].concat(typeof opts.footer === "function" ? opts.footer() : opts.footer)
		);
	}
	if (actions.length) {
		const $actions = $('<div class="es-alert__actions"></div>').append(actions);
		if (banner) $actions.appendTo($el.find(".es-alert__body"));
		else $actions.insertAfter($el.find(".es-alert__title"));
	}
	return $el;
};

frappe.ui.alert.html = alert_html;

export default frappe.ui.alert;
