const BOUNDARY_PADDING = 5;
const OPPOSITE = { left: "right", right: "left", top: "bottom", bottom: "top" };

const style_of = (element) => (element.nodeType === 1 ? getComputedStyle(element) : {});
const base_side = (placement) => placement.split("-")[0];
const variation_of = (placement) => placement.split("-")[1] || "";
const is_horizontal = (side) => side === "left" || side === "right";
const opposite_of = (placement) => placement.replace(/left|right|bottom|top/g, (m) => OPPOSITE[m]);
const with_edges = (rect) => ({
	...rect,
	right: rect.left + rect.width,
	bottom: rect.top + rect.height,
});

function parent_node(element) {
	return element.nodeName === "HTML" ? element : element.parentNode || element.host;
}

function scroll_parent(element) {
	if (!element) return document.body;
	if (element.nodeName === "HTML" || element.nodeName === "BODY") {
		return element.ownerDocument.body;
	}
	if (element.nodeName === "#document") return element.body;

	const { overflow, overflowX, overflowY } = style_of(element);
	if (/(auto|scroll|overlay)/.test(overflow + overflowY + overflowX)) return element;
	return scroll_parent(parent_node(element));
}

function offset_parent(element) {
	if (!element) return document.documentElement;

	let parent = element.offsetParent || null;
	while (parent === null && element.nextElementSibling) {
		element = element.nextElementSibling;
		parent = element.offsetParent;
	}

	const name = parent && parent.nodeName;
	if (!name || name === "BODY" || name === "HTML") {
		return element ? element.ownerDocument.documentElement : document.documentElement;
	}
	if (["TH", "TD", "TABLE"].includes(name) && style_of(parent).position === "static") {
		return offset_parent(parent);
	}
	return parent;
}

function is_offset_container(element) {
	if (element.nodeName === "BODY") return false;
	return element.nodeName === "HTML" || offset_parent(element.firstElementChild) === element;
}

function root_of(node) {
	return node.parentNode !== null ? root_of(node.parentNode) : node;
}

function common_offset_parent(a, b) {
	if (!a?.nodeType || !b?.nodeType) return document.documentElement;

	const a_first = a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;
	const start = a_first ? a : b;
	const end = a_first ? b : a;
	const range = document.createRange();
	range.setStart(start, 0);
	range.setEnd(end, 0);
	const common = range.commonAncestorContainer;

	if ((a !== common && b !== common) || start.contains(end)) {
		return is_offset_container(common) ? common : offset_parent(common);
	}

	const a_root = root_of(a);
	return a_root.host
		? common_offset_parent(a_root.host, b)
		: common_offset_parent(a, root_of(b).host);
}

function scroll_of(element, side = "top") {
	const key = side === "top" ? "scrollTop" : "scrollLeft";
	if (element.nodeName === "BODY" || element.nodeName === "HTML") {
		const doc = element.ownerDocument;
		return (doc.scrollingElement || doc.documentElement)[key];
	}
	return element[key];
}

function border_size(styles, axis) {
	const [a, b] = axis === "x" ? ["Left", "Right"] : ["Top", "Bottom"];
	return parseFloat(styles[`border${a}Width`]) + parseFloat(styles[`border${b}Width`]);
}

function document_size(doc) {
	const { body, documentElement: html } = doc;
	const size = (axis) =>
		Math.max(
			body[`offset${axis}`],
			body[`scroll${axis}`],
			html[`client${axis}`],
			html[`offset${axis}`],
			html[`scroll${axis}`]
		);
	return { width: size("Width"), height: size("Height") };
}

function client_rect(element) {
	const box = element.getBoundingClientRect();
	const rect = {
		left: box.left,
		top: box.top,
		width: box.right - box.left,
		height: box.bottom - box.top,
	};

	const sizes = element.nodeName === "HTML" ? document_size(element.ownerDocument) : {};
	let scrollbar_x = element.offsetWidth - (sizes.width || element.clientWidth || rect.width);
	let scrollbar_y = element.offsetHeight - (sizes.height || element.clientHeight || rect.height);
	if (scrollbar_x || scrollbar_y) {
		const styles = style_of(element);
		rect.width -= scrollbar_x - border_size(styles, "x");
		rect.height -= scrollbar_y - border_size(styles, "y");
	}
	return with_edges(rect);
}

function rect_relative_to(child, parent) {
	const is_html = parent.nodeName === "HTML";
	const child_rect = client_rect(child);
	const parent_rect = client_rect(parent);
	const styles = style_of(parent);
	const border_top = parseFloat(styles.borderTopWidth);
	const border_left = parseFloat(styles.borderLeftWidth);

	const rect = with_edges({
		top: child_rect.top - parent_rect.top - border_top,
		left: child_rect.left - parent_rect.left - border_left,
		width: child_rect.width,
		height: child_rect.height,
	});
	rect.marginTop = 0;
	rect.marginLeft = 0;

	if (is_html) {
		const margin_top = parseFloat(styles.marginTop);
		const margin_left = parseFloat(styles.marginLeft);
		rect.top -= border_top - margin_top;
		rect.bottom -= border_top - margin_top;
		rect.left -= border_left - margin_left;
		rect.right -= border_left - margin_left;
		rect.marginTop = margin_top;
		rect.marginLeft = margin_left;
	}

	const scroller = scroll_parent(child);
	if (parent === scroller && scroller.nodeName !== "BODY") {
		const top = scroll_of(parent, "top");
		const left = scroll_of(parent, "left");
		rect.top += top;
		rect.bottom += top;
		rect.left += left;
		rect.right += left;
	}
	return rect;
}

function viewport_rect_relative_to(element) {
	const html = element.ownerDocument.documentElement;
	const relative = rect_relative_to(element, html);
	return with_edges({
		top: scroll_of(html) - relative.top + relative.marginTop,
		left: scroll_of(html, "left") - relative.left + relative.marginLeft,
		width: Math.max(html.clientWidth, window.innerWidth || 0),
		height: Math.max(html.clientHeight, window.innerHeight || 0),
	});
}

function is_fixed(element) {
	if (element.nodeName === "BODY" || element.nodeName === "HTML") return false;
	if (style_of(element).position === "fixed") return true;
	const parent = parent_node(element);
	return parent ? is_fixed(parent) : false;
}

function get_boundaries(popper, reference, boundary) {
	const parent = common_offset_parent(popper, reference);
	let bounds = { top: 0, left: 0 };

	if (boundary === "viewport") {
		bounds = viewport_rect_relative_to(parent);
	} else {
		let node = boundary;
		if (boundary === "scrollParent") {
			node = scroll_parent(parent_node(reference));
			if (node.nodeName === "BODY") node = popper.ownerDocument.documentElement;
		} else if (boundary === "window") {
			node = popper.ownerDocument.documentElement;
		}

		const rect = rect_relative_to(node, parent);
		if (node.nodeName === "HTML" && !is_fixed(parent)) {
			const { width, height } = document_size(popper.ownerDocument);
			bounds.top += rect.top - rect.marginTop;
			bounds.bottom = height + rect.top;
			bounds.left += rect.left - rect.marginLeft;
			bounds.right = width + rect.left;
		} else {
			bounds = rect;
		}
	}

	bounds.left += BOUNDARY_PADDING;
	bounds.top += BOUNDARY_PADDING;
	bounds.right -= BOUNDARY_PADDING;
	bounds.bottom -= BOUNDARY_PADDING;
	return bounds;
}

function resolve_auto(placement, reference_rect, popper, reference) {
	if (!placement.includes("auto")) return placement;

	const bounds = get_boundaries(popper, reference, "viewport");
	const rooms = {
		top: { width: bounds.width, height: reference_rect.top - bounds.top },
		right: { width: bounds.right - reference_rect.right, height: bounds.height },
		bottom: { width: bounds.width, height: bounds.bottom - reference_rect.bottom },
		left: { width: reference_rect.left - bounds.left, height: bounds.height },
	};
	const by_area = Object.entries(rooms)
		.map(([side, room]) => ({ side, ...room, area: room.width * room.height }))
		.sort((a, b) => b.area - a.area);
	const fitting = by_area.filter(
		(room) => room.width >= popper.clientWidth && room.height >= popper.clientHeight
	);
	const side = (fitting[0] || by_area[0]).side;
	const variation = variation_of(placement);
	return side + (variation ? `-${variation}` : "");
}

function outer_size(element) {
	const styles = getComputedStyle(element);
	return {
		width:
			element.offsetWidth +
			parseFloat(styles.marginLeft || 0) +
			parseFloat(styles.marginRight || 0),
		height:
			element.offsetHeight +
			parseFloat(styles.marginTop || 0) +
			parseFloat(styles.marginBottom || 0),
	};
}

function popper_rect(popper, reference_rect, placement) {
	const side = base_side(placement);
	const size = outer_size(popper);
	const rect = { width: size.width, height: size.height };
	const horizontal = is_horizontal(side);
	const main = horizontal ? "top" : "left";
	const cross = horizontal ? "left" : "top";
	const length = horizontal ? "height" : "width";
	const depth = horizontal ? "width" : "height";

	rect[main] = reference_rect[main] + reference_rect[length] / 2 - size[length] / 2;
	rect[cross] =
		side === cross ? reference_rect[cross] - size[depth] : reference_rect[OPPOSITE[cross]];
	return rect;
}

function to_px(fragment, measurement, popper, reference) {
	const [, number, unit] = fragment.match(/((?:-|\+)?\d*\.?\d*)(.*)/);
	const value = +number;
	if (!value) return fragment;
	if (unit.startsWith("%")) {
		return (with_edges(unit === "%p" ? popper : reference)[measurement] / 100) * value;
	}
	if (unit === "vh" || unit === "vw") {
		const html = document.documentElement;
		const size =
			unit === "vh"
				? Math.max(html.clientHeight, window.innerHeight || 0)
				: Math.max(html.clientWidth, window.innerWidth || 0);
		return (size / 100) * value;
	}
	return value;
}

const is_numeric = (n) => n !== "" && !isNaN(parseFloat(n)) && isFinite(n);

function parse_offset(offset, popper, reference, side) {
	const result = [0, 0];
	const horizontal = is_horizontal(side);
	const fragments = offset.split(/(\+|-)/).map((fragment) => fragment.trim());
	const divider = fragments.findIndex((fragment) => fragment.search(/,|\s/) !== -1);
	const split = /\s*,\s*|\s+/;
	const groups =
		divider === -1
			? [fragments]
			: [
					[...fragments.slice(0, divider), fragments[divider].split(split)[0]],
					[fragments[divider].split(split)[1], ...fragments.slice(divider + 1)],
			  ];

	groups.forEach((group, index) => {
		const measurement = (index === 1 ? !horizontal : horizontal) ? "height" : "width";
		let merge_next = false;
		const terms = group
			.reduce((acc, fragment) => {
				if (acc[acc.length - 1] === "" && ["+", "-"].includes(fragment)) {
					acc[acc.length - 1] = fragment;
					merge_next = true;
				} else if (merge_next) {
					acc[acc.length - 1] += fragment;
					merge_next = false;
				} else {
					acc.push(fragment);
				}
				return acc;
			}, [])
			.map((fragment) => to_px(fragment, measurement, popper, reference));

		terms.forEach((term, i) => {
			if (is_numeric(term)) result[index] += term * (terms[i - 1] === "-" ? -1 : 1);
		});
	});
	return result;
}

function shift(data) {
	const variation = variation_of(data.placement);
	if (!variation) return;
	const { reference, popper } = data.offsets;
	const vertical = !is_horizontal(base_side(data.placement));
	const side = vertical ? "left" : "top";
	const measurement = vertical ? "width" : "height";
	popper[side] =
		variation === "start"
			? reference[side]
			: reference[side] + reference[measurement] - popper[measurement];
}

function apply_offset(data, offset, element) {
	const { popper, reference } = data.offsets;
	if (typeof offset === "function") {
		Object.assign(data.offsets, offset(data.offsets, element));
		return;
	}

	const side = base_side(data.placement);
	const [along, away] = is_numeric(+offset)
		? [+offset, 0]
		: parse_offset(offset, popper, reference, side);
	if (is_horizontal(side)) {
		popper.top += along;
		popper.left += side === "left" ? -away : away;
	} else {
		popper.left += along;
		popper.top += side === "top" ? -away : away;
	}
}

function prevent_overflow(data, boundary) {
	const { style } = data.popper;
	const saved = [style.top, style.left, style.transform];
	style.top = style.left = style.transform = "";
	const bounds = get_boundaries(data.popper, data.reference, boundary);
	[style.top, style.left, style.transform] = saved;
	data.boundaries = bounds;

	const popper = { ...data.offsets.popper };
	for (const side of ["left", "right", "top", "bottom"]) {
		if (side === "left" || side === "top") {
			if (popper[side] < bounds[side]) popper[side] = bounds[side];
		} else {
			const main = side === "right" ? "left" : "top";
			const size = side === "right" ? popper.width : popper.height;
			if (popper[side] > bounds[side])
				popper[main] = Math.min(popper[main], bounds[side] - size);
		}
	}
	data.offsets.popper = popper;
}

function keep_together(data) {
	const { popper, reference } = data.offsets;
	const vertical = !is_horizontal(base_side(data.placement));
	const side = vertical ? "right" : "bottom";
	const op_side = vertical ? "left" : "top";
	const measurement = vertical ? "width" : "height";
	if (popper[side] < Math.floor(reference[op_side])) {
		popper[op_side] = Math.floor(reference[op_side]) - popper[measurement];
	}
	if (popper[op_side] > Math.floor(reference[side])) {
		popper[op_side] = Math.floor(reference[side]);
	}
}

function position_arrow(data, selector) {
	const arrow = selector && data.popper.querySelector(selector);
	if (!arrow) return;

	const vertical = is_horizontal(base_side(data.placement));
	const length = vertical ? "height" : "width";
	const side = vertical ? "top" : "left";
	const cross = vertical ? "left" : "top";
	const op_side = vertical ? "bottom" : "right";
	const { popper, reference } = data.offsets;
	const arrow_size = outer_size(arrow)[length];

	if (reference[op_side] - arrow_size < popper[side]) {
		data.offsets.popper[side] -= popper[side] - (reference[op_side] - arrow_size);
	}
	if (reference[side] + arrow_size > popper[op_side]) {
		data.offsets.popper[side] += reference[side] + arrow_size - popper[op_side];
	}
	data.offsets.popper = with_edges(data.offsets.popper);

	const styles = getComputedStyle(data.popper);
	const Side = side === "top" ? "Top" : "Left";
	const center = reference[side] + reference[length] / 2 - arrow_size / 2;
	let value =
		center -
		data.offsets.popper[side] -
		parseFloat(styles[`margin${Side}`]) -
		parseFloat(styles[`border${Side}Width`]);
	value = Math.max(Math.min(popper[length] - arrow_size, value), 0);

	data.arrow = arrow;
	data.arrow_styles = { [side]: Math.round(value), [cross]: "" };
}

function flip(data, run_until_flip) {
	if (data.flipped && data.placement === data.original_placement) return;

	const bounds = get_boundaries(data.popper, data.reference, "viewport");
	const side = base_side(data.placement);
	if (!flips_out(data.offsets, side, bounds)) return;

	const variation = variation_of(data.placement);
	data.flipped = true;
	data.placement = OPPOSITE[side] + (variation ? `-${variation}` : "");
	Object.assign(
		data.offsets.popper,
		popper_rect(data.popper, data.offsets.reference, data.placement)
	);
	run_until_flip();
}

function flips_out({ popper, reference }, side, bounds) {
	const f = Math.floor;
	const overlaps_reference = {
		left: f(popper.right) > f(reference.left),
		right: f(popper.left) < f(reference.right),
		top: f(popper.bottom) > f(reference.top),
		bottom: f(popper.top) < f(reference.bottom),
	}[side];
	const overflows = {
		left: f(popper.left) < f(bounds.left),
		right: f(popper.right) > f(bounds.right),
		top: f(popper.top) < f(bounds.top),
		bottom: f(popper.bottom) > f(bounds.bottom),
	}[side];
	return overlaps_reference || overflows;
}

function rounded(data) {
	const { popper, reference } = data.offsets;
	const reference_width = Math.round(reference.width);
	const popper_width = Math.round(popper.width);
	const has_variation = data.placement.includes("-");
	const same_parity = reference_width % 2 === popper_width % 2;
	const both_odd = reference_width % 2 === 1 && popper_width % 2 === 1;
	const round_x =
		is_horizontal(data.placement) || has_variation || same_parity ? Math.round : Math.floor;
	return {
		left: round_x(both_odd && !has_variation ? popper.left - 1 : popper.left),
		top: Math.round(popper.top),
	};
}

function px(value) {
	return typeof value === "number" ? `${value}px` : value;
}

export class Anchor {
	constructor(reference, popper, options = {}) {
		this.reference = reference;
		this.popper = popper;
		this.options = {
			placement: "bottom",
			offset: 0,
			flip: true,
			boundary: "scrollParent",
			arrow: null,
			apply_style: true,
			on_create: () => {},
			on_update: () => {},
			...options,
		};
		this.is_created = false;
		this.is_destroyed = false;
		this.scroll_parents = [];

		let queued = false;
		this.update = () => {
			if (queued) return;
			queued = true;
			Promise.resolve().then(() => {
				queued = false;
				this.compute();
			});
		};
		this.schedule_update = () => requestAnimationFrame(this.update);

		if (this.options.apply_style) {
			const reference_rect = rect_relative_to(
				reference,
				common_offset_parent(popper, reference)
			);
			popper.setAttribute(
				"x-placement",
				resolve_auto(this.options.placement, reference_rect, popper, reference)
			);
			popper.style.position = "absolute";
		}

		this.update();
		this.listen();
	}

	compute() {
		if (this.is_destroyed) return;

		const { reference, popper } = this;
		const reference_rect = rect_relative_to(
			reference,
			common_offset_parent(popper, reference)
		);
		const placement = resolve_auto(this.options.placement, reference_rect, popper, reference);
		const data = {
			reference,
			popper,
			placement,
			original_placement: placement,
			flipped: false,
			offsets: {
				reference: reference_rect,
				popper: popper_rect(popper, reference_rect, placement),
			},
		};

		this.run(data, true);
		this.apply(data);

		if (!this.is_created) {
			this.is_created = true;
			this.options.on_create(data);
		} else {
			this.options.on_update(data);
		}
	}

	run(data, with_flip) {
		const steps = [
			() => shift(data),
			() => apply_offset(data, this.options.offset, this.reference),
			() => prevent_overflow(data, this.options.boundary),
			() => keep_together(data),
			() => position_arrow(data, this.options.arrow),
		];
		for (const step of steps) {
			data.offsets.popper = with_edges(data.offsets.popper);
			data.offsets.reference = with_edges(data.offsets.reference);
			step();
		}
		if (with_flip && this.options.flip) {
			data.offsets.popper = with_edges(data.offsets.popper);
			data.offsets.reference = with_edges(data.offsets.reference);
			flip(data, () => this.run(data, false));
		}
	}

	apply(data) {
		data.offsets.popper = with_edges(data.offsets.popper);
		data.offsets.reference = with_edges(data.offsets.reference);
		const bounds = data.boundaries;
		const ref = data.offsets.reference;
		const out_of_bounds =
			ref.bottom < bounds.top ||
			ref.left > bounds.right ||
			ref.top > bounds.bottom ||
			ref.right < bounds.left;

		if (!this.options.apply_style) return;

		const { left, top } = rounded(data);
		Object.assign(this.popper.style, {
			position: "absolute",
			transform: `translate3d(${left}px, ${top}px, 0)`,
			top: "0px",
			left: "0px",
			willChange: "transform",
		});
		this.popper.setAttribute("x-placement", data.placement);
		if (out_of_bounds) this.popper.setAttribute("x-out-of-boundaries", "");
		else this.popper.removeAttribute("x-out-of-boundaries");

		if (data.arrow) {
			for (const [prop, value] of Object.entries(data.arrow_styles)) {
				data.arrow.style[prop] = px(value);
			}
		}
	}

	listen() {
		window.addEventListener("resize", this.schedule_update, { passive: true });
		let scroller = scroll_parent(this.reference);
		for (;;) {
			const is_body = scroller.nodeName === "BODY";
			const target = is_body ? scroller.ownerDocument.defaultView : scroller;
			target.addEventListener("scroll", this.schedule_update, { passive: true });
			this.scroll_parents.push(target);
			if (is_body) break;
			scroller = scroll_parent(target.parentNode);
		}
	}

	destroy() {
		this.is_destroyed = true;
		if (this.options.apply_style) {
			this.popper.removeAttribute("x-placement");
			const { style } = this.popper;
			style.position = style.top = style.left = style.right = style.bottom = "";
			style.willChange = style.transform = "";
		}
		window.removeEventListener("resize", this.schedule_update);
		for (const target of this.scroll_parents) {
			target.removeEventListener("scroll", this.schedule_update);
		}
		this.scroll_parents = [];
	}
}
