import { make_activatable } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} StatCardDelta
 * @property {number} value Signed percentage change, e.g. 12.5 or -4.
 * @property {boolean} [positive_is_good=true] Set false for metrics where a rise is bad (overdue, churn), so an increase reads red.
 * @property {string} [suffix] Muted text after the number, e.g. "since last year".
 */

/**
 * @typedef {Object} StatCardOpts
 * @property {string} label Small heading above the value. Rendered as text.
 * @property {string|number|Element|JQuery} value The headline number, already formatted.
 * @property {StatCardDelta} [delta] Trend line under the value. Takes the place of `caption`.
 * @property {string|Element|JQuery} [caption] Muted line under the value.
 * @property {string} [dot] CSS colour for a dot before the label — ties the card to a chart series.
 * @property {string} [icon] Lucide icon before the label (ignored when `dot` is set).
 * @property {function} [onclick] Makes the whole card a button (click, Enter, Space).
 * @property {string} [css_class] Extra classes on the root.
 */

/**
 * A lightweight KPI card: label, big value, and a trend delta or caption.
 * Unlike Number Card widgets it is not backed by a doc — the caller passes
 * computed values, so any form, page or dashboard can use it.
 * @param {StatCardOpts} opts
 * @returns {JQuery}
 * @example
 * frappe.ui.stat_card({
 *   label: __("Net Sales"),
 *   value: format_currency(120000),
 *   delta: { value: 12, suffix: __("since last year") },
 * });
 */
frappe.ui.stat_card = function ({
	label,
	value,
	delta,
	caption,
	dot,
	icon,
	onclick,
	css_class,
} = {}) {
	const $card = $('<div class="es-stat-card">').addClass(css_class || "");

	const $head = $('<div class="es-stat-card__head">').appendTo($card);
	if (dot) $('<span class="es-stat-card__dot">').css("background", dot).appendTo($head);
	else if (icon) $head.append(frappe.utils.icon(icon, "sm"));
	$('<span class="es-stat-card__label">')
		.text(label || "")
		.appendTo($head);

	set_content($('<div class="es-stat-card__value">').appendTo($card), value);

	if (delta) {
		$card.append(build_delta(delta));
	} else if (caption != null) {
		set_content($('<div class="es-stat-card__caption">').appendTo($card), caption);
	}

	if (onclick) make_activatable($card.addClass("es-stat-card--clickable"), onclick);

	return $card;
};

/**
 * A group of cards from a list of StatCardOpts.
 * @param {{items: StatCardOpts[], layout?: "grid"|"stack"}} opts `grid` (default) is an equal-height wrapping grid; `stack` is one column.
 * @returns {JQuery}
 */
frappe.ui.stat_cards = function ({ items = [], layout = "grid" } = {}) {
	const cls = layout === "stack" ? "es-stat-card-stack" : "es-stat-card-grid";
	const $wrap = $(`<div class="${cls}">`);
	items.forEach((opts) => $wrap.append(frappe.ui.stat_card(opts)));
	return $wrap;
};

function set_content($el, content) {
	if (content == null) return;
	if (content instanceof jQuery || content instanceof Element) {
		$el.append(content);
	} else {
		$el.text(content);
	}
}

function build_delta({ value, positive_is_good = true, suffix } = {}) {
	const $delta = $('<div class="es-stat-card__caption es-stat-card__delta">');
	const change = flt(value, 1);
	if (!change) {
		$delta.attr("data-tone", "neutral").append(document.createTextNode("0%"));
	} else {
		const up = change > 0;
		$delta
			.attr("data-tone", up === positive_is_good ? "positive" : "negative")
			.append(frappe.utils.icon(up ? "arrow-up-right" : "arrow-down-right", "sm"))
			.append(document.createTextNode(" " + Math.abs(change) + "%"));
	}
	if (suffix)
		$('<span class="es-stat-card__delta-suffix">')
			.text(" " + suffix)
			.appendTo($delta);
	return $delta;
}

export default frappe.ui.stat_card;
