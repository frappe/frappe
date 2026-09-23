import { validated, safe_href } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} EmptyStateAction
 * @property {string} label Button/link text. Rendered as text, never HTML.
 * @property {"solid"|"subtle"|"outline"|"ghost"} [variant] Button look (defaults: subtle for buttons, ghost for links).
 * @property {"gray"|"red"} [theme]
 * @property {string} [icon] Leading lucide icon.
 * @property {function} [onclick] Renders the action as a button (element form only).
 * @property {string} [href] Renders the action as a link (opens in a new tab). Code-running schemes are refused.
 * @property {string} [css_class] Extra classes on this action (e.g. a hook a caller wires clicks to).
 */

/**
 * @typedef {Object} EmptyStateOpts
 * @property {string} [icon] Lucide icon shown in a round grey well above the title.
 * @property {string} title The headline. Rendered as text, never HTML.
 * @property {string} [description] Smaller supporting line under the title.
 * @property {EmptyStateAction[]} [actions] One or more actions — e.g. a "New …" button plus a docs link. Rendered in a row.
 * @property {string} [css_class] Extra classes on the root (e.g. a min-height so it fills its container).
 */

const VARIANTS = ["solid", "subtle", "outline", "ghost"];

// EmptyState has no state and no data-attribute contract, so it carries NO
// component stylesheet — it's composed entirely from the shared utility
// classes (utilities.scss + typography.css) right in the markup. The styling
// mirrors frappe-ui (AccountingDesktop.vue): a round grey icon well, a
// medium title, a small muted description, then the actions.

/** One action → a button (onclick) or a link (href), styled as an es-button. */
function build_action(action) {
	if (!action || !action.label) return null;

	if (action.href) {
		// a real <a> so the docs link behaves like a link (new tab, etc.);
		// reuses the es-button look via the class (button.css is element-neutral)
		const href = safe_href(action.href, "empty_state");
		const variant =
			validated(action.variant, VARIANTS, "action variant", "empty_state") || "ghost";
		const a = document.createElement("a");
		a.className = ["es-button", action.css_class].filter(Boolean).join(" ");
		if (variant !== "subtle") a.setAttribute("data-variant", variant);
		if (action.theme === "red") a.setAttribute("data-theme", "red");
		if (href) {
			a.href = href;
			a.target = "_blank";
			a.rel = "noreferrer noopener";
		}
		if (action.icon) {
			a.insertAdjacentHTML(
				"beforeend",
				frappe.utils.icon(action.icon, "sm", "", "", "", true)
			);
		}
		const label = document.createElement("span");
		label.className = "es-button__label";
		label.textContent = action.label;
		a.appendChild(label);
		return a;
	}

	// onclick (or nothing) → a normal button
	return frappe.ui.button({
		label: action.label,
		variant: action.variant,
		theme: action.theme,
		icon: action.icon,
		size: action.size,
		css_class: action.css_class,
		onclick: action.onclick,
	})[0];
}

/**
 * A "nothing here yet" block for empty lists, reports, tables and pages:
 * an icon, a title, an optional description, and any number of actions
 * (a create button, a docs link, both). Styled purely with utility classes
 * — there is no empty-state stylesheet.
 * @param {EmptyStateOpts} [opts]
 * @returns {JQuery} the root element
 * @example
 * list_area.append(frappe.ui.empty_state({
 *     icon: "inbox",
 *     title: __("No invoices yet"),
 *     description: __("Create your first invoice to get started."),
 *     actions: [
 *         { label: __("New Invoice"), variant: "solid", icon: "plus", onclick: () => this.new_doc() },
 *         { label: __("Learn more"), href: "https://docs.erpnext.com/invoicing", icon: "external-link" },
 *     ],
 * }));
 */
frappe.ui.empty_state = function (opts = {}) {
	const wrap = document.createElement("div");
	// Default breathing room: the content centres in a min-height box so it
	// isn't jammed against the edges. Pass a bigger min-h-* in css_class to
	// override — utilities are ordered ascending, so a larger step wins.
	wrap.className = [
		"flex flex-col items-center justify-center text-center gap-3 min-h-48",
		opts.css_class,
	]
		.filter(Boolean)
		.join(" ");

	if (opts.icon) {
		const well = document.createElement("div");
		well.className =
			"flex size-11 items-center justify-center rounded-full bg-surface-gray-2 text-ink-gray-5";
		// icon inherits the well's ink colour via stroke="currentColor"
		well.insertAdjacentHTML("beforeend", frappe.utils.icon(opts.icon, "md", "", "", "", true));
		wrap.appendChild(well);
	}

	// title + description sit close together (their own tight gap)
	const text = document.createElement("div");
	text.className = "flex flex-col items-center gap-1";
	const title = document.createElement("div");
	title.className = "text-base-medium text-ink-gray-8";
	title.textContent = opts.title || "";
	text.appendChild(title);
	if (opts.description) {
		const desc = document.createElement("div");
		desc.className = "text-p-sm text-ink-gray-5 max-w-xs";
		desc.textContent = opts.description;
		text.appendChild(desc);
	}
	wrap.appendChild(text);

	const actions = (opts.actions || []).map(build_action).filter(Boolean);
	if (actions.length) {
		const row = document.createElement("div");
		row.className = "flex flex-wrap items-center justify-center gap-2";
		actions.forEach((node) => row.appendChild(node));
		wrap.appendChild(row);
	}

	return $(wrap);
};

/**
 * Markup-string form for templates. Static — button `onclick`s can't survive
 * a string, so use `href` actions (or the element form) when you need clicks.
 * @param {EmptyStateOpts} [opts]
 * @returns {string}
 */
frappe.ui.empty_state.html = function (opts = {}) {
	return frappe.ui.empty_state(opts)[0].outerHTML;
};

export default frappe.ui.empty_state;
