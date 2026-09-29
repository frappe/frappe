import { make_activatable } from "./utils.js";

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
 * @property {number} [max] Axis maximum; defaults to the largest value.
 * @property {function} [format] (value) -> string, for the end labels and axis ticks.
 * @property {string} [color] Bar colour (any CSS colour or token); defaults to a dark grey.
 * @property {number} [label_width=96] Width of the label gutter, in px.
 * @property {boolean} [values_on_hover=false] Hide each end label until its row is hovered or focused.
 * @property {function} [on_click] (item) -> void. Makes each row a button.
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
	label_width,
	values_on_hover,
	on_click,
	css_class,
} = {}) {
	const $root = $('<div class="es-bar-list">').addClass(css_class || "");
	if (!items.length) {
		return $root
			.attr("data-state", "empty")
			.append($('<div class="es-bar-list__empty">').text(__("No data to show")));
	}

	format = format || ((v) => String(v));
	const values = items.map((it) => Math.max(flt(it.value), 0));
	const data_max = max != null ? max : Math.max(0, ...values);
	const { nice_max, ticks } = axis_ticks(data_max, 6);
	const at = (v) => (nice_max ? (Math.max(flt(v), 0) / nice_max) * 100 : 0) + "%";

	$root.toggleClass("es-bar-list--hover-values", !!values_on_hover);
	if (label_width) $root.css("--es-bl-label-w", label_width + "px");
	const $plot = $('<div class="es-bar-list__plot">').appendTo($root);

	ticks.forEach((t) => {
		$('<div class="es-bar-list__gridline">').css("left", at(t)).appendTo($plot);
	});

	const $rows = $('<div class="es-bar-list__rows">').appendTo($plot);
	items.forEach((it) => $rows.append(build_row(it, { at, format, color, on_click })));

	const $axis = $('<div class="es-bar-list__axis">').appendTo($plot);
	ticks.forEach((t) => {
		$('<div class="es-bar-list__tick">').css("left", at(t)).text(format(t)).appendTo($axis);
	});

	return $root;
};

function build_row(item, { at, format, color, on_click }) {
	const $row = $('<div class="es-bar-list__row">');
	if (on_click) {
		make_activatable($row.addClass("es-bar-list__row--clickable"), () => on_click(item));
	}
	$('<div class="es-bar-list__label">')
		.text(item.label)
		.attr("title", item.label)
		.appendTo($row);
	const $bar = $('<div class="es-bar-list__bar">').css("width", at(item.value)).appendTo($row);
	if (color) $bar.css("background-color", color);
	$('<div class="es-bar-list__value">')
		.css("left", at(item.value))
		.text(item.formatted != null ? item.formatted : format(item.value))
		.appendTo($row);
	return $row;
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
