import { CHART_PALETTE } from "./utils.js";

frappe.provide("frappe.ui");

/**
 * @typedef {Object} DonutSegment
 * @property {string} label Legend and tooltip text. Rendered as text.
 * @property {number} value Segment size. Zero and negative segments are dropped.
 * @property {string} [color] Any CSS colour or token, e.g. var(--blue-600). Defaults to the next chart colour.
 */

/**
 * @typedef {Object} DonutOpts
 * @property {DonutSegment[]} segments With none above zero, the chart shows "No data to show" in the ring's place.
 * @property {{value: string, label?: string}} [center] Text in the hole when nothing is hovered.
 * @property {function} [format] (value) -> string, for the hovered centre and the tooltip.
 * @property {number} [size=240] Chart width and height, in px.
 * @property {string} [css_class] Extra classes on the root.
 */

/**
 * A donut chart (frappe-ui's look): gently rounded, gapped segments, a value
 * in the hole and a legend below. Hovering a segment pops it out, fades the
 * rest, swaps the centre to it and shows a tooltip; hovering a legend row does
 * the same without the tooltip. The caller passes computed segments, so it
 * needs no chart doc or charting library.
 * @example
 * frappe.ui.donut({
 *   segments: [{ label: __("Paid"), value: 70 }, { label: __("Unpaid"), value: 30 }],
 *   center: { value: "70%", label: __("paid") },
 * });
 */
frappe.ui.Donut = class Donut {
	/** @param {DonutOpts} opts */
	constructor({ segments = [], center, format, size = 240, css_class } = {}) {
		this.center = center || {};
		this.format = format || ((v) => String(v));
		this.size = size;
		const ro = size * 0.46;
		const ri = ro * 0.7;
		this.geometry = { c: size / 2, ro, ri, lift: size * 0.02, corner: (ro - ri) * 0.15 };
		this.segments = this.prepare(segments);
		this.active = -1;

		this.$el = $('<div class="es-donut">').addClass(css_class || "");
		this.$chart = $('<div class="es-donut__chart">')
			.css({ width: size, height: size })
			.appendTo(this.$el);
		if (!this.segments.length) {
			this.$el.attr("data-state", "empty");
			$('<div class="es-donut__empty">').text(__("No data to show")).appendTo(this.$chart);
			return;
		}
		this.render_ring();
		this.render_center();
		this.$tip = $('<div class="es-donut__tip">').appendTo(this.$chart);
		this.render_legend();

		this.$chart.on("mouseleave", () => this.clear());
		this.$legend.on("mouseleave", () => this.clear());
	}

	prepare(segments) {
		const kept = segments.filter((s) => flt(s.value) > 0);
		const total = kept.reduce((sum, s) => sum + flt(s.value), 0);
		const pcts = whole_percentages(kept.map((s) => flt(s.value) / total));
		const gap = kept.length > 1 ? 0.03 : 0;
		let angle = -Math.PI / 2;
		return kept.map((s, i) => {
			const sweep = (flt(s.value) / total) * 2 * Math.PI;
			const g = Math.min(gap, sweep / 2);
			const seg = {
				label: s.label,
				value: flt(s.value),
				color: s.color || CHART_PALETTE[i % CHART_PALETTE.length],
				pct: pcts[i],
				a0: angle + g / 2,
				a1: angle + sweep - g / 2,
			};
			angle += sweep;
			return seg;
		});
	}

	path(seg, outer) {
		const { c, ri, corner } = this.geometry;
		if (this.segments.length === 1) return ring_path(c, ri, outer);
		return sector_path(c, ri, outer, seg.a0, seg.a1, corner);
	}

	render_ring() {
		const { ro } = this.geometry;
		const svg = svg_el("svg", {
			viewBox: `0 0 ${this.size} ${this.size}`,
			class: "es-donut__svg",
			role: "img",
			"aria-label": this.segments
				.map((s) => `${s.label}: ${this.format(s.value)} (${s.pct}%)`)
				.join(", "),
		});
		this.shapes = this.segments.map((seg, i) => {
			const shape = svg_el("path", { class: "es-donut__seg", d: this.path(seg, ro) });
			shape.style.fill = seg.color;
			$(shape)
				.on("mouseenter", (e) => {
					this.highlight(i);
					this.$tip.addClass("is-visible");
					this.place_tip(e);
				})
				.on("mousemove", (e) => this.place_tip(e));
			svg.appendChild(shape);
			return shape;
		});
		this.$chart.append(svg);
	}

	render_center() {
		const { c, ri } = this.geometry;
		const inset = c - ri * 0.85;
		const $center = $('<div class="es-donut__center">')
			.css({ paddingLeft: inset, paddingRight: inset })
			.appendTo(this.$chart);
		this.$value = $('<div class="es-donut__value">').appendTo($center);
		this.$label = $('<div class="es-donut__label">').appendTo($center);
		this.set_center(this.center.value, this.center.label);
	}

	render_legend() {
		this.$legend = $('<div class="es-donut__legend">').appendTo(this.$el);
		this.segments.forEach((seg, i) => {
			$('<div class="es-donut__legend-row" tabindex="0">')
				.append(dot(seg.color))
				.append($('<span class="es-donut__legend-label">').text(seg.label))
				.append(
					$('<span class="es-donut__legend-pct">').text(
						`${this.format(seg.value)} · ${seg.pct}%`
					)
				)
				.on("mouseenter focus", () => {
					this.highlight(i);
					this.$tip.removeClass("is-visible");
				})
				.on("blur", () => this.clear())
				.appendTo(this.$legend);
		});
	}

	set_center(value, label) {
		this.$value.text(value == null ? "" : value);
		this.$label.text(label == null ? "" : label);
	}

	highlight(i) {
		if (this.active === i) return;
		this.active = i;
		const seg = this.segments[i];
		const { ro, lift } = this.geometry;
		this.shapes.forEach((shape, j) => {
			shape.classList.toggle("is-dim", j !== i);
			shape.setAttribute("d", this.path(this.segments[j], j === i ? ro + lift : ro));
		});
		this.$legend.children().removeClass("is-active").eq(i).addClass("is-active");
		this.set_center(this.format(seg.value), `${seg.label} · ${seg.pct}%`);
		this.$tip
			.empty()
			.append(dot(seg.color))
			.append($('<span class="es-donut__tip-label">').text(seg.label))
			.append($("<b>").text(this.format(seg.value)))
			.append($('<span class="es-donut__legend-pct">').text(seg.pct + "%"));
	}

	clear() {
		if (this.active === -1) return;
		this.shapes[this.active].setAttribute(
			"d",
			this.path(this.segments[this.active], this.geometry.ro)
		);
		this.active = -1;
		this.shapes.forEach((shape) => shape.classList.remove("is-dim"));
		this.$legend.children().removeClass("is-active");
		this.set_center(this.center.value, this.center.label);
		this.$tip.removeClass("is-visible");
	}

	/* Beside the cursor, on whichever side keeps it inside the viewport. */
	place_tip(e) {
		const rect = this.$chart[0].getBoundingClientRect();
		const x = e.clientX - rect.left;
		const fits_right =
			e.clientX + 14 + this.$tip.outerWidth() < document.documentElement.clientWidth;
		const right = x >= rect.width / 2 && fits_right;
		this.$tip.css({
			left: right ? x + 14 : x - 14,
			top: e.clientY - rect.top,
			transform: right ? "translateY(-50%)" : "translate(-100%, -50%)",
		});
	}
};

/**
 * Convenience form: build the chart and get the element back, so it chains
 * inside append(...) calls. The instance is on `.data("es-donut")`.
 * @param {DonutOpts} opts
 * @returns {JQuery}
 */
frappe.ui.donut = function (opts = {}) {
	const donut = new frappe.ui.Donut(opts);
	donut.$el.data("es-donut", donut);
	return donut.$el;
};

function dot(color) {
	return $('<span class="es-donut__dot">').css("background", color);
}

function svg_el(tag, attrs) {
	const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
	Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
	return el;
}

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

function polar(c, r, a) {
	return [c + r * Math.cos(a), c + r * Math.sin(a)];
}

/* A ring segment from a0 to a1 with all four corners rounded by ~`cr`, drawn as
 * outer arc → rounded corner → inner arc → rounded corner. Corners use the sharp
 * vertex as a quadratic control point. Each arc gets its own large-arc flag
 * because the corners shorten the outer and inner arcs by different angles. */
function sector_path(c, ri, ro, a0, a1, cr) {
	const span = a1 - a0;
	cr = Math.min(cr, (ro - ri) / 2, (span * ri) / 2.2);
	const dao = cr / ro;
	const dai = cr / ri;
	const large_o = span - 2 * dao > Math.PI ? 1 : 0;
	const large_i = span - 2 * dai > Math.PI ? 1 : 0;
	const p = (r, a) => polar(c, r, a).join(" ");
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

/* A full ring, as two half-circle arcs per edge (one arc can't close a circle). */
function ring_path(c, ri, ro) {
	const arc = (r, sweep, x) => `A ${r} ${r} 0 1 ${sweep} ${x} ${c}`;
	return [
		`M ${c + ro} ${c}`,
		arc(ro, 1, c - ro),
		arc(ro, 1, c + ro),
		`M ${c + ri} ${c}`,
		arc(ri, 0, c - ri),
		arc(ri, 0, c + ri),
		"Z",
	].join(" ");
}

export default frappe.ui.donut;
