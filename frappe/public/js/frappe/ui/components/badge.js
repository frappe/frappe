import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} BadgeOpts
 * @property {string} [label] Badge text (pre-translated). HTML-escaped.
 * @property {"gray"|"blue"|"green"|"amber"|"red"|"violet"|"orange"} [theme="gray"] "orange" means amber (same as frappe-ui). Old indicator colors (yellow, cyan, purple, pink, grey, darkgrey, light-blue) still work through badge-legacy-colors.css.
 * @property {string} [icon] Lucide icon name, shown before the label.
 * @property {string} [icon_left] Same as `icon`.
 * @property {string} [icon_right] Lucide icon name, shown after the label inside an `.es-badge__affix` wrapper (the frappe-ui suffix-slot markup). Unlike direct icons, the affix accepts pointer events — bind to `.es-badge__affix` for a clickable suffix (dismissible tags).
 * @property {string} [title] Tooltip; doubles as aria-label when the badge has no visible label.
 * @property {"sm"|"md"|"lg"} [size="md"]
 * @property {"solid"|"subtle"|"outline"|"ghost"} [variant="subtle"]
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes, e.g. { "data-testid": "status" }.
 */

const THEMES = ["gray", "blue", "green", "amber", "red", "violet"];
// old indicator colors that badge-legacy-colors.css still renders — accepted
// without a warning so existing data keeps working.
// TODO: remove when badge-legacy-colors.css is retired.
const LEGACY_THEMES = ["grey", "darkgrey", "yellow", "cyan", "purple", "pink", "light-blue"];
const SIZES = ["sm", "md", "lg"];
const VARIANTS = ["solid", "subtle", "outline", "ghost"];

/**
 * Espresso badge (`.es-badge`) as a markup string, for template literals.
 * @param {BadgeOpts} [opts]
 * @returns {string}
 * @example `<td>${frappe.ui.badge.html({ label: __("Open"), theme: "blue" })}</td>`
 */
function badge_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	// orange and amber are the same thing; frappe-ui accepts both too
	const theme_name = opts.theme === "orange" ? "amber" : opts.theme;
	const theme = LEGACY_THEMES.includes(theme_name)
		? theme_name
		: validated(theme_name, THEMES, "theme", "badge");
	const size = validated(opts.size, SIZES, "size", "badge");
	const variant = validated(opts.variant, VARIANTS, "variant", "badge");

	const icon_name = opts.icon_left || opts.icon;
	const icon_right_name = opts.icon_right;

	const attrs = [];
	// leave out attributes that match the CSS defaults (gray / md / subtle)
	if (theme && theme !== "gray") attrs.push(`data-theme="${theme}"`);
	if (size && size !== "md") attrs.push(`data-size="${size}"`);
	if (variant && variant !== "subtle") attrs.push(`data-variant="${variant}"`);
	if (opts.title) {
		attrs.push(`title="${escape(opts.title)}"`);
		// an icon-only badge has no text for screen readers — reuse the title
		if ((icon_name || icon_right_name) && !opts.label) {
			attrs.push(`aria-label="${escape(opts.title)}"`);
		}
	}
	attrs.push(...safe_attrs(opts.attrs, "badge"));

	const classes = escape(["es-badge", opts.css_class].filter(Boolean).join(" "));
	const attr_str = attrs.length ? " " + attrs.join(" ") : "";
	const icon = icon_name ? frappe.utils.icon(icon_name, "sm", "", "", "", true) : "";
	// suffix rides in the affix wrapper: direct svg children are
	// pointer-events:none, the affix is the interactive-suffix channel
	const icon_right = icon_right_name
		? `<span class="es-badge__affix">${frappe.utils.icon(
				icon_right_name,
				"sm",
				"",
				"",
				"",
				true
		  )}</span>`
		: "";
	return `<span class="${classes}"${attr_str}>${icon}${escape(
		opts.label || ""
	)}${icon_right}</span>`;
}

/**
 * Espresso badge (`.es-badge`) as a jQuery element.
 * Use `frappe.ui.badge.html(opts)` for the markup-string form.
 * @param {BadgeOpts} [opts]
 * @returns {JQuery} badge element
 * @example frappe.ui.badge({ label: __("Draft"), theme: "red" }).appendTo($row);
 */
frappe.ui.badge = function (opts = {}) {
	return $(badge_html(opts));
};

frappe.ui.badge.html = badge_html;

export default frappe.ui.badge;
