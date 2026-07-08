frappe.provide("frappe.ui");

/**
 * @typedef {Object} ButtonOpts
 * @property {string} [label] Button text (pre-translated). HTML-escaped.
 * @property {string} [loading_label] Text shown while busy. Defaults for common labels (Save → Saving..., Delete → Deleting..., Submit → Submitting...); pass "" to opt out.
 * @property {"solid"|"subtle"|"outline"|"ghost"} [variant="subtle"]
 * @property {"xs"|"sm"|"md"|"lg"} [size="sm"]
 * @property {"gray"|"red"} [theme="gray"]
 * @property {string} [icon] Lucide icon name. Icon without label renders a square icon-button — pass `title`.
 * @property {string} [title] Tooltip; doubles as aria-label on icon-only buttons.
 * @property {boolean} [disabled]
 * @property {boolean} [loading] Shows spinner, blocks clicks, sets aria-busy.
 * @property {"button"|"submit"|"reset"} [type="button"]
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes, e.g. { "data-toggle": "dropdown" }.
 * @property {function} [onclick] Click handler (element form only). Return a promise to show the busy state until it settles.
 */

const VARIANTS = ["solid", "subtle", "outline", "ghost"];
const SIZES = ["xs", "sm", "md", "lg"];
const THEMES = ["gray", "red"];

function default_loading_label(label) {
	if (!label) return null;
	// keyed by translated label so it matches whenever the caller used __()
	const map = {
		[__("Save")]: __("Saving..."),
		[__("Delete")]: __("Deleting..."),
		[__("Submit")]: __("Submitting..."),
	};
	return map[label] || null;
}

function validated(value, allowed, option) {
	if (value == null) return null;
	if (!allowed.includes(value)) {
		console.warn(
			`frappe.ui.button: unknown ${option} "${value}" — expected ${allowed.join(" | ")}`
		);
		return null;
	}
	return value;
}

/**
 * Espresso button (`.es-button`) as a markup string, for template literals.
 * @param {ButtonOpts} [opts]
 * @returns {string}
 * @example `<div>${frappe.ui.button.html({ label: __("Load More") })}</div>`
 */
function button_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const variant = validated(opts.variant, VARIANTS, "variant");
	const size = validated(opts.size, SIZES, "size");
	const theme = validated(opts.theme, THEMES, "theme");
	const icon_only = Boolean(opts.icon && !opts.label);

	const attrs = [`type="${escape(opts.type || "button")}"`];
	// omit attributes that equal the CSS defaults (subtle / sm / gray)
	if (variant && variant !== "subtle") attrs.push(`data-variant="${variant}"`);
	if (size && size !== "sm") attrs.push(`data-size="${size}"`);
	if (theme && theme !== "gray") attrs.push(`data-theme="${theme}"`);
	if (icon_only) attrs.push('data-icon-button="true"');
	if (opts.loading) attrs.push('aria-busy="true"');
	if (opts.disabled) attrs.push("disabled");
	if (opts.title) {
		attrs.push(`title="${escape(opts.title)}"`);
		if (icon_only) attrs.push(`aria-label="${escape(opts.title)}"`);
	}
	for (const [key, value] of Object.entries(opts.attrs || {})) {
		// attribute names become markup (computed keys can carry user data,
		// e.g. fieldnames), so enforce a safe charset; refuse on* handlers —
		// their values execute as JS after HTML entity decoding, so escaping
		// cannot protect user data in them. Bind handlers via onclick instead.
		if (!/^[a-zA-Z][\w.:-]*$/.test(key) || /^on/i.test(key)) {
			console.warn(`frappe.ui.button: refusing unsafe attribute "${key}"`);
			continue;
		}
		attrs.push(value === true ? key : `${key}="${escape(value)}"`);
	}

	if (icon_only && !opts.title && !(opts.attrs || {})["aria-label"]) {
		console.warn(
			`frappe.ui.button: icon-only button ("${opts.icon}") needs a title for accessibility`
		);
	}

	const classes = escape(["es-button", opts.css_class].filter(Boolean).join(" "));
	// .es-button > svg in button.css sizes the icon to the button;
	// currentColor keeps the stroke in sync with the button's text color
	const icon = opts.icon ? frappe.utils.icon(opts.icon, "sm", "", "", "", true) : "";
	const label = opts.label ? `<span class="es-button__label">${escape(opts.label)}</span>` : "";
	const loading_label_text =
		"loading_label" in opts ? opts.loading_label : default_loading_label(opts.label);
	// aria-live: best-effort announcement of the busy text when it appears;
	// screen readers do not reliably announce a focused button's name change
	const loading_label = loading_label_text
		? `<span class="es-button__loading-label" aria-live="polite">${escape(
				loading_label_text
		  )}</span>`
		: "";

	return `<button class="${classes}" ${attrs.join(" ")}>
		<span class="es-spinner" aria-hidden="true"></span>${loading_label}${icon}${label}
	</button>`;
}

/**
 * Espresso button (`.es-button`) as a wired jQuery element.
 * If `onclick` returns a promise, the button is busy (aria-busy, spinner,
 * clicks blocked) until it settles. Use `frappe.ui.button.html(opts)` for
 * the markup-string form.
 * @param {ButtonOpts} [opts]
 * @returns {JQuery} button element, with `opts.onclick` bound
 * @example frappe.ui.button({ label: __("Save"), variant: "solid", onclick: () => frm.save() });
 */
frappe.ui.button = function (opts = {}) {
	const $btn = $(button_html(opts));
	if (opts.onclick) {
		$btn.on("click", function (e) {
			// pointer-events:none only blocks the mouse — keyboard activation
			// (Enter/Space) still fires, so guard re-entry while busy
			if ($btn.attr("aria-busy") === "true") return;
			const result = opts.onclick.call(this, e);
			if (result && typeof result.then === "function") {
				$btn.attr("aria-busy", "true");
				result.then(
					() => $btn.removeAttr("aria-busy"),
					(err) => {
						$btn.removeAttr("aria-busy");
						// observing the promise marks its rejection as handled, which
						// would hide handler bugs. Re-report in developer mode only:
						// in production, API-level failures already surface through
						// frappe.call's own error dialogs.
						if (frappe.boot?.developer_mode) {
							console.error("frappe.ui.button: onclick rejected", err);
						}
					}
				);
			}
		});
	}
	return $btn;
};

frappe.ui.button.html = button_html;

export default frappe.ui.button;
