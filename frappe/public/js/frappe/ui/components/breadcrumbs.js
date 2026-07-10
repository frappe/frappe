import { safe_attrs } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} BreadcrumbItem
 * @property {string} [label] Text of the crumb. HTML-escaped.
 * @property {string} [href] Renders the crumb as a link.
 * @property {function} [onclick] Click handler (element form only).
 * @property {string} [prefix] Lucide icon name shown before the label.
 * @property {string} [suffix] Lucide icon name shown after the label.
 * @property {string} [title] Tooltip; becomes the aria-label when the crumb has no label (icon-only).
 */

/**
 * @typedef {Object} BreadcrumbsOpts
 * @property {BreadcrumbItem[]} items Ordered crumbs; the last one is the current page.
 * @property {string} [css_class] Extra CSS classes.
 * @property {Object<string, string|true>} [attrs] Extra attributes.
 */

// javascript:/data: links run code — escaping can't help, so refuse them
function safe_href(href) {
	if (!href) return null;
	if (/^\s*(javascript|data|vbscript):/i.test(href)) {
		console.warn(`frappe.ui.breadcrumbs: refusing unsafe href "${href}"`);
		return null;
	}
	return href;
}

/**
 * Espresso breadcrumbs (`.es-breadcrumbs`) as a markup string.
 * @param {BreadcrumbsOpts} [opts]
 * @returns {string}
 * @example `${frappe.ui.breadcrumbs.html({ items: [{ label: "Home", href: "/app" }, { label: doc.name }] })}`
 */
function breadcrumbs_html(opts = {}) {
	const escape = frappe.utils.escape_html;
	const items = opts.items || [];

	if (!opts._element_form && items.some((item) => item.onclick)) {
		console.warn(
			"frappe.ui.breadcrumbs: onclick needs the element form — frappe.ui.breadcrumbs(opts)"
		);
	}

	// prefix/suffix are lucide icon names
	const affix = (value) => {
		if (!value) return "";
		if (typeof value !== "string") {
			console.warn("frappe.ui.breadcrumbs: prefix/suffix take a lucide icon name");
			return "";
		}
		return frappe.utils.icon(value, "sm", "", "", "", true);
	};

	const crumbs = items
		.map((item, i) => {
			const last = i === items.length - 1;
			const href = safe_href(item.href);
			// no label span when there is no label — an empty span is still a
			// flex item and would get its own share of the gap
			const label = item.label
				? `<span class="es-breadcrumbs__label">${escape(item.label)}</span>`
				: "";
			const content = affix(item.prefix) + label + affix(item.suffix);

			let extra = "";
			const title = item.title || (last ? item.label : "");
			if (title) extra += ` title="${escape(title)}"`;
			if (last) extra += ' aria-current="page"';
			// an icon-only crumb has no text for screen readers — reuse the title
			if (!item.label && (item.prefix || item.suffix)) {
				if (item.title) {
					extra += ` aria-label="${escape(item.title)}"`;
				} else {
					console.warn(
						"frappe.ui.breadcrumbs: an icon-only crumb needs a title for accessibility"
					);
				}
			}

			const inner = href
				? `<a class="es-breadcrumbs__item" href="${escape(href)}"${extra}>${content}</a>`
				: `<button class="es-breadcrumbs__item" type="button"${extra}>${content}</button>`;
			return `<li>${inner}</li>`;
		})
		.join("");

	const attrs = [`aria-label="${escape(__("Breadcrumb"))}"`];
	attrs.push(...safe_attrs(opts.attrs, "breadcrumbs"));
	const classes = escape(["es-breadcrumbs", opts.css_class].filter(Boolean).join(" "));
	return `<nav class="${classes}" ${attrs.join(" ")}><ol>${crumbs}</ol></nav>`;
}

/**
 * Espresso breadcrumbs as a jQuery element, with each item's `onclick` wired.
 * @param {BreadcrumbsOpts} [opts]
 * @returns {JQuery}
 */
frappe.ui.breadcrumbs = function (opts = {}) {
	const $el = $(breadcrumbs_html({ ...opts, _element_form: true }));
	(opts.items || []).forEach((item, i) => {
		if (item.onclick) {
			$el.find(".es-breadcrumbs__item").eq(i).on("click", item.onclick);
		}
	});
	return $el;
};

frappe.ui.breadcrumbs.html = breadcrumbs_html;

export default frappe.ui.breadcrumbs;
