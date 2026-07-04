<template>
	<div class="live-canvas">
		<div v-if="error" class="live-canvas-error">{{ error }}</div>
		<div v-else-if="!loaded" class="live-canvas-loading">{{ __("Rendering...") }}</div>
		<iframe v-show="loaded && !error" ref="frame" class="live-canvas-frame"></iframe>
	</div>
</template>

<script setup>
import { serialize_layout } from "../../utils";
import { ref, inject, watch, onMounted } from "vue";

let store = inject("$store");
let frame = ref(null);
let loaded = ref(false);
let error = ref(null);
let render_seq = 0;

const INTERACTION_CSS = `
	[data-pfb-path] { cursor: pointer; }
	[data-pfb-path]:hover { outline: 1px dashed #94b8ff; outline-offset: 1px; }
	[data-pfb-section]:hover, [data-pfb-zone]:hover { outline: 1px dashed #c7d7fe; outline-offset: 3px; }
	.pfb-live-selected { outline: 2px solid #4d7cfe !important; outline-offset: 1px; }
	.pfb-live-selected-section { outline: 2px solid #94b8ff !important; outline-offset: 3px; }
`;

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
	if (!store.preview_doc_name.value) return;
	const seq = ++render_seq;
	frappe
		.call("frappe.utils.print_format_generator.render_preview", {
			doctype: store.print_format.value.doc_type,
			name: store.preview_doc_name.value,
			print_format: store.print_format.value.name,
			format_data: serialized_format_data(),
			letterhead: store.letterhead.value?.name || null,
			settings: JSON.stringify(preview_settings()),
		})
		.then((r) => {
			if (seq !== render_seq) return;
			error.value = null;
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
	frame.value.contentWindow?.scrollTo(0, scroll_y);
	loaded.value = true;
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

onMounted(render);
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
