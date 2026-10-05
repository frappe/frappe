import { safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} SkeletonOpts
 * @property {string} [width] CSS length, e.g. "120px" or "100%".
 * @property {string} [height] CSS length, e.g. "16px".
 * @property {string} [css_class] Extra CSS classes, e.g. "rounded-full".
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

/**
 * Espresso skeleton (`.es-skeleton`) as a markup string — a pulsing
 * placeholder shown while content loads. Size it with width/height or
 * with classes. The skeleton itself is hidden from screen readers — set
 * aria-busy="true" on the region being loaded so they know to wait.
 * @param {SkeletonOpts} [opts]
 * @returns {string}
 * @example `<div>${frappe.ui.skeleton.html({ width: "120px", height: "16px" })}</div>`
 */
function skeleton_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const attrs = ['aria-hidden="true"'];
	// only accept a plain CSS length — anything else could smuggle extra
	// style declarations into the attribute
	const length = (value, option) => {
		if (value == null) return "";
		if (!/^[\d.]+(px|rem|em|%|vh|vw|ch)?$/.test(value)) {
			console.warn(`frappe.ui.skeleton: ${option} must be a CSS length, got "${value}"`);
			return "";
		}
		return value;
	};
	const width = length(opts.width, "width");
	const height = length(opts.height, "height");
	const style = [width ? `width: ${width}` : "", height ? `height: ${height}` : ""]
		.filter(Boolean)
		.join("; ");
	if (style) attrs.push(`style="${style}"`);
	attrs.push(...safe_attrs(opts.attrs, "skeleton"));

	const classes = escape(["es-skeleton", opts.css_class].filter(Boolean).join(" "));
	return `<div class="${classes}" ${attrs.join(" ")}></div>`;
}

/**
 * Espresso skeleton as a jQuery element.
 * @param {SkeletonOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.skeleton = function (opts = {}) {
	return $(skeleton_html(opts));
};

frappe.ui.skeleton.html = skeleton_html;

export default frappe.ui.skeleton;
