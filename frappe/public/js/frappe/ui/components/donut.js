frappe.provide("frappe.ui");

const DONUT_PALETTE = [
	"#2590d6",
	"#84c5f9",
	"#289e60",
	"#84d4a1",
	"#753cbb",
	"#e5a13a",
	"#e2657a",
];

/* A donut chart: a ring of gently rounded, gapped segments with a value in the
 * middle and a dotted legend below. Hovering a segment pops it out, fades the
 * rest, swaps the centre to it and shows a tooltip; hovering a legend row does
 * the same without the tooltip. Framework neutral — the caller passes computed
 * segments — so any form/page/dashboard can use it in place of a charting library.
 *
 *   frappe.ui.donut({
 *     segments: [{ label, value, color? }],
 *     center: { value, label },   // shown when nothing is hovered
 *     format,                     // (value) -> string, for the hovered centre and tooltip
 *     size,
 *   }) -> jQuery
 *
 * `color` takes any CSS colour, including theme tokens like var(--ink-red-5);
 * segments without one fall back to a categorical palette. */
frappe.ui.donut = function ({ segments = [], center, format, size = 240 } = {}) {
	format = format || ((v) => String(v));
	segments = segments.filter((s) => flt(s.value) > 0);
	const total = segments.reduce((sum, s) => sum + flt(s.value), 0);
	const pcts = whole_percentages(segments.map((s) => flt(s.value) / total));

	const cx = size / 2;
	const cy = size / 2;
	const ro = size * 0.46;
	const ri = ro * 0.7;
	const lift = size * 0.02;
	const corner = (ro - ri) * 0.15;
	const gap = segments.length > 1 ? 0.03 : 0;

	const $root = $('<div class="es-donut">');
	const $chart = $('<div class="es-donut__chart">')
		.css({ width: size, height: size })
		.appendTo($root);
	const svgns = "http://www.w3.org/2000/svg";
	const svg = document.createElementNS(svgns, "svg");
	svg.setAttribute("viewBox", `0 0 ${size} ${size}`);
	svg.setAttribute("class", "es-donut__svg");
	$chart.append(svg);

	let angle = -Math.PI / 2;
	const shapes = segments.map((seg, i) => {
		const sweep = (flt(seg.value) / total) * 2 * Math.PI;
		const g = Math.min(gap, sweep / 2);
		const a0 = angle + g / 2;
		const a1 = angle + sweep - g / 2;
		angle += sweep;
		seg._color = seg.color || DONUT_PALETTE[i % DONUT_PALETTE.length];
		seg._pct = pcts[i];
		seg._d = (outer) =>
			segments.length === 1
				? ring_path(cx, cy, ri, outer)
				: sector_path(cx, cy, ri, outer, a0, a1, corner);

		const shape = document.createElementNS(svgns, "path");
		shape.setAttribute("class", "es-donut__seg");
		shape.setAttribute("fill-rule", "evenodd");
		shape.setAttribute("d", seg._d(ro));
		shape.style.fill = seg._color;
		svg.appendChild(shape);
		return shape;
	});

	const $center = $('<div class="es-donut__center">')
		.css("padding", `0 ${cx - ri * 0.85}px`)
		.appendTo($chart);
	const $cval = $('<div class="es-donut__value">').appendTo($center);
	const $clabel = $('<div class="es-donut__label">').appendTo($center);
	const set_center = (value, label) => {
		$cval.text(value == null ? "" : value);
		$clabel.text(label == null ? "" : label);
	};
	const reset_center = () => set_center(center && center.value, center && center.label);
	reset_center();

	const $tip = $('<div class="es-donut__tip">').appendTo($chart);
	const place_tip = (e) => {
		const rect = $chart[0].getBoundingClientRect();
		const x = e.clientX - rect.left;
		const fits_right =
			e.clientX + 14 + $tip.outerWidth() < document.documentElement.clientWidth;
		const right = x >= rect.width / 2 && fits_right;
		$tip.css({
			left: right ? x + 14 : x - 14,
			top: e.clientY - rect.top,
			transform: right ? "translateY(-50%)" : "translate(-100%, -50%)",
		});
	};

	const $legend = $('<div class="es-donut__legend">').appendTo($root);
	let active = -1;
	const highlight = (i) => {
		if (active === i) return;
		active = i;
		const seg = segments[i];
		shapes.forEach((s, j) => {
			s.classList.toggle("is-dim", j !== i);
			s.setAttribute("d", segments[j]._d(j === i ? ro + lift : ro));
		});
		$legend.children().removeClass("is-active").eq(i).addClass("is-active");
		set_center(format(seg.value), seg.label + " · " + seg._pct + "%");
		$tip.empty()
			.append($('<span class="es-donut__dot">').css("background", seg._color))
			.append($('<span class="es-donut__tip-label">').text(seg.label))
			.append($("<b>").text(format(seg.value)))
			.append($('<span class="es-donut__legend-pct">').text(seg._pct + "%"));
	};
	const clear = () => {
		if (active === -1) return;
		shapes[active].setAttribute("d", segments[active]._d(ro));
		active = -1;
		shapes.forEach((s) => s.classList.remove("is-dim"));
		$legend.children().removeClass("is-active");
		reset_center();
		$tip.removeClass("is-visible");
	};

	segments.forEach((seg, i) => {
		$('<div class="es-donut__legend-row">')
			.append($('<span class="es-donut__dot">').css("background", seg._color))
			.append($('<span class="es-donut__legend-label">').text(seg.label))
			.append($('<span class="es-donut__legend-pct">').text(seg._pct + "%"))
			.on("mouseenter", () => {
				highlight(i);
				$tip.removeClass("is-visible");
			})
			.appendTo($legend);

		$(shapes[i])
			.on("mouseenter", (e) => {
				highlight(i);
				$tip.addClass("is-visible");
				place_tip(e);
			})
			.on("mousemove", place_tip);
	});
	$chart.on("mouseleave", clear);
	$legend.on("mouseleave", clear);

	return $root;
};

/* Largest-remainder rounding, so the legend adds up to exactly 100%. */
function whole_percentages(fracs) {
	const raw = fracs.map((f) => f * 100);
	const out = raw.map(Math.floor);
	let short = 100 - out.reduce((a, b) => a + b, 0);
	raw.map((r, i) => [r - out[i], i])
		.sort((a, b) => b[0] - a[0])
		.forEach(([, i]) => {
			if (short-- > 0) out[i] += 1;
		});
	return out;
}

function polar(cx, cy, r, a) {
	return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
}

/* A ring segment from a0 to a1 with all four corners rounded by ~`cr`, drawn as
 * outer arc → rounded corner → inner arc → rounded corner. Corners use the sharp
 * vertex as a quadratic control point. Each arc gets its own large-arc flag
 * because the corners shorten the outer and inner arcs by different angles. */
function sector_path(cx, cy, ri, ro, a0, a1, cr) {
	const span = a1 - a0;
	cr = Math.min(cr, (ro - ri) / 2, (span * ri) / 2.2);
	const dao = cr / ro;
	const dai = cr / ri;
	const large_o = span - 2 * dao > Math.PI ? 1 : 0;
	const large_i = span - 2 * dai > Math.PI ? 1 : 0;
	const p = (r, a) => polar(cx, cy, r, a).join(" ");
	return [
		"M " + p(ro, a0 + dao),
		"A " + ro + " " + ro + " 0 " + large_o + " 1 " + p(ro, a1 - dao),
		"Q " + p(ro, a1) + " " + p(ro - cr, a1),
		"L " + p(ri + cr, a1),
		"Q " + p(ri, a1) + " " + p(ri, a1 - dai),
		"A " + ri + " " + ri + " 0 " + large_i + " 0 " + p(ri, a0 + dai),
		"Q " + p(ri, a0) + " " + p(ri + cr, a0),
		"L " + p(ro - cr, a0),
		"Q " + p(ro, a0) + " " + p(ro, a0 + dao),
		"Z",
	].join(" ");
}

function ring_path(cx, cy, ri, ro) {
	const o = (r) => r + " " + r + " 0 1 1 ";
	const inner = (r) => r + " " + r + " 0 1 0 ";
	return [
		"M " + (cx + ro) + " " + cy,
		"A " + o(ro) + (cx - ro) + " " + cy,
		"A " + o(ro) + (cx + ro) + " " + cy,
		"M " + (cx + ri) + " " + cy,
		"A " + inner(ri) + (cx - ri) + " " + cy,
		"A " + inner(ri) + (cx + ri) + " " + cy,
		"Z",
	].join(" ");
}
