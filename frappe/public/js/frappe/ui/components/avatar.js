import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} AvatarOpts
 * @property {string} [image] Image URL. Falls back to the label's first letter if missing (element form also falls back when the image fails to load).
 * @property {string} [label] Name used for the fallback letter and the image alt text.
 * @property {"xs"|"sm"|"md"|"lg"|"xl"|"2xl"|"3xl"} [size="md"]
 * @property {"circle"|"square"} [shape="circle"]
 * @property {"gray"|"blue"|"green"|"amber"|"red"|"violet"} [theme="gray"] Colors the fallback letter.
 * @property {"gray"|"blue"|"green"|"amber"|"red"|"violet"} [indicator] Shows a status dot at the bottom-right in this color.
 * @property {string} [title] Tooltip. Defaults to the label.
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const SIZES = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl"];
const SHAPES = ["circle", "square"];
const THEMES = ["gray", "blue", "green", "amber", "red", "violet"];

function fallback_html(label) {
	const escape = frappe.utils.escape_html;
	const letter = (label || "").trim().charAt(0);
	return `<span class="es-avatar__fallback">${escape(letter)}</span>`;
}

/**
 * Espresso avatar (`.es-avatar`) as a markup string.
 * @param {AvatarOpts} [opts]
 * @returns {string}
 * @example `${frappe.ui.avatar.html({ label: user.fullname, image: user.image, size: "sm" })}`
 */
function avatar_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const size = validated(opts.size, SIZES, "size", "avatar");
	const shape = validated(opts.shape, SHAPES, "shape", "avatar");
	const theme = validated(opts.theme, THEMES, "theme", "avatar");

	const attrs = [];
	// leave out attributes that match the CSS defaults (md / circle / gray)
	if (size && size !== "md") attrs.push(`data-size="${size}"`);
	if (shape && shape !== "circle") attrs.push(`data-shape="${shape}"`);
	if (theme && theme !== "gray") attrs.push(`data-theme="${theme}"`);
	const title = opts.title || opts.label;
	if (title) attrs.push(`title="${escape(title)}"`);
	attrs.push(...safe_attrs(opts.attrs, "avatar"));

	const inner = opts.image
		? `<img src="${escape(opts.image)}" alt="${escape(opts.label || "")}">`
		: fallback_html(opts.label);

	const indicator_color = validated(opts.indicator, THEMES, "indicator", "avatar");
	const indicator = indicator_color
		? `<span class="es-avatar__indicator" aria-hidden="true"><span class="es-avatar__indicator-dot"${
				indicator_color !== "gray" ? ` data-color="${indicator_color}"` : ""
		  }></span></span>`
		: "";

	const classes = escape(["es-avatar", opts.css_class].filter(Boolean).join(" "));
	const attr_str = attrs.length ? " " + attrs.join(" ") : "";
	return `<span class="${classes}"${attr_str}>${inner}${indicator}</span>`;
}

/**
 * Espresso avatar as a jQuery element. If the image fails to load, it is
 * swapped for the initials fallback (same behavior as frappe-ui's Avatar).
 * @param {AvatarOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.avatar = function (opts = {}) {
	const $el = $(avatar_html(opts));
	if (opts.image) {
		$el.find("img").on("error", function () {
			$(this).replaceWith(fallback_html(opts.label));
		});
	}
	return $el;
};

frappe.ui.avatar.html = avatar_html;

export default frappe.ui.avatar;
