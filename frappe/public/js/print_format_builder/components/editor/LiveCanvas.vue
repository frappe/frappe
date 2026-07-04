<template>
	<div class="live-canvas">
		<div v-if="!store.preview_doc_name.value" class="live-canvas-empty">
			{{ __("Pick a {0} above to start designing with real data", [__(doctype_label)]) }}
		</div>
		<div v-else-if="error" class="live-canvas-error">{{ error }}</div>
		<div v-else-if="!loaded" class="live-canvas-loading">{{ __("Rendering...") }}</div>
		<iframe v-show="loaded && !error" ref="frame" class="live-canvas-frame"></iframe>
	</div>
</template>

<script setup>
import { serialize_layout } from "../../utils";
import { ref, inject, watch, onActivated, onDeactivated } from "vue";

import { computed } from "vue";

let store = inject("$store");
let frame = ref(null);
let loaded = ref(false);
let error = ref(null);
let render_seq = 0;
let is_active = false;
let last_payload = null;

let doctype_label = computed(() => store.print_format.value?.doc_type || "document");

function desk_token(name, fallback) {
	const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
	return value || fallback;
}

function interaction_css() {
	const hover_line = desk_token("--gray-200", "#ededed");
	const hover_fill = desk_token("--gray-50", "#f8f8f8");
	const selected = desk_token("--gray-500", "#999999");
	const section_line = desk_token("--gray-400", "#c7c7c7");
	const danger = desk_token("--red-500", "#e03434");
	const muted = desk_token("--text-muted", "#525252");
	const backdrop = desk_token("--bg-gray", "#f3f3f3");
	const sheet = desk_token("--card-bg", "#fff");
	return `
	[data-pfb-path] { cursor: pointer; }
	[data-pfb-path]:hover { outline: 1px solid ${hover_line}; outline-offset: 1px; background: ${hover_fill}; }
	[data-pfb-section]:hover, [data-pfb-zone]:hover { outline: 1px dashed ${hover_line}; outline-offset: 3px; }
	.pfb-live-selected { outline: 1px solid ${selected}; outline-offset: 1px; }
	.pfb-live-selected-section { outline: 2px dashed ${section_line}; outline-offset: 3px; }
	.pfb-dragging { opacity: 0.4; }
	.pfb-drop-indicator {
		position: absolute;
		height: 2px;
		background: ${selected};
		border-radius: 1px;
		pointer-events: none;
		z-index: 9999;
		display: none;
	}
	.label[contenteditable], .section-label[contenteditable] {
		outline: 1px solid ${selected};
		outline-offset: 1px;
		cursor: text;
		border-radius: 2px;
	}
	body {
		position: relative;
		padding: 0 !important;
		margin: 0 !important;
		min-width: 0 !important;
		max-width: none !important;
		min-height: 0 !important;
		background: ${backdrop} !important;
		box-shadow: none !important;
	}
	.pfb-pages { padding: 24px 16px 16px; }
	.pfb-page {
		position: relative;
		display: flex;
		flex-direction: column;
		background: ${sheet};
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
		margin: 0 auto 34px;
		box-sizing: border-box;
	}
	.pfb-page-head, .pfb-clip { flex: none; }
	.pfb-page-foot { flex: none; margin-top: auto; }
	.pfb-page-head header, .pfb-page-foot footer {
		position: static !important;
		width: auto !important;
		padding-left: 0 !important;
		padding-right: 0 !important;
		padding-top: 0 !important;
		padding-bottom: 0 !important;
	}
	.pfb-page-num {
		position: absolute;
		bottom: -23px;
		left: 0;
		right: 0;
		text-align: center;
		font: 11px/1.5 -apple-system, sans-serif;
		color: ${muted};
	}
	.pfb-clip { overflow: hidden; }
	.pfb-flow { position: relative; }
	.pfb-del-chip {
		position: absolute;
		z-index: 10000;
		width: 18px;
		height: 18px;
		padding: 0;
		border: none;
		border-radius: 50%;
		background: ${danger};
		color: #fff;
		font: 700 12px/17px -apple-system, sans-serif;
		text-align: center;
		cursor: pointer;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
	}
	.pfb-add-section {
		display: block;
		margin: 0 auto 24px;
		padding: 5px 14px;
		border: 1px dashed ${section_line};
		border-radius: ${desk_token("--radius", "8px")};
		background: transparent;
		color: ${muted};
		font: 500 12px/1.5 -apple-system, sans-serif;
		cursor: pointer;
	}
	.pfb-add-section:hover {
		border-color: ${selected};
		color: ${desk_token("--text-color", "#171717")};
		background: ${hover_fill};
	}
`;
}

const PAGE_SIZES_MM = { A4: [210, 297], Letter: [216, 279.4] };

// Chrome renders PDFs under print media. Make the canvas lay out identically:
// activate @media print blocks and disable @media screen blocks, inlining
// linked stylesheets so their media blocks get the same treatment.
const css_cache = new Map();

function to_print_media(css) {
	return css
		.replace(/@media\s+print/g, "@media all")
		.replace(/@media\s+screen/g, "@media not all");
}

async function apply_print_media(html) {
	html = to_print_media(html);
	for (const [tag, href] of [...html.matchAll(/<link[^>]+href="([^"]+\.css)"[^>]*>/g)]) {
		let css = css_cache.get(href);
		if (css == null) {
			css = to_print_media(await fetch(href).then((r) => (r.ok ? r.text() : "")));
			css_cache.set(href, css);
		}
		html = html.replace(tag, () => `<style>${css}</style>`);
	}
	return html;
}

function serialized_format_data() {
	const clone = JSON.parse(JSON.stringify(store.layout.value));
	serialize_layout(clone);
	return JSON.stringify(clone);
}

function preview_settings() {
	const pf = store.print_format.value;
	const keys = [
		"font",
		"font_size",
		"label_color",
		"value_color",
		"margin_top",
		"margin_bottom",
		"margin_left",
		"margin_right",
		"page_number",
	];
	const out = {};
	for (const key of keys) {
		if (pf[key] != null) out[key] = pf[key];
	}
	return out;
}

// Chrome-measured heights of the repeating header/footer. The PDF pipeline
// shrinks the body page by these exact values, so sheet boundaries only match
// the PDF when we use Chrome's numbers, not our own on-screen measurement.
// Re-measured only when the letterhead / header / footer / settings change.
let measured = { key: null, pending: null, has: false, header: 0, footer: 0 };

function measure(args) {
	const lay = store.layout.value;
	const key = JSON.stringify([args.letterhead, lay.header, lay.footer, args.settings]);
	if (measured.key === key || measured.pending === key) return;
	measured.pending = key;
	frappe
		.call("frappe.utils.print_format_generator.measure_preview", args)
		.then((r) => {
			if (measured.pending !== key) return;
			measured = {
				key,
				pending: null,
				has: true,
				header: r.message.header_height || 0,
				footer: r.message.footer_height || 0,
			};
			paginate();
		})
		.catch(() => {
			if (measured.pending === key) measured.pending = null;
		});
}

function render() {
	if (!is_active || !store.preview_doc_name.value) return;
	const args = {
		doctype: store.print_format.value.doc_type,
		name: store.preview_doc_name.value,
		print_format: store.print_format.value.name,
		format_data: serialized_format_data(),
		letterhead: store.letterhead.value?.name || null,
		settings: JSON.stringify(preview_settings()),
	};
	measure(args);
	const payload = JSON.stringify(args);
	if (payload === last_payload && loaded.value) return;
	const seq = ++render_seq;
	frappe
		.call("frappe.utils.print_format_generator.render_preview", args)
		.then(async (r) => {
			const html = await apply_print_media(r.message);
			if (seq !== render_seq) return;
			error.value = null;
			last_payload = payload;
			write_document(html);
		})
		.catch((e) => {
			if (seq !== render_seq) return;
			error.value = e?.message || __("Failed to render preview");
		});
}

const debounced_render = frappe.utils.debounce(render, 400);

function write_document(html) {
	const doc = frame.value?.contentDocument;
	if (!doc) return;
	const scroll_y = frame.value.contentWindow?.scrollY || 0;
	doc.open();
	doc.write(html);
	doc.close();
	const style = doc.createElement("style");
	style.textContent = interaction_css();
	(doc.head || doc.documentElement).appendChild(style);
	doc.addEventListener("click", handle_click);
	doc.addEventListener("keydown", forward_keydown);
	doc.addEventListener("pointerdown", on_pointer_down);
	doc.addEventListener("dblclick", on_dblclick);
	doc.addEventListener("dragover", on_palette_drag_over);
	doc.addEventListener("drop", on_palette_drop);
	master = null;
	paginate();
	frame.value.contentWindow?.addEventListener("load", paginate);
	doc.fonts?.ready?.then(() => {
		if (frame.value?.contentDocument === doc) paginate();
	});
	frame.value.contentWindow?.scrollTo(0, scroll_y);
	loaded.value = true;
	update_highlight();
}

// ── Pagination: mirror the Chrome PDF page model ────────────
let master = null;

// PDF (repeat_header_footer on) puts letterhead + header/footer zones in
// per-page overlays outside the content flow — pull the same elements out
// so the canvas paginates the same content the PDF paginates.
function split_master(doc, repeat) {
	const flow_master = master.cloneNode(true);
	if (!repeat) return { flow_master, head_master: null, foot_master: null };

	const pick = (selectors) => {
		const wrap = doc.createElement("div");
		for (const sel of selectors) {
			for (const el of flow_master.querySelectorAll(sel)) wrap.appendChild(el);
		}
		return wrap.childNodes.length ? wrap : null;
	};
	const head_master = pick(["header", '[data-pfb-zone="header"]']);
	const foot_master = pick(['[data-pfb-zone="footer"]', "footer"]);
	return { flow_master, head_master, foot_master };
}

// Emulate the PDF engine's break rules: an unsplittable block (field, table
// row) that straddles a sheet boundary is pushed to the next sheet; pushed
// table rows get a cloned header row, like thead repetition in print.
function push_across_boundaries(doc, flow, usable) {
	const flow_top = () => flow.getBoundingClientRect().top;
	for (const el of [...flow.querySelectorAll(".field, .section-label, tr")]) {
		if (el.closest("thead")) continue;
		const rect = el.getBoundingClientRect();
		const top = rect.top - flow_top();
		const height = rect.height;
		if (height <= 0 || height > usable) continue;
		const page_end = (Math.floor(top / usable + 1e-4) + 1) * usable;
		if (top + height <= page_end + 0.5) continue;
		const gap = page_end - top;
		if (el.tagName === "TR") {
			const pad = doc.createElement("tr");
			pad.className = "pfb-break-pad";
			const td = doc.createElement("td");
			td.colSpan = el.children.length || 1;
			td.style.cssText = `height:${gap}px;padding:0;border:none;background:transparent;`;
			pad.appendChild(td);
			el.before(pad);
			const thead_row = el.closest("table")?.querySelector("thead tr");
			if (thead_row) el.before(thead_row.cloneNode(true));
		} else {
			// break-after: avoid — a section label stays with its first field
			let anchor = el;
			let push_gap = gap;
			const section = el.closest("[data-pfb-section], [data-pfb-zone]");
			const label = section?.querySelector(".section-label");
			if (label && el === section.querySelector(".field")) {
				const label_top = label.getBoundingClientRect().top - flow_top();
				if (label_top > page_end - usable) {
					anchor = label;
					push_gap = page_end - label_top;
				}
			}
			const spacer = doc.createElement("div");
			spacer.className = "pfb-break-spacer";
			spacer.style.height = `${push_gap}px`;
			anchor.before(spacer);
		}
	}
}

function paginate() {
	const doc = frame.value?.contentDocument;
	const body = doc?.body;
	if (!body) return;

	if (!master) {
		master = doc.createElement("div");
		while (body.firstChild) master.appendChild(body.firstChild);
	}
	doc.querySelector(".pfb-pages")?.remove();

	const probe = doc.createElement("div");
	probe.style.cssText = "position:absolute;height:100mm;width:0;visibility:hidden";
	body.appendChild(probe);
	const px_per_mm = probe.getBoundingClientRect().height / 100;
	probe.remove();
	if (!px_per_mm) return;

	const [page_w_mm, page_h_mm] = PAGE_SIZES_MM[body.dataset.pageSize] || PAGE_SIZES_MM.A4;
	const mt = parseFloat(body.dataset.marginTop) || 0;
	const mb = parseFloat(body.dataset.marginBottom) || 0;
	const ml = parseFloat(body.dataset.marginLeft) || 0;
	const mr = parseFloat(body.dataset.marginRight) || 0;
	const repeat = body.dataset.repeatHf === "1";

	const { flow_master, head_master, foot_master } = split_master(doc, repeat);

	const pages_el = doc.createElement("div");
	pages_el.className = "pfb-pages";
	body.appendChild(pages_el);

	const make_page = () => {
		const page = doc.createElement("div");
		page.className = "pfb-page";
		page.style.cssText = `width:${page_w_mm}mm;height:${page_h_mm}mm;padding:${mt}mm ${mr}mm ${mb}mm ${ml}mm;`;
		if (head_master) {
			const head = doc.createElement("div");
			head.className = "pfb-page-head";
			head.appendChild(head_master.cloneNode(true));
			if (measured.has) {
				head.style.height = `${measured.header}px`;
				head.style.overflow = "hidden";
			}
			page.appendChild(head);
		}
		const clip = doc.createElement("div");
		clip.className = "pfb-clip";
		const flow = doc.createElement("div");
		flow.className = "pfb-flow";
		clip.appendChild(flow);
		page.appendChild(clip);
		if (foot_master) {
			const foot = doc.createElement("div");
			foot.className = "pfb-page-foot";
			foot.appendChild(foot_master.cloneNode(true));
			if (measured.has) {
				foot.style.height = `${measured.footer}px`;
				foot.style.overflow = "hidden";
			}
			page.appendChild(foot);
		}
		pages_el.appendChild(page);
		return { page, flow, clip };
	};

	// Build page 1 first to establish repeating header/footer heights, then
	// derive the usable content height per sheet — same formula as the PDF
	// pipeline, where overlay heights shrink the body page. Chrome-measured
	// heights (exact PDF parity) take precedence over our own measurement.
	const first = make_page();
	const head_h = measured.has
		? measured.header
		: first.page.querySelector(".pfb-page-head")?.offsetHeight || 0;
	const foot_h = measured.has
		? measured.footer
		: first.page.querySelector(".pfb-page-foot")?.offsetHeight || 0;
	const usable = (page_h_mm - mt - mb) * px_per_mm - head_h - foot_h;
	if (usable <= 0) {
		pages_el.remove();
		return;
	}
	first.clip.style.height = `${usable}px`;
	first.flow.appendChild(flow_master);

	// Explicit page breaks: pad so following content starts on a fresh sheet
	for (const brk of first.flow.querySelectorAll(".page-break")) {
		const y = brk.getBoundingClientRect().bottom - first.flow.getBoundingClientRect().top;
		const pad = (usable - (y % usable)) % usable;
		if (pad > 0.5) {
			const spacer = doc.createElement("div");
			spacer.className = "pfb-break-spacer";
			spacer.style.height = `${pad}px`;
			brk.after(spacer);
		}
	}

	push_across_boundaries(doc, first.flow, usable);

	const total = first.flow.scrollHeight;
	const page_count = Math.max(1, Math.ceil((total - 1) / usable));
	const sliced = first.flow.firstChild;
	for (let k = 1; k < page_count; k++) {
		const pg = make_page();
		pg.clip.style.height = `${usable}px`;
		pg.flow.style.transform = `translateY(-${k * usable}px)`;
		pg.flow.appendChild(sliced.cloneNode(true));
	}
	for (const [k, page] of [...pages_el.querySelectorAll(".pfb-page")].entries()) {
		const num = doc.createElement("div");
		num.className = "pfb-page-num";
		num.textContent = __("Page {0} of {1}", [k + 1, page_count]);
		page.appendChild(num);
	}

	const add_btn = doc.createElement("button");
	add_btn.className = "pfb-add-section";
	add_btn.textContent = `+ ${__("Add Section")}`;
	add_btn.addEventListener("click", (e) => {
		e.stopPropagation();
		add_section();
	});
	pages_el.appendChild(add_btn);

	update_highlight();
}

function live_sections() {
	return (store.layout.value.sections || []).filter((s) => !s.remove);
}

function resolve_path(path) {
	const parts = path.split(".");
	let section, fields;
	if (parts[0] === "s") {
		section = live_sections()[+parts[1]];
		fields = section?.columns?.[+parts[2]]?.fields.filter((f) => !f.remove);
		return { section, field: fields?.[+parts[3]] };
	}
	section = parts[0] === "h" ? store.layout.value.header : store.layout.value.footer;
	fields = section?.columns?.[+parts[1]]?.fields.filter((f) => !f.remove);
	return { section, field: fields?.[+parts[2]] };
}

function path_of(field) {
	const sections = live_sections();
	for (let si = 0; si < sections.length; si++) {
		const cols = sections[si].columns || [];
		for (let ci = 0; ci < cols.length; ci++) {
			const fields = cols[ci].fields.filter((f) => !f.remove);
			const fi = fields.indexOf(field);
			if (fi !== -1) return `s.${si}.${ci}.${fi}`;
		}
	}
	for (const [prefix, zone] of [
		["h", store.layout.value.header],
		["f", store.layout.value.footer],
	]) {
		const cols = zone?.columns || [];
		for (let ci = 0; ci < cols.length; ci++) {
			const fields = cols[ci].fields.filter((f) => !f.remove);
			const fi = fields.indexOf(field);
			if (fi !== -1) return `${prefix}.${ci}.${fi}`;
		}
	}
	return null;
}

function handle_click(e) {
	e.preventDefault();
	if (suppress_click) {
		suppress_click = false;
		return;
	}
	const field_el = e.target.closest("[data-pfb-path]");
	const section_el = e.target.closest("[data-pfb-section]");
	const zone_el = e.target.closest("[data-pfb-zone]");

	store.selected_letterhead.value = false;
	store.selected_lh_footer.value = false;

	if (field_el) {
		const { section, field } = resolve_path(field_el.dataset.pfbPath);
		if (field) {
			store.selected_field.value = field;
			store.selected_section.value = section || null;
		}
	} else if (section_el) {
		store.selected_field.value = null;
		store.selected_section.value = live_sections()[+section_el.dataset.pfbSection] || null;
	} else if (zone_el) {
		store.selected_field.value = null;
		store.selected_section.value =
			zone_el.dataset.pfbZone === "header"
				? store.layout.value.header
				: store.layout.value.footer;
	} else if (e.target.closest("header")) {
		store.selected_field.value = null;
		store.selected_section.value = null;
		store.selected_letterhead.value = true;
	} else if (e.target.closest("footer")) {
		store.selected_field.value = null;
		store.selected_section.value = null;
		store.selected_lh_footer.value = true;
	} else {
		store.selected_field.value = null;
		store.selected_section.value = null;
	}
	update_highlight();
}

function remove_selected() {
	const lv = store.layout.value;
	const field = store.selected_field.value;
	if (field) {
		const zones = [lv.header, lv.footer, ...(lv.sections || [])].filter(Boolean);
		for (const zone of zones) {
			for (const col of zone.columns || []) {
				const idx = col.fields.indexOf(field);
				if (idx !== -1) {
					col.fields.splice(idx, 1);
					store.selected_field.value = null;
					return;
				}
			}
		}
		return;
	}
	const section = store.selected_section.value;
	if (section && lv.sections?.includes(section)) {
		lv.sections.splice(lv.sections.indexOf(section), 1);
		store.selected_section.value = null;
	}
}

function add_section() {
	const section = { label: "", columns: [{ label: "", fields: [] }] };
	store.layout.value.sections.push(section);
	store.selected_field.value = null;
	store.selected_section.value = section;
}

// ── Drop new fields/sections dragged from the left panel ────
// The panel uses SortableJS (native HTML5 drag), which can't drop across the
// iframe boundary on its own — so the panel exposes the dragged payload via
// the store and the iframe accepts it with plain dragover/drop handlers.
let palette_indicator = null;
let palette_target = null;

function on_palette_drag_over(e) {
	const payload = store.drag_payload.value;
	if (!payload) return;
	e.preventDefault();
	e.dataTransfer.dropEffect = "copy";
	const doc = frame.value.contentDocument;
	if (!palette_indicator) {
		palette_indicator = doc.createElement("div");
		palette_indicator.className = "pfb-drop-indicator";
		doc.body.appendChild(palette_indicator);
	}
	const under = doc.elementFromPoint(e.clientX, e.clientY);
	const win = frame.value.contentWindow;

	if (payload.kind === "section") {
		const section_el = under?.closest("[data-pfb-section]");
		palette_target = { section_idx: section_el ? +section_el.dataset.pfbSection : null };
		const rect = (section_el || doc.querySelector(".pfb-pages"))?.getBoundingClientRect();
		if (rect) {
			Object.assign(palette_indicator.style, {
				display: "block",
				top: `${rect.bottom + win.scrollY - 1}px`,
				left: `${rect.left + win.scrollX}px`,
				width: `${rect.width}px`,
			});
		}
		return;
	}

	const field_el = under?.closest("[data-pfb-path]");
	const col_el = under?.closest("[data-pfb-col]");
	if (field_el) {
		const rect = field_el.getBoundingClientRect();
		const before = e.clientY < rect.top + rect.height / 2;
		palette_target = {
			col_path: field_el.dataset.pfbPath.split(".").slice(0, -1).join("."),
			field_path: field_el.dataset.pfbPath,
			before,
		};
		Object.assign(palette_indicator.style, {
			display: "block",
			top: `${(before ? rect.top : rect.bottom) + win.scrollY - 1}px`,
			left: `${rect.left + win.scrollX}px`,
			width: `${rect.width}px`,
		});
	} else if (col_el) {
		palette_target = { col_path: col_el.dataset.pfbCol, append: true };
		const rect = col_el.getBoundingClientRect();
		Object.assign(palette_indicator.style, {
			display: "block",
			top: `${rect.bottom + win.scrollY - 1}px`,
			left: `${rect.left + win.scrollX}px`,
			width: `${rect.width}px`,
		});
	} else {
		palette_target = null;
		palette_indicator.style.display = "none";
	}
}

function on_palette_drop(e) {
	const payload = store.drag_payload.value;
	if (!payload) return;
	e.preventDefault();
	palette_indicator?.remove();
	palette_indicator = null;
	const target = palette_target;
	palette_target = null;
	store.drag_payload.value = null;

	if (payload.kind === "section") {
		const sections = store.layout.value.sections;
		const idx = target?.section_idx != null ? target.section_idx + 1 : sections.length;
		sections.splice(idx, 0, payload.section);
		return;
	}
	if (!target) return;
	const col = column_of(target.col_path);
	if (!col) return;
	if (target.append || !target.field_path) {
		col.fields.push(payload.df);
	} else {
		const filtered = col.fields.filter((f) => !f.remove);
		const anchor = filtered[+target.field_path.split(".").at(-1)];
		let idx = anchor ? col.fields.indexOf(anchor) : col.fields.length;
		if (!target.before) idx += 1;
		col.fields.splice(idx, 0, payload.df);
	}
	store.selected_field.value = payload.df;
}

// ── Drag to reorder ─────────────────────────────────────────
let drag = null;
let suppress_click = false;

function column_of(col_path) {
	const parts = col_path.split(".");
	if (parts[0] === "s") return live_sections()[+parts[1]]?.columns?.[+parts[2]];
	const zone = parts[0] === "h" ? store.layout.value.header : store.layout.value.footer;
	return zone?.columns?.[+parts[1]];
}

function on_pointer_down(e) {
	if (e.button !== 0 || e.target.isContentEditable) return;
	const el = e.target.closest("[data-pfb-path]");
	if (!el) return;
	const doc = frame.value.contentDocument;
	drag = {
		el,
		path: el.dataset.pfbPath,
		start_x: e.clientX,
		start_y: e.clientY,
		active: false,
		indicator: null,
		target: null,
	};
	doc.addEventListener("pointermove", on_pointer_move);
	doc.addEventListener("pointerup", on_pointer_up, { once: true });
}

function on_pointer_move(e) {
	if (!drag) return;
	const doc = frame.value.contentDocument;
	if (!drag.active) {
		if (Math.hypot(e.clientX - drag.start_x, e.clientY - drag.start_y) < 5) return;
		drag.active = true;
		drag.el.classList.add("pfb-dragging");
		doc.body.style.userSelect = "none";
		drag.indicator = doc.createElement("div");
		drag.indicator.className = "pfb-drop-indicator";
		doc.body.appendChild(drag.indicator);
	}
	e.preventDefault();
	const under = doc.elementFromPoint(e.clientX, e.clientY);
	const field_el = under?.closest("[data-pfb-path]");
	const col_el = under?.closest("[data-pfb-col]");
	if (field_el && field_el !== drag.el) {
		const rect = field_el.getBoundingClientRect();
		const before = e.clientY < rect.top + rect.height / 2;
		drag.target = {
			col_path: field_el.dataset.pfbPath.split(".").slice(0, -1).join("."),
			field_path: field_el.dataset.pfbPath,
			before,
		};
		position_indicator(rect, before);
	} else if (col_el) {
		drag.target = { col_path: col_el.dataset.pfbCol, append: true };
		const rect = col_el.getBoundingClientRect();
		position_indicator(rect, !col_el.querySelector("[data-pfb-path]"));
	} else {
		drag.target = null;
		if (drag.indicator) drag.indicator.style.display = "none";
	}
}

function position_indicator(rect, at_top) {
	const win = frame.value.contentWindow;
	Object.assign(drag.indicator.style, {
		display: "block",
		top: (at_top ? rect.top : rect.bottom) + win.scrollY - 1 + "px",
		left: rect.left + win.scrollX + "px",
		width: rect.width + "px",
	});
}

function on_pointer_up() {
	const doc = frame.value.contentDocument;
	doc?.removeEventListener("pointermove", on_pointer_move);
	if (!drag) return;
	const d = drag;
	drag = null;
	if (!d.active) return;
	suppress_click = true;
	d.el.classList.remove("pfb-dragging");
	doc.body.style.userSelect = "";
	d.indicator?.remove();
	if (d.target) move_field(d.path, d.target);
}

function move_field(src_path, target) {
	const src_parts = src_path.split(".");
	const src_col = column_of(src_parts.slice(0, -1).join("."));
	const dst_col = column_of(target.col_path);
	if (!src_col || !dst_col) return;

	const field = src_col.fields.filter((f) => !f.remove)[+src_parts.at(-1)];
	if (!field) return;

	const anchor = target.field_path
		? dst_col.fields.filter((f) => !f.remove)[+target.field_path.split(".").at(-1)]
		: null;

	src_col.fields.splice(src_col.fields.indexOf(field), 1);

	if (anchor) {
		let idx = dst_col.fields.indexOf(anchor);
		if (!target.before) idx += 1;
		dst_col.fields.splice(idx, 0, field);
	} else {
		dst_col.fields.push(field);
	}
	store.selected_field.value = field;
}

// ── Inline label editing ────────────────────────────────────
function on_dblclick(e) {
	const doc = frame.value.contentDocument;
	const field_el = e.target.closest("[data-pfb-path]");
	const field_label = field_el?.querySelector(".label");
	const section_el = e.target.closest("[data-pfb-section]");
	const section_label = e.target.closest(".section-label");

	let el, commit;
	if (field_label && field_label.contains(e.target)) {
		const { field } = resolve_path(field_el.dataset.pfbPath);
		if (!field) return;
		el = field_label;
		commit = (text) => {
			if (text !== field.label) field.label = text;
		};
	} else if (section_label && section_el) {
		const section = live_sections()[+section_el.dataset.pfbSection];
		if (!section) return;
		el = section_label;
		commit = (text) => {
			if (text !== section.label) section.label = text;
		};
	} else {
		return;
	}

	e.preventDefault();
	const original = el.textContent;
	el.setAttribute("contenteditable", "plaintext-only");
	el.focus();
	doc.getSelection()?.selectAllChildren(el);

	const on_key = (ke) => {
		ke.stopPropagation();
		if (ke.key === "Enter") {
			ke.preventDefault();
			el.blur();
		} else if (ke.key === "Escape") {
			el.textContent = original;
			el.blur();
		}
	};
	el.addEventListener("keydown", on_key);
	el.addEventListener(
		"blur",
		() => {
			el.removeEventListener("keydown", on_key);
			el.removeAttribute("contenteditable");
			commit(el.textContent.trim());
		},
		{ once: true }
	);
}

function forward_keydown(e) {
	if ((e.key === "Delete" || e.key === "Backspace") && !e.target.isContentEditable) {
		e.preventDefault();
		remove_selected();
		return;
	}
	document.dispatchEvent(
		new KeyboardEvent("keydown", {
			key: e.key,
			ctrlKey: e.ctrlKey,
			metaKey: e.metaKey,
			shiftKey: e.shiftKey,
		})
	);
}

function place_delete_chip(doc, el, title) {
	const chip = doc.createElement("button");
	chip.className = "pfb-del-chip";
	chip.title = title;
	chip.textContent = "×";
	chip.addEventListener("click", (e) => {
		e.stopPropagation();
		remove_selected();
	});
	const rect = el.getBoundingClientRect();
	const win = doc.defaultView;
	chip.style.top = `${rect.top + win.scrollY - 9}px`;
	chip.style.left = `${rect.right + win.scrollX - 9}px`;
	doc.body.appendChild(chip);
}

function update_highlight() {
	const doc = frame.value?.contentDocument;
	if (!doc) return;
	for (const el of doc.querySelectorAll(".pfb-live-selected, .pfb-live-selected-section")) {
		el.classList.remove("pfb-live-selected", "pfb-live-selected-section");
	}
	for (const chip of doc.querySelectorAll(".pfb-del-chip")) chip.remove();
	const mark = (selector, cls) => {
		const els = [...doc.querySelectorAll(selector)];
		for (const el of els) el.classList.add(cls);
		return els[0];
	};
	const field = store.selected_field.value;
	if (field) {
		const path = path_of(field);
		const el = path && mark(`[data-pfb-path="${path}"]`, "pfb-live-selected");
		if (el) place_delete_chip(doc, el, __("Remove field"));
		return;
	}
	const section = store.selected_section.value;
	if (section) {
		if (section === store.layout.value.header || section === store.layout.value.footer) {
			const zone = section === store.layout.value.header ? "header" : "footer";
			mark(`[data-pfb-zone="${zone}"]`, "pfb-live-selected-section");
			return;
		}
		const idx = live_sections().indexOf(section);
		if (idx !== -1) {
			const el = mark(`[data-pfb-section="${idx}"]`, "pfb-live-selected-section");
			if (el) place_delete_chip(doc, el, __("Remove section"));
		}
	}
}

watch(() => store.layout.value, debounced_render, { deep: true });
watch(() => store.print_format.value, debounced_render, { deep: true });
watch(() => store.preview_doc_name.value, render);
watch(() => store.letterhead.value?.name, render);
watch([() => store.selected_field.value, () => store.selected_section.value], update_highlight);

onActivated(() => {
	is_active = true;
	loaded.value = false;
	last_payload = null;
	render();
});

onDeactivated(() => {
	is_active = false;
	render_seq++;
});
</script>

<style scoped>
.live-canvas {
	height: 100%;
	display: flex;
	flex-direction: column;
}

.live-canvas-frame {
	flex: 1;
	width: 100%;
	border: none;
	zoom: var(--pfb-zoom, 1);
}

.live-canvas-loading,
.live-canvas-error,
.live-canvas-empty {
	padding: 2rem;
	text-align: center;
	color: var(--text-muted);
	font-size: var(--text-sm);
}

.live-canvas-error {
	color: var(--red-500);
}
</style>
