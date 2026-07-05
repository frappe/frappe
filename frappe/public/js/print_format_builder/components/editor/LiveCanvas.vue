<template>
	<div class="live-canvas">
		<div v-if="!store.preview_doc_name.value" class="live-canvas-empty">
			{{ __("Pick a {0} above to start designing with real data", [__(doctype_label)]) }}
		</div>
		<div v-else-if="error" class="live-canvas-error">{{ error }}</div>
		<div v-else-if="!loaded" class="live-canvas-loading">{{ __("Rendering...") }}</div>
		<div v-show="loaded && !error" ref="host" class="live-canvas-host"></div>
	</div>
</template>

<script setup>
import Sortable from "sortablejs";
import { serialize_layout } from "../../utils";
import {
	ref,
	inject,
	watch,
	computed,
	nextTick,
	onMounted,
	onUnmounted,
	onActivated,
	onDeactivated,
} from "vue";

let store = inject("$store");
let host = ref(null);
let loaded = ref(false);
let error = ref(null);
let render_seq = 0;
let is_active = false;
let last_payload = null;

let doctype_label = computed(() => store.print_format.value?.doc_type || "document");

// The canvas lives in a shadow root: same document as the desk (so native
// drag & drop, selection, and design tokens all just work) but the print
// stylesheet and the desk stylesheet cannot leak into each other.
let shadow = null;
let root_el = null;
let server_style = null;

const INTERACTION_CSS = `
	[data-pfb-path] { cursor: grab; }
	[data-pfb-path]:hover { outline: 1px solid var(--gray-200, #ededed); outline-offset: -1px; background: var(--gray-50, #f8f8f8); position: relative; z-index: 2; }
	[data-pfb-section]:hover, [data-pfb-zone]:hover { outline: 1px dashed var(--gray-200, #ededed); outline-offset: 3px; position: relative; z-index: 1; }
	.pfb-live-selected { outline: 1px solid var(--gray-500, #999); outline-offset: -1px; position: relative; z-index: 3; }
	.pfb-live-selected-section { outline: 2px dashed var(--gray-400, #c7c7c7); outline-offset: 3px; position: relative; z-index: 1; }
	.pfb-sortable-ghost { opacity: 0.35; outline: 1px dashed var(--gray-400, #c7c7c7); outline-offset: -1px; }
	.pfb-sortable-drag { opacity: 1 !important; background: var(--card-bg, #fff); box-shadow: 0 4px 14px rgba(0, 0, 0, 0.18) !important; }
	.pfb-drop-indicator {
		position: absolute;
		height: 2px;
		background: var(--gray-500, #999);
		border-radius: 1px;
		pointer-events: none;
		z-index: 9999;
		display: none;
	}
	.label[contenteditable], .section-label[contenteditable] {
		outline: 1px solid var(--gray-500, #999);
		outline-offset: 1px;
		cursor: text;
		border-radius: 2px;
	}
	.label[contenteditable]::selection, .section-label[contenteditable]::selection {
		background: var(--gray-300, #e2e2e2);
	}
	.pfb-root {
		position: relative;
		background: var(--bg-gray, #f3f3f3);
	}
	.pfb-pages { padding: 24px 16px 16px; }
	.pfb-pages-measuring {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		visibility: hidden;
		pointer-events: none;
	}
	.pfb-page {
		position: relative;
		display: flex;
		flex-direction: column;
		background: var(--card-bg, #fff);
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15) !important;
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
		color: var(--text-muted, #525252);
	}
	.pfb-clip { overflow: hidden; }
	.pfb-flow { position: relative; }
	.pfb-del-chip {
		position: absolute;
		z-index: 10000;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 22px;
		height: 22px;
		padding: 0;
		border: 1px solid var(--border-color, #ededed);
		border-radius: var(--radius, 6px);
		background: var(--card-bg, #fff);
		color: var(--red-500, #e03434);
		cursor: pointer;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08) !important;
	}
	.pfb-del-chip:hover {
		background: var(--red-50, #fff5f5);
	}
	.pfb-del-chip svg {
		width: 12px;
		height: 12px;
		fill: none;
		stroke: currentColor;
		stroke-width: 1.5;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.pfb-add-section {
		display: block;
		margin: 0 auto 24px;
		padding: 5px 14px;
		border: 1px dashed var(--gray-400, #c7c7c7);
		border-radius: var(--radius, 8px);
		background: transparent;
		color: var(--text-muted, #525252);
		font: 500 12px/1.5 -apple-system, sans-serif;
		cursor: pointer;
	}
	.pfb-add-section:hover {
		border-color: var(--gray-500, #999);
		color: var(--text-color, #171717);
		background: var(--gray-50, #f8f8f8);
	}
`;

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

// Inside a shadow root there is no body/html/:root — the print CSS's
// document-level rules must land on the canvas container instead.
function scope_css(css) {
	return css.replace(/(^|[\s,{}])(?:body|html|:root)\b/g, "$1.pfb-root");
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
			set_content(html);
		})
		.catch((e) => {
			if (seq !== render_seq) return;
			error.value = e?.message || __("Failed to render preview");
		});
}

const debounced_render = frappe.utils.debounce(render, 400);

function ensure_shadow() {
	if (shadow || !host.value) return;
	shadow = host.value.attachShadow({ mode: "open" });
	server_style = document.createElement("style");
	const interaction = document.createElement("style");
	interaction.textContent = INTERACTION_CSS;
	root_el = document.createElement("div");
	root_el.className = "pfb-root";
	shadow.append(server_style, interaction, root_el);
	shadow.addEventListener("click", handle_click);
	shadow.addEventListener("dblclick", on_dblclick);
	shadow.addEventListener("dragover", on_palette_drag_over);
	shadow.addEventListener("drop", on_palette_drop);
}

function set_content(html) {
	ensure_shadow();
	if (!shadow) return;
	const parsed = new DOMParser().parseFromString(html, "text/html");

	// @font-face does not apply inside shadow roots — web font links (Google
	// fonts etc.) go on the main document instead.
	for (const link of [...parsed.querySelectorAll("link[rel=stylesheet]")]) {
		const href = link.getAttribute("href");
		if (
			href &&
			!document.head.querySelector(`link[data-pfb-font][href="${CSS.escape(href)}"]`)
		) {
			const l = document.createElement("link");
			l.rel = "stylesheet";
			l.href = href;
			l.dataset.pfbFont = "1";
			document.head.appendChild(l);
		}
		link.remove();
	}

	const css = scope_css(
		[...parsed.querySelectorAll("style")].map((s) => s.textContent).join("\n")
	);
	if (server_style.textContent !== css) server_style.textContent = css;

	for (const attr of [...root_el.attributes]) {
		if (attr.name.startsWith("data-")) root_el.removeAttribute(attr.name);
	}
	for (const attr of [...parsed.body.attributes]) {
		if (attr.name.startsWith("data-")) root_el.setAttribute(attr.name, attr.value);
	}

	master = document.createElement("div");
	for (const node of [...parsed.body.childNodes]) {
		if (node.tagName === "STYLE" || node.tagName === "SCRIPT") continue;
		master.appendChild(document.adoptNode(node));
	}

	if (loaded.value) {
		paginate();
	} else {
		// The host is hidden until the first content arrives — reveal it
		// before paginating, measurements inside display:none are all zero.
		loaded.value = true;
		nextTick(paginate);
	}
}

// ── Pagination: mirror the Chrome PDF page model ────────────
let master = null;

// PDF (repeat_header_footer on) puts letterhead + header/footer zones in
// per-page overlays outside the content flow — pull the same elements out
// so the canvas paginates the same content the PDF paginates.
function split_master(repeat) {
	const flow_master = master.cloneNode(true);
	if (!repeat) return { flow_master, head_master: null, foot_master: null };

	const pick = (selectors) => {
		const wrap = document.createElement("div");
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
function push_across_boundaries(flow, usable) {
	const z = zoom_factor();
	const flow_top = () => flow.getBoundingClientRect().top;
	for (const el of [...flow.querySelectorAll(".field, .section-label, tr")]) {
		if (el.closest("thead")) continue;
		const rect = el.getBoundingClientRect();
		const top = (rect.top - flow_top()) / z;
		const height = rect.height / z;
		if (height <= 0 || height > usable) continue;
		const page_end = (Math.floor(top / usable + 1e-4) + 1) * usable;
		if (top + height <= page_end + 0.5) continue;
		const gap = page_end - top;
		if (el.tagName === "TR") {
			const pad = document.createElement("tr");
			pad.className = "pfb-break-pad";
			const td = document.createElement("td");
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
				const label_top = (label.getBoundingClientRect().top - flow_top()) / z;
				if (label_top > page_end - usable) {
					anchor = label;
					push_gap = page_end - label_top;
				}
			}
			const spacer = document.createElement("div");
			spacer.className = "pfb-break-spacer";
			spacer.style.height = `${push_gap}px`;
			anchor.before(spacer);
		}
	}
}

// Zoom is applied on the host element; rects come back in zoomed viewport
// pixels while absolute positions inside the root are in local pixels.
function zoom_factor() {
	return parseFloat(getComputedStyle(host.value).zoom) || 1;
}

function local_rect(rect) {
	const base = root_el.getBoundingClientRect();
	const z = zoom_factor();
	return {
		top: (rect.top - base.top) / z,
		left: (rect.left - base.left) / z,
		bottom: (rect.bottom - base.top) / z,
		right: (rect.right - base.left) / z,
		width: rect.width / z,
		height: rect.height / z,
	};
}

function paginate() {
	if (!master || !root_el || !root_el.dataset.pageSize) return;

	root_el.querySelector(".pfb-pages-measuring")?.remove();

	const probe = document.createElement("div");
	probe.style.cssText = "position:absolute;height:100mm;width:0;visibility:hidden";
	root_el.appendChild(probe);
	const px_per_mm = probe.getBoundingClientRect().height / 100 / zoom_factor();
	probe.remove();
	if (!px_per_mm) return;

	const [page_w_mm, page_h_mm] = PAGE_SIZES_MM[root_el.dataset.pageSize] || PAGE_SIZES_MM.A4;
	const mt = parseFloat(root_el.dataset.marginTop) || 0;
	const mb = parseFloat(root_el.dataset.marginBottom) || 0;
	const ml = parseFloat(root_el.dataset.marginLeft) || 0;
	const mr = parseFloat(root_el.dataset.marginRight) || 0;
	const repeat = root_el.dataset.repeatHf === "1";

	const { flow_master, head_master, foot_master } = split_master(repeat);

	const pages_el = document.createElement("div");
	pages_el.className = "pfb-pages pfb-pages-measuring";
	root_el.appendChild(pages_el);

	const make_page = () => {
		const page = document.createElement("div");
		page.className = "pfb-page";
		page.style.cssText = `width:${page_w_mm}mm;height:${page_h_mm}mm;padding:${mt}mm ${mr}mm ${mb}mm ${ml}mm;`;
		if (head_master) {
			const head = document.createElement("div");
			head.className = "pfb-page-head";
			head.appendChild(head_master.cloneNode(true));
			if (measured.has) {
				head.style.height = `${measured.header}px`;
				head.style.overflow = "hidden";
			}
			page.appendChild(head);
		}
		const clip = document.createElement("div");
		clip.className = "pfb-clip";
		const flow = document.createElement("div");
		flow.className = "pfb-flow";
		clip.appendChild(flow);
		page.appendChild(clip);
		if (foot_master) {
			const foot = document.createElement("div");
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
	const z = zoom_factor();
	for (const brk of first.flow.querySelectorAll(".page-break")) {
		const y =
			(brk.getBoundingClientRect().bottom - first.flow.getBoundingClientRect().top) / z;
		const pad = (usable - (y % usable)) % usable;
		if (pad > 0.5) {
			const spacer = document.createElement("div");
			spacer.className = "pfb-break-spacer";
			spacer.style.height = `${pad}px`;
			brk.after(spacer);
		}
	}

	push_across_boundaries(first.flow, usable);

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
		const num = document.createElement("div");
		num.className = "pfb-page-num";
		num.textContent = __("Page {0} of {1}", [k + 1, page_count]);
		page.appendChild(num);
	}

	const add_btn = document.createElement("button");
	add_btn.className = "pfb-add-section";
	add_btn.textContent = `+ ${__("Add Section")}`;
	add_btn.addEventListener("click", (e) => {
		e.stopPropagation();
		add_section();
	});
	pages_el.appendChild(add_btn);

	for (const stale of root_el.querySelectorAll(".pfb-pages")) {
		if (stale !== pages_el) stale.remove();
	}
	root_el.querySelector(".pfb-del-chip")?.remove();
	pages_el.classList.remove("pfb-pages-measuring");

	setup_sortables(pages_el);
	update_highlight();
}

// ── Native drag & drop via SortableJS on the rendered pages ──
let sortables = [];
let suppress_click = false;

function setup_sortables(pages_el) {
	for (const s of sortables) s.destroy();
	sortables = [];
	for (const col of pages_el.querySelectorAll("[data-pfb-col]")) {
		sortables.push(
			new Sortable(col, {
				group: "pfb-fields",
				draggable: "[data-pfb-path]",
				animation: 150,
				ghostClass: "pfb-sortable-ghost",
				dragClass: "pfb-sortable-drag",
				onStart: () => (suppress_click = true),
				onEnd: on_sort_end,
			})
		);
	}
}

function on_sort_end(evt) {
	setTimeout(() => (suppress_click = false));
	const src_col_path = evt.from.dataset.pfbCol;
	const dst_col_path = evt.to.dataset.pfbCol;
	if (evt.from === evt.to && evt.oldIndex === evt.newIndex) return;

	const src_col = column_of(src_col_path);
	const dst_col = column_of(dst_col_path);
	if (!src_col || !dst_col) return;

	const field = src_col.fields.filter((f) => !f.remove)[evt.oldIndex];
	if (!field) return;
	src_col.fields.splice(src_col.fields.indexOf(field), 1);

	const dst_filtered = dst_col.fields.filter((f) => !f.remove);
	const anchor = dst_filtered[evt.newIndex];
	const raw_idx = anchor ? dst_col.fields.indexOf(anchor) : dst_col.fields.length;
	dst_col.fields.splice(raw_idx, 0, field);
	store.selected_field.value = field;

	optimistic(() => {
		const el = master_el(`[data-pfb-path="${src_col_path}.${evt.oldIndex}"]`);
		const col_el = master_el(`[data-pfb-col="${dst_col_path}"]`);
		if (!el || !col_el) return;
		const items = [...col_el.querySelectorAll("[data-pfb-path]")].filter((n) => n !== el);
		const before = items[evt.newIndex];
		before ? before.before(el) : col_el.appendChild(el);
	});
}

// ── Optimistic edits ────────────────────────────────────────
// Structural edits mirror the store mutation onto the master DOM and
// repaginate locally, so the canvas responds in the same frame; the
// immediate background render then swaps in exact server markup.
function master_el(selector) {
	return master?.querySelector(selector);
}

// Sections that render nothing are skipped by the server, so DOM section
// indices are SPARSE and must track store indices — never rewrite them from
// DOM order. Field and column indices are dense and follow DOM order.
function renumber_master() {
	if (!master) return;
	master.querySelectorAll("[data-pfb-section]").forEach((sec) => {
		const si = sec.dataset.pfbSection;
		sec.querySelectorAll("[data-pfb-col]").forEach((col, ci) => {
			col.dataset.pfbCol = `s.${si}.${ci}`;
			col.querySelectorAll("[data-pfb-path]").forEach((f, fi) => {
				f.dataset.pfbPath = `s.${si}.${ci}.${fi}`;
			});
		});
	});
	for (const [prefix, zone] of [
		["h", "header"],
		["f", "footer"],
	]) {
		master.querySelectorAll(`[data-pfb-zone="${zone}"] [data-pfb-col]`).forEach((col, ci) => {
			col.dataset.pfbCol = `${prefix}.${ci}`;
			col.querySelectorAll("[data-pfb-path]").forEach((f, fi) => {
				f.dataset.pfbPath = `${prefix}.${ci}.${fi}`;
			});
		});
	}
}

function shift_section_indices(from, delta) {
	master.querySelectorAll("[data-pfb-section]").forEach((sec) => {
		const idx = +sec.dataset.pfbSection;
		if (idx >= from) sec.dataset.pfbSection = idx + delta;
	});
}

function optimistic(mutate) {
	if (master) {
		mutate();
		renumber_master();
		paginate();
	}
	render();
}

function synthetic_field_el(df, col_el) {
	const sample = col_el.querySelector("[data-pfb-path]") || master_el("[data-pfb-path]");
	if (!sample) {
		const el = document.createElement("div");
		el.className = "field";
		el.textContent = df.label || df.fieldname || "";
		return el;
	}
	const el = sample.cloneNode(true);
	el.classList.remove("pfb-live-selected");
	const label = el.querySelector(".label");
	if (label) label.textContent = df.label || df.fieldname || "";
	const value = el.querySelector(".value");
	if (value) {
		const v = store.preview_doc.value?.[df.fieldname];
		if (v != null && v !== "") {
			value.textContent = String(v);
			value.classList.remove("pfb-empty-value");
		} else {
			value.textContent = "—";
			value.classList.add("pfb-empty-value");
		}
	}
	return el;
}

function synthetic_section_el(section) {
	const sample = [...master.querySelectorAll("[data-pfb-section]")].at(-1);
	let el;
	if (sample) {
		el = sample.cloneNode(true);
		el.classList.remove("pfb-live-selected-section");
		for (const n of el.querySelectorAll("[data-pfb-path], .section-label, .page-break")) {
			n.remove();
		}
	} else {
		el = document.createElement("div");
		el.className = "section";
		el.dataset.pfbSection = "0";
		const col = document.createElement("div");
		col.dataset.pfbCol = "s.0.0";
		el.appendChild(col);
	}
	if (section?.page_break) {
		const brk = document.createElement("div");
		brk.className = "page-break";
		el.prepend(brk);
	}
	return el;
}

function append_section_el(el) {
	const last = [...master.querySelectorAll("[data-pfb-section]")].at(-1);
	if (last) {
		last.after(el);
	} else {
		const foot =
			master.querySelector('[data-pfb-zone="footer"]') || master.querySelector("footer");
		foot ? foot.before(el) : master.appendChild(el);
	}
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

function column_of(col_path) {
	const parts = col_path.split(".");
	if (parts[0] === "s") return live_sections()[+parts[1]]?.columns?.[+parts[2]];
	const zone = parts[0] === "h" ? store.layout.value.header : store.layout.value.footer;
	return zone?.columns?.[+parts[1]];
}

function handle_click(e) {
	e.preventDefault();
	e.stopPropagation();
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
		const path = path_of(field);
		const zones = [lv.header, lv.footer, ...(lv.sections || [])].filter(Boolean);
		for (const zone of zones) {
			for (const col of zone.columns || []) {
				const idx = col.fields.indexOf(field);
				if (idx !== -1) {
					col.fields.splice(idx, 1);
					store.selected_field.value = null;
					optimistic(() => master_el(`[data-pfb-path="${path}"]`)?.remove());
					return;
				}
			}
		}
		return;
	}
	const section = store.selected_section.value;
	if (section && lv.sections?.includes(section)) {
		const idx = live_sections().indexOf(section);
		lv.sections.splice(lv.sections.indexOf(section), 1);
		store.selected_section.value = null;
		optimistic(() => {
			master_el(`[data-pfb-section="${idx}"]`)?.remove();
			shift_section_indices(idx + 1, -1);
		});
	}
}

function add_section() {
	const section = { label: "", columns: [{ label: "", fields: [] }] };
	store.layout.value.sections.push(section);
	store.selected_field.value = null;
	store.selected_section.value = section;
	optimistic(() => {
		const el = synthetic_section_el(section);
		el.dataset.pfbSection = String(live_sections().length - 1);
		append_section_el(el);
	});
}

// ── Drop new fields/sections dragged from the left panel ────
// The panel forwards synthetic dragover/drop events at viewport coordinates,
// with the dragged payload exposed via the store.
let palette_indicator = null;
let palette_target = null;

function on_palette_drag_over(e) {
	const payload = store.drag_payload.value;
	if (!payload) return;
	e.preventDefault();
	if (!palette_indicator) {
		palette_indicator = document.createElement("div");
		palette_indicator.className = "pfb-drop-indicator";
		root_el.appendChild(palette_indicator);
	}
	const under = e.target instanceof Element ? e.target : null;

	if (payload.kind === "section") {
		const section_el = under?.closest("[data-pfb-section]");
		palette_target = { section_idx: section_el ? +section_el.dataset.pfbSection : null };
		const target_el = section_el || root_el.querySelector(".pfb-pages");
		if (target_el) {
			const rect = local_rect(target_el.getBoundingClientRect());
			Object.assign(palette_indicator.style, {
				display: "block",
				top: `${rect.bottom - 1}px`,
				left: `${rect.left}px`,
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
		const local = local_rect(rect);
		Object.assign(palette_indicator.style, {
			display: "block",
			top: `${(before ? local.top : local.bottom) - 1}px`,
			left: `${local.left}px`,
			width: `${local.width}px`,
		});
	} else if (col_el) {
		palette_target = { col_path: col_el.dataset.pfbCol, append: true };
		const local = local_rect(col_el.getBoundingClientRect());
		Object.assign(palette_indicator.style, {
			display: "block",
			top: `${local.bottom - 1}px`,
			left: `${local.left}px`,
			width: `${local.width}px`,
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
		optimistic(() => {
			const el = synthetic_section_el(payload.section);
			shift_section_indices(idx, 1);
			el.dataset.pfbSection = String(idx);
			const anchor =
				target?.section_idx != null &&
				master_el(`[data-pfb-section="${target.section_idx}"]`);
			anchor ? anchor.after(el) : append_section_el(el);
		});
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

	optimistic(() => {
		const col_el = master_el(`[data-pfb-col="${target.col_path}"]`);
		if (!col_el) return;
		const el = synthetic_field_el(payload.df, col_el);
		const anchor_el =
			!target.append &&
			target.field_path &&
			master_el(`[data-pfb-path="${target.field_path}"]`);
		if (anchor_el) {
			target.before ? anchor_el.before(el) : anchor_el.after(el);
		} else {
			col_el.appendChild(el);
		}
	});
}

// ── Inline label editing ────────────────────────────────────
function on_dblclick(e) {
	const field_el = e.target.closest("[data-pfb-path]");
	const field_label = field_el?.querySelector(".label");
	const section_el = e.target.closest("[data-pfb-section]");
	const section_label = e.target.closest(".section-label");

	let el, commit;
	if (field_label && field_label.contains(e.target)) {
		const { field } = resolve_path(field_el.dataset.pfbPath);
		if (!field) return;
		el = field_label;
		const path = field_el.dataset.pfbPath;
		commit = (text) => {
			if (text === field.label) return;
			field.label = text;
			const m = master_el(`[data-pfb-path="${path}"]`)?.querySelector(".label");
			if (m) m.textContent = text;
			paginate();
		};
	} else if (section_label && section_el) {
		const section = live_sections()[+section_el.dataset.pfbSection];
		if (!section) return;
		el = section_label;
		const idx = section_el.dataset.pfbSection;
		commit = (text) => {
			if (text === section.label) return;
			section.label = text;
			const m = master_el(`[data-pfb-section="${idx}"]`)?.querySelector(".section-label");
			if (m) m.textContent = text;
			paginate();
		};
	} else {
		return;
	}

	e.preventDefault();
	const original = el.textContent;
	el.setAttribute("contenteditable", "plaintext-only");
	el.focus();
	window.getSelection()?.selectAllChildren(el);

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

function on_document_keydown(e) {
	if (!is_active) return;
	if (e.key !== "Delete" && e.key !== "Backspace") return;
	if (!store.selected_field.value && !store.selected_section.value) return;
	const ae = document.activeElement;
	if (ae && (ae.tagName === "INPUT" || ae.tagName === "TEXTAREA" || ae.isContentEditable)) {
		return;
	}
	if (shadow?.activeElement?.isContentEditable) return;
	e.preventDefault();
	remove_selected();
}

function place_delete_chip(el, title) {
	const chip = document.createElement("button");
	chip.className = "pfb-del-chip";
	chip.title = title;
	const symbol = document.getElementById("icon-x");
	if (symbol) {
		const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
		svg.setAttribute("viewBox", symbol.getAttribute("viewBox") || "0 0 24 24");
		svg.innerHTML = symbol.innerHTML;
		chip.appendChild(svg);
	} else {
		chip.textContent = "×";
	}
	chip.addEventListener("click", (e) => {
		e.stopPropagation();
		remove_selected();
	});
	const rect = local_rect(el.getBoundingClientRect());
	chip.style.top = `${rect.top + 2}px`;
	chip.style.left = `${rect.right - 24}px`;
	root_el.appendChild(chip);
}

function update_highlight() {
	if (!root_el) return;
	for (const el of root_el.querySelectorAll(".pfb-live-selected, .pfb-live-selected-section")) {
		el.classList.remove("pfb-live-selected", "pfb-live-selected-section");
	}
	for (const chip of root_el.querySelectorAll(".pfb-del-chip")) chip.remove();
	const mark = (selector, cls) => {
		const els = [...root_el.querySelectorAll(selector)];
		for (const el of els) el.classList.add(cls);
		return els[0];
	};
	const field = store.selected_field.value;
	if (field) {
		const path = path_of(field);
		const el = path && mark(`[data-pfb-path="${path}"]`, "pfb-live-selected");
		if (el) place_delete_chip(el, __("Remove field"));
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
			if (el) place_delete_chip(el, __("Remove section"));
		}
	}
}

watch(() => store.layout.value, debounced_render, { deep: true });
watch(() => store.print_format.value, debounced_render, { deep: true });
watch(() => store.preview_doc_name.value, render);
watch(() => store.letterhead.value?.name, render);
watch([() => store.selected_field.value, () => store.selected_section.value], update_highlight);

onMounted(() => {
	document.addEventListener("keydown", on_document_keydown);
	window.addEventListener("resize", update_highlight);
});

onUnmounted(() => {
	document.removeEventListener("keydown", on_document_keydown);
	window.removeEventListener("resize", update_highlight);
});

onActivated(() => {
	is_active = true;
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

.live-canvas-host {
	flex: 1;
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
