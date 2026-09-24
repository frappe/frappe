frappe.provide("frappe.ui");

/* A horizontal labeled bar chart: one row per item (label · proportional bar ·
 * end value) over a shared value axis with gridlines and ticks. Fills the gap
 * left by frappe-charts, which has no horizontal bar type; the axis is computed
 * from the values.
 *
 *   frappe.ui.bar_list({
 *     items: [{ label, value, formatted? }],
 *     max, format, color, on_click, values_on_hover,
 *   }) -> jQuery
 *
 * format(value) is used for the end labels and the axis ticks. values_on_hover
 * hides each end label until its row is hovered. */
frappe.ui.bar_list = function ({
	items = [],
	max,
	format,
	color,
	on_click,
	values_on_hover,
} = {}) {
	format = format || ((v) => String(v));
	const values = items.map((it) => flt(it.value));
	const data_max = max != null ? max : Math.max.apply(null, values.concat([0]));
	const { nice_max, ticks } = axis_ticks(data_max, 6);
	const at = (v) => (nice_max ? (flt(v) / nice_max) * 100 : 0) + "%";

	const $root = $('<div class="es-bar-list">').toggleClass(
		"es-bar-list--hover-values",
		!!values_on_hover
	);
	const $plot = $('<div class="es-bar-list__plot">').appendTo($root);

	ticks.forEach((t) => {
		$('<div class="es-bar-list__gridline">').css("left", at(t)).appendTo($plot);
	});

	const $rows = $('<div class="es-bar-list__rows">').appendTo($plot);
	items.forEach((it) => {
		const $row = $('<div class="es-bar-list__row">');
		if (on_click) {
			$row.addClass("es-bar-list__row--clickable")
				.attr({ role: "button", tabindex: 0 })
				.on("click", () => on_click(it))
				.on("keydown", (e) => {
					if (e.key === "Enter" || e.key === " ") {
						e.preventDefault();
						on_click(it);
					}
				});
		}
		$('<div class="es-bar-list__label">')
			.text(it.label)
			.attr("title", it.label)
			.appendTo($row);
		const $bar = $('<div class="es-bar-list__bar">').css("width", at(it.value));
		if (color) $bar.css("background-color", color);
		$bar.appendTo($row);
		$('<div class="es-bar-list__value">')
			.css("left", at(it.value))
			.text(it.formatted != null ? it.formatted : format(it.value))
			.appendTo($row);
		$row.appendTo($rows);
	});

	const $axis = $('<div class="es-bar-list__axis">').appendTo($plot);
	ticks.forEach((t) => {
		$('<div class="es-bar-list__tick">').css("left", at(t)).text(format(t)).appendTo($axis);
	});

	return $root;
};

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
	count = count || 6;
	if (!(max > 0)) return { nice_max: 1, ticks: [0, 1] };
	const step = nice_num(nice_num(max, false) / (count - 1), true);
	const nice_max = Math.ceil(max / step) * step;
	const ticks = [];
	for (let t = 0; t <= nice_max + step / 2; t += step) ticks.push(t);
	return { nice_max, ticks };
}
