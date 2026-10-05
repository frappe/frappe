import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} AvatarGroupOpts
 * @property {Object[]} [avatars] People to show, each taking frappe.ui.avatar options (label, image, theme, title, indicator). The group's size and shape apply to all of them.
 * @property {number} [max=3] Avatars shown before the +N circle. One hidden person is shown instead of a "+1".
 * @property {"xs"|"sm"|"md"|"lg"|"xl"|"2xl"|"3xl"} [size="md"]
 * @property {"circle"|"square"} [shape="circle"]
 * @property {Object} [add] Shows an add button after the avatars: { title, icon = "plus" }.
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const SIZES = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl"];
const SHAPES = ["circle", "square"];

function split_avatars(avatars, max) {
	// a "+1" circle takes the same room as the person it hides
	if (avatars.length <= max + 1) return { shown: avatars, hidden: [] };
	return { shown: avatars.slice(0, max), hidden: avatars.slice(max) };
}

/**
 * Espresso avatar group (`.es-avatar-group`) as a markup string.
 * @param {AvatarGroupOpts} [opts]
 * @returns {string}
 * @example `${frappe.ui.avatar_group.html({ avatars: users, max: 3, size: "sm" })}`
 */
function avatar_group_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const size = validated(opts.size, SIZES, "size", "avatar_group") || "md";
	const shape = validated(opts.shape, SHAPES, "shape", "avatar_group") || "circle";
	const max = Math.max(1, parseInt(opts.max, 10) || 3);
	const { shown, hidden } = split_avatars(opts.avatars || [], max);

	const avatar = (item) => frappe.ui.avatar.html({ ...item, size, shape });
	let stack = shown.map(avatar).join("");
	if (hidden.length) {
		// avatar markup by hand: frappe.ui.avatar would show only the "+"
		const names = hidden.map((item) => item.title || item.label).join(", ");
		const shape_attr = shape !== "circle" ? ` data-shape="${shape}"` : "";
		stack += `<span class="es-avatar es-avatar-group__more" data-size="${size}"${shape_attr} title="${escape(
			names
		)}"><span class="es-avatar__fallback"><bdi>+${hidden.length}</bdi></span></span>`;
	}

	const add = opts.add
		? frappe.ui.button.html({
				icon: opts.add.icon || "plus",
				title: opts.add.title || __("Add"),
				css_class: "es-avatar-group__add",
		  })
		: "";

	const attrs = [`data-size="${size}"`];
	if (shape !== "circle") attrs.push(`data-shape="${shape}"`);
	attrs.push(...safe_attrs(opts.attrs, "avatar_group"));
	const classes = escape(["es-avatar-group", opts.css_class].filter(Boolean).join(" "));
	const stack_html = stack ? `<span class="es-avatar-group__stack">${stack}</span>` : "";
	return `<div class="${classes}" ${attrs.join(" ")}>${stack_html}${add}</div>`;
}

/**
 * Espresso avatar group as a jQuery element.
 * @param {AvatarGroupOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.avatar_group = function (opts = {}) {
	return $(avatar_group_html(opts));
};

frappe.ui.avatar_group.html = avatar_group_html;

export default frappe.ui.avatar_group;
