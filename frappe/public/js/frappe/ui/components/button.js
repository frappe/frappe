import { validated, safe_attrs, safe_href } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} ButtonOpts
 * @property {string} [label] Button text (pre-translated). HTML-escaped.
 * @property {string} [loading_label] Text shown while busy. Defaults for common labels (Save → Saving..., Delete → Deleting..., Submit → Submitting...); pass "" to opt out.
 * @property {"solid"|"subtle"|"outline"|"ghost"} [variant="subtle"]
 * @property {"xs"|"sm"|"md"|"lg"} [size="sm"]
 * @property {"gray"|"red"} [theme="gray"]
 * @property {string} [icon] Lucide icon name, shown before the label. An icon without a label renders a square icon-button — pass `title`.
 * @property {string} [icon_left] Same as `icon`.
 * @property {string} [icon_right] Lucide icon name, shown after the label.
 * @property {string} [title] Native browser tooltip; doubles as aria-label on icon-only buttons. Prefer `tooltip`.
 * @property {string} [href] Render as a link (`<a>`) with this href instead of a `<button>` — middle-click / ctrl-click open a tab. Code-running schemes are refused.
 * @property {string|Object} [tooltip] Espresso tooltip text (or full TooltipOpts) shown on hover/focus (element form only, like onclick). Doubles as aria-label on icon-only buttons.
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

/**
 * Espresso button (`.es-button`) as a markup string, for template literals.
 * @param {ButtonOpts} [opts]
 * @returns {string}
 * @example `<div>${frappe.ui.button.html({ label: __("Load More") })}</div>`
 */
function button_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const variant = validated(opts.variant, VARIANTS, "variant", "button");
	const size = validated(opts.size, SIZES, "size", "button");
	const theme = validated(opts.theme, THEMES, "theme", "button");
	const icon_left_name = opts.icon_left || opts.icon;
	const icon_only = Boolean((icon_left_name || opts.icon_right) && !opts.label);

	const href = safe_href(opts.href, "button");
	// a link keeps the button's look but none of a button's attributes
	const attrs = href ? [`href="${escape(href)}"`] : [`type="${escape(opts.type || "button")}"`];
	// omit attributes that equal the CSS defaults (subtle / sm / gray)
	if (variant && variant !== "subtle") attrs.push(`data-variant="${variant}"`);
	if (size && size !== "sm") attrs.push(`data-size="${size}"`);
	if (theme && theme !== "gray") attrs.push(`data-theme="${theme}"`);
	if (icon_only) attrs.push('data-icon-button="true"');
	if (opts.loading) attrs.push('aria-busy="true"');
	if (opts.disabled) attrs.push("disabled");
	const tooltip_text =
		typeof opts.tooltip === "string" ? opts.tooltip : opts.tooltip && opts.tooltip.text;
	// native title only when there's no espresso tooltip — both at once
	// would show two bubbles for the same button
	if (opts.title && !tooltip_text) attrs.push(`title="${escape(opts.title)}"`);
	// the name should match what the user can actually see, and the visible
	// one is the espresso tooltip when both are given
	const accessible_name = tooltip_text || opts.title;
	if (icon_only && accessible_name) attrs.push(`aria-label="${escape(accessible_name)}"`);
	attrs.push(...safe_attrs(opts.attrs, "button"));

	if (icon_only && !accessible_name && !(opts.attrs || {})["aria-label"]) {
		console.warn(
			`frappe.ui.button: icon-only button ("${
				icon_left_name || opts.icon_right
			}") needs a tooltip or title for accessibility`
		);
	}

	const classes = escape(["es-button", opts.css_class].filter(Boolean).join(" "));

	// no whitespace around the content: legacy callers read labels back with
	// $(btn).text(), which includes every text node inside the button
	const tag = href ? "a" : "button";
	return `<${tag} class="${classes}" ${attrs.join(" ")}>${content_html(opts)}</${tag}>`;
}

// The button's children: spinner + loading label + icons + label. Shared by
// the markup form above and by dress() below so the two can't drift.
function content_html(opts) {
	const escape = frappe.utils.escape_html;
	// .es-button > svg in button.css sizes the icons to the button;
	// currentColor keeps the stroke in sync with the button's text color
	const render_icon = (name) => (name ? frappe.utils.icon(name, "sm", "", "", "", true) : "");
	const icon_left = render_icon(opts.icon_left || opts.icon);
	const icon_right = render_icon(opts.icon_right);
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
	return `<span class="es-spinner" aria-hidden="true"></span>${loading_label}${icon_left}${label}${icon_right}`;
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
	// runtime lookup, not an import: both live in the same bundles, and a
	// bundle without the tooltip component should still get working buttons
	if (opts.tooltip && frappe.ui.tooltip) {
		frappe.ui.tooltip(
			$btn,
			typeof opts.tooltip === "string" ? { text: opts.tooltip } : opts.tooltip
		);
	}
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

/**
 * Apply the es-button contract to an EXISTING <button> element — the
 * migration channel for legacy surfaces (like the page header) where external
 * code holds a reference to the element, so it must be mutated in place, never
 * replaced.
 *
 * Sets the `es-button` class and the data-variant/size/theme attributes
 * (removing them when the value is the CSS default, so markup stays lean).
 * When `label` or an icon is passed, the button's children are rebuilt to the
 * es structure (spinner + loading label + icons + label span); otherwise the
 * existing content is left untouched, so a trigger with bespoke children can
 * be dressed for looks alone.
 *
 * Deliberately does NOT touch click handlers, disabled, aria-busy, or
 * visibility — those stay the caller's domain. Can be re-applied to the same
 * element (idempotent per option).
 *
 * @param {HTMLElement|JQuery} el The button to dress.
 * @param {ButtonOpts} [opts] label / loading_label / icon / icon_left / icon_right / variant / size / theme.
 * @returns {JQuery} the same element, dressed
 * @example frappe.ui.button.dress(this.btn_primary, { label: __("Save"), variant: "solid" });
 */
frappe.ui.button.dress = function (el, opts = {}) {
	const $el = $(el);
	$el.addClass("es-button");
	if (!$el.attr("type")) $el.attr("type", "button");

	// undefined = leave the existing attribute alone; a value = set it,
	// unless it's the CSS default, which is expressed by NO attribute
	const set_data = (name, value, default_value) => {
		if (value === undefined) return;
		if (value === default_value) {
			$el.removeAttr(`data-${name}`);
		} else {
			$el.attr(`data-${name}`, value);
		}
	};
	set_data("variant", validated(opts.variant, VARIANTS, "variant", "button"), "subtle");
	set_data("size", validated(opts.size, SIZES, "size", "button"), "sm");
	set_data("theme", validated(opts.theme, THEMES, "theme", "button"), "gray");

	const has_icon = Boolean(opts.icon || opts.icon_left || opts.icon_right);
	if ("label" in opts || has_icon) {
		$el.html(content_html(opts));
		if (has_icon && !opts.label) {
			$el.attr("data-icon-button", "true");
		} else {
			$el.removeAttr("data-icon-button");
		}
	}
	return $el;
};

export default frappe.ui.button;
