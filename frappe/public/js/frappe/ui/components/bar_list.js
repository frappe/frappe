import { place } from "./position.js";
import { CHART_PALETTE, make_activatable } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} BarListItem
 * @property {string} label Row label on the left. Rendered as text; long labels ellipsize with a title tooltip.
 * @property {number} value Bar length. Negative values draw as an empty bar.
 * @property {string} [formatted] End label text; defaults to `format(value)`.
 */

/**
 * @typedef {Object} BarListOpts
 * @property {BarListItem[]} items One row per item, drawn in the given order. With none, the chart shows "No data to show" (zero values still draw).
 * @property {number} [max] Minimum axis maximum; expands to fit the largest value.
 * @property {function} [format] (value) -> string, for the end labels and axis ticks.
 * @property {string} [color] Bar colour: any CSS colour or token, e.g. var(--green-600). Defaults to the first chart colour.
 * @property {string} [name] Series name shown in the hover tooltip, e.g. "Outstanding".
 * @property {function} [tooltip_format] (value) -> string, for the hover tooltip; defaults to the item's `formatted`, then `format`.
 * @property {number} [label_width=96] Width of the label gutter, in px.
 * @property {boolean} [values_on_hover=false] Hide clickable row values until hovered or focused; static rows keep values visible.
 * @property {function} [onclick] (item) -> void. Makes each row a button.
 * @property {string} [css_class] Extra classes on the root.
 */

/**
 * A horizontal bar chart: one row per item (label · proportional bar · end
 * value) over a shared axis with gridlines and ticks. frappe-charts has no
 * horizontal bar type; this covers ranked lists like ageing buckets or top
 * customers. The axis is computed from the values.
 * @param {BarListOpts} opts
 * @returns {JQuery}
 * @example
 * frappe.ui.bar_list({
 *   items: [{ label: "0–30 days", value: 42000 }, { label: "31–60 days", value: 18000 }],
 *   format: (v) => format_currency(v),
 * });
 */
frappe.ui.bar_list = function ({
	items = [],
	max,
	format,
	color,
	name,
	tooltip_format,
	label_width,
	values_on_hover,
	onclick,
	css_class,
} = {}) {
	const $root = $('<div class="es-bar-list">').addClass(css_class || "");
	if (!items.length) {
		return $root
			.attr("data-state", "empty")
			.append($('<div class="es-bar-list__empty">').text(__("No data to show")));
	}

	format = format || ((v) => String(v));
	color = color || CHART_PALETTE[0];
	const values = items.map((it) => Math.max(flt(it.value), 0));
	const data_max = Math.max(flt(max), 0, ...values);
	const { nice_max, ticks } = axis_ticks(data_max, 6);
	const at = (v) => (nice_max ? (Math.max(flt(v), 0) / nice_max) * 100 : 0) + "%";

	$root.toggleClass("es-bar-list--hover-values", !!values_on_hover && !!onclick);
	if (label_width) $root.css("--es-bl-label-w", label_width + "px");
	const $plot = $('<div class="es-bar-list__plot">').appendTo($root);

	ticks.forEach((t) => {
		$('<div class="es-bar-list__gridline">').css("inset-inline-start", at(t)).appendTo($plot);
	});

	const $rows = $('<div class="es-bar-list__rows">').appendTo($plot);
	items.forEach((it) => $rows.append(build_row(it, { at, format, color, onclick })));
	bind_tooltip($rows, { color, name, format, tooltip_format });

	const $axis = $('<div class="es-bar-list__axis">').appendTo($plot);
	ticks.forEach((t) => {
		$('<div class="es-bar-list__tick">')
			.css("inset-inline-start", at(t))
			.text(format(t))
			.appendTo($axis);
	});

	return $root;
};

function build_row(item, { at, format, color, onclick }) {
	const $row = $('<div class="es-bar-list__row">').data("item", item);
	if (onclick) {
		make_activatable($row.addClass("es-bar-list__row--clickable"), () => onclick(item));
	}
	$('<div class="es-bar-list__label">')
		.text(item.label)
		.attr("title", item.label)
		.appendTo($row);
	$('<div class="es-bar-list__bar">')
		.css({ width: at(item.value), "background-color": color })
		.appendTo($row);
	$('<div class="es-bar-list__value">')
		.css("inset-inline-start", at(item.value))
		.text(item.formatted != null ? item.formatted : format(item.value))
		.appendTo($row);
	return $row;
}

function bind_tooltip($rows, opts) {
	let open = null;
	const hide = () => {
		if (!open) return;
		open.observer.disconnect();
		window.removeEventListener("resize", hide);
		document.removeEventListener("scroll", hide, { capture: true });
		open.$tip.remove();
		open = null;
	};
	const show = (row) => {
		hide();
		const $tip = build_tip($(row).data("item"), opts).appendTo(document.body);
		place_tip($tip[0], row);
		const observer = new MutationObserver(() => row.isConnected || hide());
		observer.observe(document.body, { childList: true, subtree: true });
		window.addEventListener("resize", hide);
		document.addEventListener("scroll", hide, { capture: true, passive: true });
		open = { row, $tip, observer };
	};
	$rows
		.on("mouseenter", ".es-bar-list__row", function () {
			if (open?.row !== this) show(this);
		})
		.on("focusin", ".es-bar-list__row", function () {
			if (open?.row !== this && this.matches(":focus-visible")) show(this);
		})
		.on("pointerdown", ".es-bar-list__row", hide)
		.on("mouseleave", ".es-bar-list__row", function () {
			if (!this.contains(document.activeElement)) hide();
		})
		.on("focusout", ".es-bar-list__row", function () {
			if (!this.matches(":hover")) hide();
		});
}

function build_tip(item, { color, name, format, tooltip_format }) {
	const value = tooltip_format
		? tooltip_format(item.value)
		: item.formatted ?? format(item.value);
	return $('<div class="es-bar-list__tip es-chart-tip" role="tooltip">')
		.append($('<div class="es-bar-list__tip-title">').text(item.label))
		.append(
			$('<div class="es-bar-list__tip-row">')
				.append($('<span class="es-bar-list__tip-dot">').css("background-color", color))
				.append(name ? $('<span class="es-bar-list__tip-name">').text(name) : null)
				.append($("<b>").text(value))
		);
}

function place_tip(tip, row) {
	const rtl = frappe.utils.is_rtl();
	const row_rect = row.getBoundingClientRect();
	const bar = row.querySelector(".es-bar-list__bar").getBoundingClientRect();
	const end = rtl ? bar.left : bar.right;
	const anchor = new DOMRect(end, row_rect.top, 0, row_rect.height);
	place(tip, anchor, rtl ? "left" : "right", "center", 12);
}

/* A "nice" number near `range` (1, 2 or 5 × 10^n) so ticks land on round values. */
function nice_num(range, round) {
	const exp = Math.floor(Math.log10(range || 1));
	const base = Math.pow(10, exp);
	const f = range / base;
	let nf;
	if (round) nf = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
	else nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
	return nf * base;
}

function axis_ticks(max, count) {
	if (!(max > 0)) return { nice_max: 1, ticks: [0, 1] };
	const step = nice_num(nice_num(max, false) / (count - 1), true);
	const nice_max = Math.ceil(max / step) * step;
	const ticks = [];
	for (let t = 0; t <= nice_max + step / 2; t += step) ticks.push(t);
	return { nice_max, ticks };
}

export default frappe.ui.bar_list;
