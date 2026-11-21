import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} RatingOpts
 * @property {number} [value=0] Stars filled, 0 to max. Rounded to the nearest step, like frappe-ui's Rating.
 * @property {number} [max=5] Number of stars.
 * @property {"xs"|"sm"|"md"|"lg"} [size="sm"] Star size (14/16/20/24px).
 * @property {1|0.5} [step=1] 1 fills whole stars; 0.5 also fills half stars.
 * @property {string} [label] Accessible name. Defaults to "{value} out of {max}".
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const SIZES = ["xs", "sm", "md", "lg"];
const STEPS = [1, 0.5];
const STAR_PATH =
	"M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z";
const STAR_SVG = `<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${STAR_PATH}"/></svg>`;

/**
 * Espresso rating (`.es-rating`) as a markup string: a read-only row of
 * stars, matching frappe-ui's Rating. Display only, with no hover or click.
 * @param {RatingOpts} [opts]
 * @returns {string}
 * @example `<div>${frappe.ui.rating.html({ value: 4, size: "md" })}</div>`
 */
function rating_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const size = validated(opts.size, SIZES, "size", "rating");
	const step = Number(validated(opts.step, STEPS, "step", "rating")) || 1;
	const max = opts.max || 5;
	const clamped = Math.max(0, Math.min(max, Number(opts.value) || 0));
	const value = Math.round(clamped / step) * step;

	const attrs = ['role="img"'];
	const label = opts.label || __("{0} out of {1}", [value, max]);
	attrs.push(`aria-label="${escape(label)}"`);
	if (size && size !== "sm") attrs.push(`data-size="${size}"`);
	attrs.push(...safe_attrs(opts.attrs, "rating"));

	let stars = "";
	for (let index = 1; index <= max; index++) {
		const left = index - 0.5 <= value ? "filled" : "empty";
		const right = index <= value ? "filled" : "empty";
		stars +=
			`<span class="es-rating__star">` +
			`<span class="es-rating__half" data-half="left" data-state="${left}">${STAR_SVG}</span>` +
			`<span class="es-rating__half" data-half="right" data-state="${right}">${STAR_SVG}</span>` +
			`</span>`;
	}
	const classes = escape(["es-rating", opts.css_class].filter(Boolean).join(" "));
	return `<span class="${classes}" ${attrs.join(" ")}>${stars}</span>`;
}

/**
 * Espresso rating as a jQuery element.
 * @param {RatingOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.rating = function (opts = {}) {
	return $(rating_html(opts));
};

frappe.ui.rating.html = rating_html;

export default frappe.ui.rating;
