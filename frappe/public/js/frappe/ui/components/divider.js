import { validated, safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} DividerOpts
 * @property {"horizontal"|"vertical"} [orientation="horizontal"]
 * @property {boolean} [flex_item] For a vertical divider in a flex row: stretch to the row's height.
 * @property {Object} [action] A small button sitting on the line (horizontal only): { label, onclick, loading }.
 * @property {"start"|"center"|"end"} [position="center"] Where the action button sits on the line.
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

const ORIENTATIONS = ["horizontal", "vertical"];
const POSITIONS = ["start", "center", "end"];

/**
 * Espresso divider (`.es-divider`) as a markup string. With `action`, a
 * button renders on the line (use the element form to get its click handler).
 * @param {DividerOpts} [opts]
 * @returns {string}
 * @example `${frappe.ui.divider.html()}`
 */
function divider_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const orientation = validated(opts.orientation, ORIENTATIONS, "orientation", "divider");
	const position = validated(opts.position, POSITIONS, "position", "divider");

	if (opts.action) {
		if (orientation === "vertical") {
			console.warn("frappe.ui.divider: the vertical action form isn't supported yet");
		}
		const attrs = [];
		if (position && position !== "center") attrs.push(`data-position="${position}"`);
		attrs.push(...safe_attrs(opts.attrs, "divider"));
		const classes = escape(["es-divider-action", opts.css_class].filter(Boolean).join(" "));
		const button = frappe.ui.button.html({
			label: opts.action.label,
			size: "sm",
			variant: "outline",
			loading: opts.action.loading,
		});
		const attr_str = attrs.length ? " " + attrs.join(" ") : "";
		// the line keeps its separator meaning for screen readers (same as
		// frappe-ui); a plain <hr> gets that role automatically
		return `<div class="${classes}"${attr_str}>
			<div class="es-divider-line" role="separator" aria-orientation="horizontal"></div>${button}
		</div>`;
	}

	const attrs = [];
	if (orientation && orientation !== "horizontal") {
		attrs.push(`data-orientation="${orientation}"`);
		attrs.push('aria-orientation="vertical"');
	}
	if (opts.flex_item) attrs.push("data-flex-item");
	attrs.push(...safe_attrs(opts.attrs, "divider"));

	const classes = escape(["es-divider", opts.css_class].filter(Boolean).join(" "));
	const attr_str = attrs.length ? " " + attrs.join(" ") : "";
	return `<hr class="${classes}"${attr_str}>`;
}

/**
 * Espresso divider as a jQuery element. When `action.onclick` is set, the
 * button is created through frappe.ui.button, so returning a promise from
 * the handler shows the busy state automatically.
 * @param {DividerOpts} [opts]
 * @returns {JQuery}
 * @example frappe.ui.divider({ action: { label: __("Load More"), onclick: () => load() } });
 */
frappe.ui.divider = function (opts = {}) {
	if (opts.action && opts.action.onclick) {
		const $el = $(divider_html({ ...opts, action: { ...opts.action } }));
		// swap the static button for a wired one so onclick (and the busy
		// state, when it returns a promise) work like any frappe.ui.button
		$el.find(".es-button").replaceWith(
			frappe.ui.button({
				label: opts.action.label,
				size: "sm",
				variant: "outline",
				loading: opts.action.loading,
				onclick: opts.action.onclick,
			})
		);
		return $el;
	}
	return $(divider_html(opts));
};

frappe.ui.divider.html = divider_html;

export default frappe.ui.divider;
