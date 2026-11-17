import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} AvatarGroupOpts
 * @property {Object[]} [avatars] People to show, each taking frappe.ui.avatar options (label, image, theme, title, indicator). The group's size and shape apply to all of them.
 * @property {number} [max=3] Avatars shown before the +N circle. One hidden person is shown instead of a "+1".
 * @property {"xs"|"sm"|"md"|"lg"|"xl"|"2xl"|"3xl"} [size="md"]
 * @property {"circle"|"square"} [shape="circle"]
 * @property {string} [theme="auto"] Fallback color for every avatar (a frappe.ui.avatar theme); "auto" gives each name its own. An avatar's own theme wins.
 * @property {function} [onclick] Makes each avatar a button; called with the clicked avatar's options and the event (element form only). The +N list then opens on click and its rows call it too; without it the list is read-only and shows on hover.
 * @property {function} [hover_card] Called with an avatar's options and the HoverCard (to close it from inside); returns the content of a hover card shown in place of the name tooltip (element form only). Touch can't open a hover card, so keep anything essential reachable another way too.
 * @property {Object} [add] Shows an add button after the avatars: { title, icon = "plus", onclick }.
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const SIZES = ["xs", "sm", "md", "lg", "xl", "2xl", "3xl"];
const SHAPES = ["circle", "square"];

// an avatar's own tooltip and label: its title when given ("Sam is viewing")
const avatar_name = (item) => item.title || item.label || "";
// a person in a list of names (+N): the name itself
const person_name = (item) => item.label || item.title || "";

function resolve(opts) {
	const avatars = opts.avatars || [];
	const max_opt = parseInt(opts.max, 10);
	const max = Math.max(1, Number.isNaN(max_opt) ? 3 : max_opt);
	// a "+1" circle takes the same room as the person it hides
	const split = avatars.length <= max + 1 ? avatars.length : max;
	return {
		size: validated(opts.size, SIZES, "size", "avatar_group") || "md",
		shape: validated(opts.shape, SHAPES, "shape", "avatar_group") || "circle",
		theme: opts.theme || "auto",
		shown: avatars.slice(0, split),
		hidden: avatars.slice(split),
	};
}

// `clickable` wraps the avatars in buttons; only the element form can wire them
function group_html(opts, { size, shape, theme, shown, hidden }, clickable) {
	const escape = frappe.utils.escape_html;

	const avatar = (item) => {
		const html = frappe.ui.avatar.html({ ...item, size, shape, theme: item.theme || theme });
		if (!clickable) return html;
		const name = avatar_name(item);
		const label = name ? ` aria-label="${escape(name)}"` : "";
		return `<button type="button" class="es-avatar-group__item"${label}>${html}</button>`;
	};
	let stack = shown.map(avatar).join("");
	if (hidden.length) {
		// avatar markup by hand: frappe.ui.avatar would show only the "+"
		const names = hidden.map(person_name).join(", ");
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

// rows of the +N popover: the hidden people, as buttons when they're clickable
function hidden_list(hidden, { shape, theme }, onclick) {
	const $list = $('<div class="es-avatar-group__list"></div>');
	for (const item of hidden) {
		const $row = onclick
			? $('<button type="button" class="es-avatar-group__list-item"></button>')
			: $('<div class="es-avatar-group__list-item"></div>');
		const $avatar = frappe.ui
			.avatar({ ...item, size: "sm", shape, theme: item.theme || theme })
			.removeAttr("title");
		const $name = $('<span class="es-avatar-group__name"></span>').text(person_name(item));
		$row.append($avatar, $name);
		if (onclick) $row.on("click", (e) => onclick(item, e));
		$list.append($row);
	}
	return $list;
}

/**
 * Espresso avatar group as a jQuery element: espresso tooltips instead of
 * native titles, the +N list in a popover, and the click handlers bound.
 * @param {AvatarGroupOpts} [opts]
 * @returns {JQuery}
 * @example frappe.ui.avatar_group({ avatars, size: "sm", add: { title: __("Assign"), onclick: assign } });
 */
frappe.ui.avatar_group = function (opts = {}) {
	const resolved = resolve(opts);
	const { shown, hidden } = resolved;
	const $group = $(group_html(opts, resolved, Boolean(opts.onclick)));

	// shown avatars, in order; the tooltip, hover card and click go on the
	// button when there is one, so keyboard focus gets them too
	$group.find(".es-avatar:not(.es-avatar-group__more)").each((i, el) => {
		const $avatar = $(el).removeAttr("title");
		const $button = $avatar.parent(".es-avatar-group__item");
		const $trigger = $button.length ? $button : $avatar;
		const name = avatar_name(shown[i]);
		// the button carries the name; a bare avatar needs it once the title is gone
		if (!$button.length && name) $avatar.attr({ role: "img", "aria-label": name });
		if (opts.hover_card) {
			const hover_card = new frappe.ui.HoverCard($trigger, {
				content: () => opts.hover_card(shown[i], hover_card),
				align: "start",
				css_class: "es-avatar-group__hover-card",
			});
		} else if (name) {
			frappe.ui.tooltip($trigger, { text: name });
		}
		if (opts.onclick) $button.on("click", (e) => opts.onclick(shown[i], e));
	});
	if (hidden.length && opts.onclick) {
		// the rows are actions, so the list opens on click and stays open (touch too)
		const $trigger = $group
			.find(".es-avatar-group__more")
			.removeAttr("title")
			.wrap('<button type="button" class="es-avatar-group__item"></button>')
			.parent()
			.attr("aria-label", __("{0} more", [hidden.length]));
		const popover = new frappe.ui.Popover({
			trigger: $trigger,
			css_class: "es-avatar-group__popover",
			content: () =>
				hidden_list(hidden, resolved, (item, e) => {
					popover.close("owner");
					opts.onclick(item, e);
				}),
		});
	} else if (hidden.length) {
		// a read-only list shows on hover and closes when the pointer leaves;
		// screen readers get the names from the label, as they can't reach the card
		const names = hidden.map(person_name).join(", ");
		const $more = $group
			.find(".es-avatar-group__more")
			.removeAttr("title")
			.attr({
				tabindex: 0,
				role: "img",
				"aria-label": __("{0} more: {1}", [hidden.length, names]),
			});
		new frappe.ui.HoverCard($more, {
			content: () => hidden_list(hidden, resolved),
			align: "start",
			css_class: "es-avatar-group__popover",
		});
	}

	if (opts.add) {
		const $add = $group.find(".es-avatar-group__add").removeAttr("title");
		frappe.ui.tooltip($add, { text: opts.add.title || __("Add") });
		if (opts.add.onclick) $add.on("click", opts.add.onclick);
	}
	return $group;
};

/**
 * Espresso avatar group (`.es-avatar-group`) as a markup string, with native
 * title tooltips and no handlers.
 * @param {AvatarGroupOpts} [opts]
 * @returns {string}
 * @example `${frappe.ui.avatar_group.html({ avatars: users, max: 3, size: "sm" })}`
 */
frappe.ui.avatar_group.html = (opts = {}) => group_html(opts, resolve(opts), false);

export default frappe.ui.avatar_group;
