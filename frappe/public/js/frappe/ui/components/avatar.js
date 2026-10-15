import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} AvatarOpts
 * @property {string} [image] Image URL. Falls back to the label's first letter if missing or if it fails to load.
 * @property {string} [label] Name used for the fallback letter and the image alt text.
 * @property {"xs"|"sm"|"md"|"lg"|"xl"|"2xl"|"3xl"} [size="md"]
 * @property {"circle"|"square"} [shape="circle"]
 * @property {"gray"|"blue"|"green"|"amber"|"red"|"violet"|"orange"|"pink"|"yellow"|"teal"|"cyan"|"purple"|"auto"} [theme="gray"] Colors the fallback letter. "auto" picks a color from the label, so a name always gets the same one.
 * @property {"gray"|"blue"|"green"|"amber"|"red"|"violet"} [indicator] Shows a status dot at the bottom-right in this color.
 * @property {string} [title] Tooltip. Defaults to the label.
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const SIZES = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl"];
const SHAPES = ["circle", "square"];
// "auto" picks from the hues that stay distinct side by side (yellow, cyan and
// purple are too close to amber, blue and violet to tell apart in a stack)
const AUTO_THEMES = ["blue", "green", "amber", "red", "violet", "orange", "pink", "teal"];
const THEMES = ["gray", ...AUTO_THEMES, "yellow", "cyan", "purple", "auto"];
const INDICATOR_COLORS = ["gray", "blue", "green", "amber", "red", "violet"];

function auto_theme(label) {
	const text = (label || "").trim();
	if (!text) return "gray";
	// FNV-1a: mixes every bit, so similar names still land on different colors
	let hash = 0x811c9dc5;
	for (const char of text) {
		hash ^= char.codePointAt(0);
		hash = Math.imul(hash, 0x01000193) >>> 0;
	}
	return AUTO_THEMES[hash % AUTO_THEMES.length];
}

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
	let theme = validated(opts.theme, THEMES, "theme", "avatar");
	if (theme === "auto") theme = auto_theme(opts.label);

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

	const indicator_color = validated(opts.indicator, INDICATOR_COLORS, "indicator", "avatar");
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
		// the image starts loading before the element is in the page, where the listener below can't see it
		$el.find("img").on("error", function () {
			$(this).replaceWith(fallback_html(opts.label));
		});
	}
	return $el;
};

// The markup form can't carry a listener, so broken avatar images in the page are caught here.
// Load errors don't bubble, hence the capture phase; the alt text is the label.
document.addEventListener(
	"error",
	(e) => {
		const img = e.target;
		if (img.tagName === "IMG" && img.parentElement?.classList.contains("es-avatar")) {
			img.outerHTML = fallback_html(img.alt);
		}
	},
	true
);

frappe.ui.avatar.html = avatar_html;

export default frappe.ui.avatar;
