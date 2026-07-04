<template>
	<div class="live-canvas">
		<div v-if="error" class="live-canvas-error">{{ error }}</div>
		<div v-else-if="!loaded" class="live-canvas-loading">{{ __("Rendering...") }}</div>
		<iframe v-show="loaded && !error" ref="frame" class="live-canvas-frame"></iframe>
	</div>
</template>

<script setup>
import { serialize_layout } from "../../utils";
import { ref, inject, watch, onActivated, onDeactivated } from "vue";

let store = inject("$store");
let frame = ref(null);
let loaded = ref(false);
let error = ref(null);
let render_seq = 0;
let is_active = false;
let last_payload = null;

const INTERACTION_CSS = `
	[data-pfb-path] { cursor: pointer; }
	[data-pfb-path]:hover { outline: 1px dashed #94b8ff; outline-offset: 1px; }
	[data-pfb-section]:hover, [data-pfb-zone]:hover { outline: 1px dashed #c7d7fe; outline-offset: 3px; }
	.pfb-live-selected { outline: 2px solid #4d7cfe !important; outline-offset: 1px; }
	.pfb-live-selected-section { outline: 2px solid #94b8ff !important; outline-offset: 3px; }
	.pfb-dragging { opacity: 0.4; }
	.pfb-drop-indicator {
		position: absolute;
		height: 2px;
		background: #4d7cfe;
		border-radius: 1px;
		pointer-events: none;
		z-index: 9999;
		display: none;
	}
	.label[contenteditable], .section-label[contenteditable] {
		outline: 1px solid #4d7cfe;
		outline-offset: 1px;
		cursor: text;
		border-radius: 2px;
	}
	body { position: relative; }
	.pfb-page-guides { position: absolute; inset: 0; pointer-events: none; z-index: 9998; }
	.pfb-page-line { position: absolute; left: 0; right: 0; border-top: 1px dashed #94a3b8; }
	.pfb-page-chip {
		position: absolute;
		right: 6px;
		transform: translateY(-50%);
		font: 500 10px/1.6 -apple-system, sans-serif;
		color: #475569;
		background: #e2e8f0;
		padding: 0 7px;
		border-radius: 8px;
		white-space: nowrap;
	}
	.pfb-margin-guide { position: absolute; top: 0; bottom: 0; border-left: 1px dashed #dbeafe; }
`;

const PAGE_HEIGHTS_MM = { A4: 297, Letter: 279.4 };

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
	const payload = JSON.stringify(args);
	if (payload === last_payload && loaded.value) return;
	const seq = ++render_seq;
	frappe
		.call("frappe.utils.print_format_generator.render_preview", args)
		.then((r) => {
			if (seq !== render_seq) return;
			error.value = null;
			last_payload = payload;
			write_document(r.message);
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
	doc.write(html.replace("</head>", `<style>${INTERACTION_CSS}</style></head>`));
	doc.close();
	doc.addEventListener("click", handle_click);
	doc.addEventListener("keydown", forward_keydown);
	doc.addEventListener("pointerdown", on_pointer_down);
	doc.addEventListener("dblclick", on_dblclick);
	draw_page_guides();
	frame.value.contentWindow?.addEventListener("load", draw_page_guides);
	frame.value.contentWindow?.scrollTo(0, scroll_y);
	loaded.value = true;
	update_highlight();
}

// ── Page boundary guides ────────────────────────────────────
function draw_page_guides() {
	const doc = frame.value?.contentDocument;
	const body = doc?.body;
	if (!body) return;
	doc.querySelector(".pfb-page-guides")?.remove();

	const probe = doc.createElement("div");
	probe.style.cssText = "position:absolute;height:100mm;width:0;visibility:hidden";
	body.appendChild(probe);
	const px_per_mm = probe.getBoundingClientRect().height / 100;
	probe.remove();
	if (!px_per_mm) return;

	const page_px = (PAGE_HEIGHTS_MM[body.dataset.pageSize] || 297) * px_per_mm;
	const margin_top = (parseFloat(body.dataset.marginTop) || 0) * px_per_mm;
	const margin_bottom = (parseFloat(body.dataset.marginBottom) || 0) * px_per_mm;
	const margin_left = (parseFloat(body.dataset.marginLeft) || 0) * px_per_mm;
	const margin_right = (parseFloat(body.dataset.marginRight) || 0) * px_per_mm;
	const usable = page_px - margin_top - margin_bottom;
	if (usable <= 0) return;

	const layer = doc.createElement("div");
	layer.className = "pfb-page-guides";

	for (const x of [margin_left, body.clientWidth - margin_right]) {
		const guide = doc.createElement("div");
		guide.className = "pfb-margin-guide";
		guide.style.left = `${x}px`;
		layer.appendChild(guide);
	}

	const content_bottom = body.scrollHeight - margin_bottom;
	const forced = [...doc.querySelectorAll(".page-break")]
		.map((el) => {
			const rect = el.getBoundingClientRect();
			return rect.bottom + frame.value.contentWindow.scrollY;
		})
		.sort((a, b) => a - b);

	let cursor = margin_top;
	let page = 1;
	const add_boundary = (y, label) => {
		const line = doc.createElement("div");
		line.className = "pfb-page-line";
		line.style.top = `${y}px`;
		const chip = doc.createElement("div");
		chip.className = "pfb-page-chip";
		chip.style.top = `${y}px`;
		chip.textContent = label;
		layer.appendChild(line);
		layer.appendChild(chip);
	};

	while (cursor + usable < content_bottom) {
		const next_forced = forced.find((y) => y > cursor && y <= cursor + usable);
		const boundary = next_forced ?? cursor + usable;
		page += 1;
		add_boundary(
			boundary,
			next_forced ? __("Page {0} · break", [page]) : __("Page {0}", [page])
		);
		cursor = boundary;
	}

	body.appendChild(layer);
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
	} else {
		store.selected_field.value = null;
		store.selected_section.value = null;
	}
	update_highlight();
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
	document.dispatchEvent(
		new KeyboardEvent("keydown", {
			key: e.key,
			ctrlKey: e.ctrlKey,
			metaKey: e.metaKey,
			shiftKey: e.shiftKey,
		})
	);
}

function update_highlight() {
	const doc = frame.value?.contentDocument;
	if (!doc) return;
	for (const el of doc.querySelectorAll(".pfb-live-selected, .pfb-live-selected-section")) {
		el.classList.remove("pfb-live-selected", "pfb-live-selected-section");
	}
	const field = store.selected_field.value;
	if (field) {
		const path = path_of(field);
		const el = path && doc.querySelector(`[data-pfb-path="${path}"]`);
		el?.classList.add("pfb-live-selected");
		return;
	}
	const section = store.selected_section.value;
	if (section) {
		if (section === store.layout.value.header || section === store.layout.value.footer) {
			const zone = section === store.layout.value.header ? "header" : "footer";
			doc.querySelector(`[data-pfb-zone="${zone}"]`)?.classList.add(
				"pfb-live-selected-section"
			);
			return;
		}
		const idx = live_sections().indexOf(section);
		if (idx !== -1) {
			doc.querySelector(`[data-pfb-section="${idx}"]`)?.classList.add(
				"pfb-live-selected-section"
			);
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
.live-canvas-error {
	padding: 2rem;
	text-align: center;
	color: var(--text-muted);
	font-size: var(--text-sm);
}

.live-canvas-error {
	color: var(--red-500);
}
</style>
