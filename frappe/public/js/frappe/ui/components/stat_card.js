frappe.provide("frappe.ui");

/* A lightweight KPI/number card: label, big value, and an optional trend delta
 * or caption. Not backed by a Number Card doc — the caller passes computed values,
 * so any form/page/dashboard can use it. Wrap a row in .es-stat-card-grid.
 *
 *   frappe.ui.stat_card({
 *     label, value,
 *     delta: { value, positive_is_good, negative, suffix },  // shown instead of caption
 *     caption, dot, icon, onclick,
 *   }) -> jQuery
 *
 * value and caption accept a string or a DOM/jQuery node.
 * Use frappe.ui.stat_cards({ items, layout }) to build a whole group from a list. */
frappe.ui.stat_card = function ({ label, value, delta, caption, dot, icon, onclick } = {}) {
	const $card = $('<div class="es-stat-card">');

	const $head = $('<div class="es-stat-card__head">').appendTo($card);
	if (dot) $('<span class="es-stat-card__dot">').css("background", dot).appendTo($head);
	else if (icon) $head.append(frappe.utils.icon(icon, "sm"));
	$('<span class="es-stat-card__label">').text(label || "").appendTo($head);

	const $value = $('<div class="es-stat-card__value">').appendTo($card);
	set_content($value, value);

	if (delta) {
		$card.append(build_delta(delta));
	} else if (caption != null) {
		set_content($('<div class="es-stat-card__caption">').appendTo($card), caption);
	}

	if (onclick) {
		$card.addClass("es-stat-card--clickable")
			.attr({ role: "button", tabindex: 0 })
			.on("click", onclick)
			.on("keydown", (e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					onclick(e);
				}
			});
	}

	return $card;
};

/* Build a group of cards from a list in one call. Each item is stat_card opts.
 *   frappe.ui.stat_cards({ items: [{ label, value, ... }], layout }) -> jQuery
 * layout: "grid" (default, equal-height wrapping columns) or "stack" (one column). */
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

function build_delta({ value, positive_is_good = true, negative, suffix } = {}) {
	const $delta = $('<div class="es-stat-card__caption es-stat-card__delta">');
	if (!value) {
		$delta.attr("data-tone", "neutral").append(document.createTextNode("0%"));
	} else {
		const up = value > 0;
		const good = negative ? false : up === positive_is_good;
		$delta
			.attr("data-tone", good ? "positive" : "negative")
			.append(frappe.utils.icon(up ? "arrow-up-right" : "arrow-down-right", "sm"))
			.append(document.createTextNode(" " + Math.abs(value) + "%"));
	}
	if (suffix) $('<span class="es-stat-card__delta-suffix">').text(" " + suffix).appendTo($delta);
	return $delta;
}
