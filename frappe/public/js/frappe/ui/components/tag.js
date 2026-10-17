import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} TagOpts
 * @property {string} label Tag text (pre-translated). HTML-escaped.
 * @property {"gray"|"blue"|"green"|"amber"|"red"|"violet"} [theme="gray"]
 * @property {"sm"|"md"|"lg"} [size="md"]
 * @property {boolean} [removable=false] Adds a ✕ button after the label. Bind to `.es-tag__remove`.
 * @property {string} [title] Tooltip.
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const THEMES = ["gray", "blue", "green", "amber", "red", "violet"];
const SIZES = ["sm", "md", "lg"];

/**
 * Espresso tag (`.es-tag`) as a markup string: a label someone put on a record,
 * optionally with a ✕ to take it off. Unlike a badge (a status the system shows)
 * it is square-cornered and gray, and its ✕ is a real button.
 * @param {TagOpts} [opts]
 * @returns {string}
 * @example `${frappe.ui.tag.html({ label: "Respond in 24h", removable: true })}`
 */
function tag_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const theme = validated(opts.theme, THEMES, "theme", "tag");
	const size = validated(opts.size, SIZES, "size", "tag");

	const attrs = [];
	if (theme && theme !== "gray") attrs.push(`data-theme="${theme}"`);
	if (size && size !== "md") attrs.push(`data-size="${size}"`);
	if (opts.title) attrs.push(`title="${escape(opts.title)}"`);
	attrs.push(...safe_attrs(opts.attrs, "tag"));

	const classes = escape(["es-tag", opts.css_class].filter(Boolean).join(" "));
	const attr_str = attrs.length ? " " + attrs.join(" ") : "";
	const label = `<span class="es-tag__label">${escape(opts.label || "")}</span>`;
	const remove = opts.removable
		? `<button type="button" class="es-tag__remove" aria-label="${escape(
				__("Remove {0}", [opts.label || ""])
		  )}">${frappe.utils.icon("x", "sm", "", "", "", true)}</button>`
		: "";
	return `<span class="${classes}"${attr_str}>${label}${remove}</span>`;
}

/**
 * Espresso tag (`.es-tag`) as a jQuery element.
 * Use `frappe.ui.tag.html(opts)` for the markup-string form.
 * @param {TagOpts} [opts]
 * @returns {JQuery}
 * @example frappe.ui.tag({ label: tag, removable: true }).appendTo($list);
 */
frappe.ui.tag = function (opts = {}) {
	return $(tag_html(opts));
};

frappe.ui.tag.html = tag_html;

export default frappe.ui.tag;
