<template>
	<div class="pfb-preview-dock" :style="{ width: dock_width + 'px' }">
		<div
			class="pfb-preview-resizer"
			:title="__('Drag to resize')"
			@pointerdown.prevent="start_resize"
		></div>
		<div class="pfb-preview-head">
			<span class="pfb-preview-title">{{ __("Preview") }}</span>
			<select class="pfb-preview-type" v-model="type">
				<option value="HTML">{{ __("Flow") }}</option>
				<option value="PDF">{{ __("Pages") }}</option>
			</select>
			<button
				class="pfb-preview-btn"
				:title="__('Refresh')"
				@click="refresh"
				v-html="frappe.utils.icon('refresh-cw', 'xs')"
			></button>
			<a
				v-if="url"
				class="pfb-preview-btn"
				target="_blank"
				:href="url"
				:title="__('Open in a new tab')"
				v-html="frappe.utils.icon('external-link', 'xs')"
			></a>
			<button
				class="pfb-preview-btn"
				:title="__('Close preview')"
				:aria-label="__('Close preview')"
				@click="$emit('close')"
				v-html="frappe.utils.icon('x', 'xs')"
			></button>
		</div>

		<div v-if="!docname" class="pfb-preview-empty">
			{{ __("Pick a record in the toolbar above to preview it.") }}
		</div>
		<div v-else-if="!preview_loaded" class="pfb-preview-empty">
			{{ __("Generating preview...") }}
		</div>
		<div ref="viewport" class="pfb-preview-viewport" v-show="docname && preview_loaded">
			<!-- the page renders at its true width and is scaled down to fit the rail -->
			<div class="pfb-preview-stage" :style="stage_style">
				<iframe
					ref="iframe"
					:key="type"
					:src="type === 'PDF' ? pdf_url : undefined"
					:scrolling="type === 'PDF' ? 'auto' : 'no'"
					class="pfb-preview-iframe"
					:style="frame_style"
				></iframe>
			</div>
		</div>
	</div>
</template>

<script setup>
import { useStore } from "../stores";
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from "vue";

defineEmits(["close"]);

let { print_format, layout, store } = useStore();

const DOCK_KEY = "pfb_preview_width";
const DOCK_MIN = 320;
const DOCK_MAX = 1100;

let type = ref("HTML");
let preview_loaded = ref(false);
let iframe = ref(null);
let viewport = ref(null);
let pdf_url = ref(null);
let render_seq = 0;

let dock_width = ref(clamp_width(parseInt(localStorage.getItem(DOCK_KEY)) || 520));
let page = ref({ w: 0, h: 0 });
let scale = ref(1);

function clamp_width(w) {
	return Math.min(DOCK_MAX, Math.max(DOCK_MIN, w));
}

// The PDF viewer does its own fitting; only the HTML render needs scaling.
let is_scaled = computed(() => type.value === "HTML" && page.value.w > 0);

let stage_style = computed(() =>
	is_scaled.value
		? {
				width: `${page.value.w * scale.value}px`,
				height: `${page.value.h * scale.value}px`,
		  }
		: { flex: "1", width: "100%" }
);

let frame_style = computed(() =>
	is_scaled.value
		? {
				width: `${page.value.w}px`,
				height: `${page.value.h}px`,
				transform: `scale(${scale.value})`,
				transformOrigin: "top left",
		  }
		: { width: "100%", height: "100%" }
);

function fit_preview() {
	if (type.value === "PDF") {
		page.value = { w: 0, h: 0 };
		return;
	}
	const cd = iframe.value?.contentDocument;
	const box = viewport.value;
	if (!cd?.documentElement || !box) return;
	const w = cd.documentElement.scrollWidth;
	const h = cd.documentElement.scrollHeight;
	if (!w || !h) return;
	// re-measuring feeds back through the body observer, so ignore sub-pixel noise
	if (Math.abs(w - page.value.w) > 1 || Math.abs(h - page.value.h) > 1) {
		page.value = { w, h };
	}
	// never blow a narrow page up past its natural size. The epsilon matters: the
	// viewport's own scrollbar appearing changes clientWidth, which would otherwise
	// rescale, hide the scrollbar, and oscillate.
	const next = Math.min(1, (box.clientWidth - 16) / w);
	if (Math.abs(next - scale.value) > 0.01) scale.value = next;
}

let resize_observer = null;
let frame_observer = null;

// Images and webfonts land after the first measure, so the page grows past the
// height we sized the frame to — and the frame sprouts its own scrollbar next to
// the dock's. Track the rendered body instead of measuring once.
function observe_frame_body() {
	frame_observer?.disconnect();
	const body = iframe.value?.contentDocument?.body;
	if (!body) return;
	frame_observer = new ResizeObserver(fit_preview);
	frame_observer.observe(body);
}

// Pointer capture, not document listeners: the drag crosses the preview iframe,
// and a mouseup over an iframe is delivered to that frame's document, never ours —
// so the drag would carry on with the button released.
function start_resize(e) {
	const handle = e.currentTarget;
	const start_x = e.clientX;
	const start_w = dock_width.value;
	handle.setPointerCapture(e.pointerId);

	const on_move = (ev) => {
		// the dock is on the right, so dragging left widens it
		dock_width.value = clamp_width(start_w + (start_x - ev.clientX));
	};
	const on_up = () => {
		handle.removeEventListener("pointermove", on_move);
		handle.removeEventListener("pointerup", on_up);
		handle.removeEventListener("pointercancel", on_up);
		localStorage.setItem(DOCK_KEY, dock_width.value);
	};
	handle.addEventListener("pointermove", on_move);
	handle.addEventListener("pointerup", on_up);
	handle.addEventListener("pointercancel", on_up);
}

// the canvas toolbar owns the record picker; the dock just follows it
let docname = computed(() => store.value.preview_doc_name);

let doctype = computed(() => print_format.value.doc_type);

let url = computed(() => {
	if (!docname.value) return null;
	// the paged view is a blob of the unsaved format — opening the saved one
	// in a new tab would quietly show something else
	if (type.value === "PDF") return pdf_url.value;
	let params = new URLSearchParams();
	params.append("doctype", doctype.value);
	params.append("name", docname.value);
	params.append("print_format", print_format.value.name);
	if (store.value.letterhead) {
		params.append("letterhead", store.value.letterhead.name);
	}
	return `/printpreview?${params.toString()}`;
});

function write_iframe(html) {
	let cd = iframe.value?.contentDocument;
	if (!cd) return;
	cd.open();
	cd.write(html);
	cd.close();
}

// Chromium decides where a page actually breaks — automatic breaks depend on
// laid-out heights, keep-together and table splitting, none of which the browser
// can work out from the flowed HTML. So the paged view asks the print renderer.
async function render_pages(seq) {
	preview_loaded.value = false;
	const params = {
		print_format: store.value.get_preview_format_doc(),
		doctype: doctype.value,
		name: docname.value,
	};
	if (store.value.letterhead) {
		params.letterhead = store.value.letterhead.name;
	}
	try {
		const res = await fetch(
			"/api/method/frappe.utils.print_format_generator.download_builder_preview_pdf",
			{
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"X-Frappe-CSRF-Token": frappe.csrf_token,
				},
				body: JSON.stringify(params),
			}
		);
		if (!res.ok) throw new Error(res.statusText);
		const blob = await res.blob();
		if (seq !== render_seq) return;
		set_pdf_url(URL.createObjectURL(blob));
	} catch (e) {
		if (seq !== render_seq) return;
		set_pdf_url(null);
		frappe.show_alert({ message: __("Could not render the paged preview"), indicator: "red" });
	}
	preview_loaded.value = true;
}

function set_pdf_url(next) {
	if (pdf_url.value) URL.revokeObjectURL(pdf_url.value);
	pdf_url.value = next;
}

function render() {
	// bump first: clearing the record must invalidate a response already in flight
	let seq = ++render_seq;
	if (!docname.value) return;
	if (type.value === "PDF") return render_pages(seq);
	preview_loaded.value = false;
	let params = {
		print_format: store.value.get_preview_format_doc(),
		doctype: doctype.value,
		name: docname.value,
	};
	if (store.value.letterhead) {
		params.letterhead = store.value.letterhead.name;
	}
	return frappe
		.call("frappe.utils.print_format_generator.render_builder_preview", params)
		.then((r) => {
			if (seq !== render_seq) return;
			write_iframe(r.message || "");
			preview_loaded.value = true;
			after_write();
		})
		.catch(() => {
			if (seq !== render_seq) return;
			write_iframe(`<p style="padding:1rem">${__("Could not generate preview.")}</p>`);
			preview_loaded.value = true;
			after_write();
		});
}

// every write replaces the document, so re-measure and re-observe the new body
function after_write() {
	nextTick(() => {
		fit_preview();
		observe_frame_body();
	});
}

function refresh() {
	render();
}

// Editing beside the preview is the whole point of the dock, but every render is a
// server round trip — so coalesce bursts of edits, and never auto-fire a PDF render.
const auto_render = frappe.utils.debounce(() => {
	if (type.value === "HTML") render();
}, 1000);

watch(() => layout.value, auto_render, { deep: true });
watch([docname, type], render, { flush: "post" });

onMounted(() => {
	render();
	resize_observer = new ResizeObserver(fit_preview);
	if (viewport.value) resize_observer.observe(viewport.value);
});

onUnmounted(() => {
	auto_render.cancel();
	resize_observer?.disconnect();
	frame_observer?.disconnect();
	set_pdf_url(null);
});
</script>

<style scoped>
.pfb-preview-dock {
	position: relative;
	display: flex;
	flex-direction: column;
	flex-shrink: 0;
	/* pin to the viewport like the inspector, so the dock scrolls and the page doesn't */
	height: calc(100vh - var(--pfb-chrome-offset, 95px));
	border-left: 1px solid var(--border-color);
	background: var(--fg-color);
	overflow: hidden;
}

.pfb-preview-resizer {
	position: absolute;
	top: 0;
	left: -3px;
	width: 6px;
	height: 100%;
	cursor: col-resize;
	z-index: 1;
}

.pfb-preview-resizer:hover {
	background: var(--gray-200);
}

.pfb-preview-head {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 8px 10px;
	border-bottom: 1px solid var(--border-color);
	flex-shrink: 0;
}

.pfb-preview-title {
	flex: 1;
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
}

.pfb-preview-type {
	border: 1px solid var(--border-color);
	background: var(--control-bg);
	border-radius: var(--radius);
	font-size: var(--text-xs);
	padding: 2px 4px;
	color: var(--text-color);
}

.pfb-preview-type:focus-visible {
	outline: none;
	border-color: var(--gray-500);
	box-shadow: 0 0 0 2px var(--gray-200);
}

.pfb-preview-btn {
	display: flex;
	align-items: center;
	padding: 4px;
	border: none;
	background: transparent;
	border-radius: var(--radius);
	color: var(--text-muted);
	cursor: pointer;
}

.pfb-preview-btn:hover {
	background: var(--gray-100);
	color: var(--text-color);
}

.pfb-preview-empty {
	padding: 10px 12px;
	font-size: var(--text-sm);
	color: var(--text-muted);
}

.pfb-preview-viewport {
	flex: 1;
	min-height: 0;
	overflow: auto;
	padding: 8px;
	display: flex;
	justify-content: center;
	background: var(--gray-100);
}

.pfb-preview-stage {
	position: relative;
	flex-shrink: 0;
	background: white;
	box-shadow: var(--shadow-sm);
}

.pfb-preview-iframe {
	border: none;
	display: block;
}
</style>
