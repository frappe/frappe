<template>
	<div class="pfb-preview-dock">
		<div class="pfb-preview-head">
			<span class="pfb-preview-title">{{ __("Preview") }}</span>
			<select class="pfb-preview-type" v-model="type">
				<option value="HTML">{{ __("HTML") }}</option>
				<option value="PDF">{{ __("PDF") }}</option>
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
		</div>

		<div v-if="type === 'PDF' && store.dirty" class="pfb-preview-note">
			{{ __("The PDF renders the saved format. Save to see recent edits.") }}
		</div>

		<div v-if="!docname" class="pfb-preview-empty">
			{{ __("Pick a record in the toolbar above to preview it.") }}
		</div>
		<div v-else-if="!preview_loaded" class="pfb-preview-empty">
			{{ __("Generating preview...") }}
		</div>
		<iframe
			ref="iframe"
			:src="type === 'PDF' ? url : undefined"
			v-show="docname && preview_loaded"
			class="pfb-preview-iframe"
			@load="type === 'PDF' && (preview_loaded = true)"
		></iframe>
	</div>
</template>

<script setup>
import { useStore } from "../stores";
import { ref, computed, onMounted, watch } from "vue";

let { print_format, layout, store } = useStore();

let type = ref("HTML");
let preview_loaded = ref(false);
let iframe = ref(null);
let render_seq = 0;

// the canvas toolbar owns the record picker; the dock just follows it
let docname = computed(() => store.value.preview_doc_name);

let doctype = computed(() => print_format.value.doc_type);

let url = computed(() => {
	if (!docname.value) return null;
	let params = new URLSearchParams();
	params.append("doctype", doctype.value);
	params.append("name", docname.value);
	params.append("print_format", print_format.value.name);
	if (store.value.letterhead) {
		params.append("letterhead", store.value.letterhead.name);
	}
	let _url =
		type.value == "PDF"
			? `/api/method/frappe.utils.print_format_generator.download_pdf`
			: "/printpreview";
	return `${_url}?${params.toString()}`;
});

function write_iframe(html) {
	let cd = iframe.value?.contentDocument;
	if (!cd) return;
	cd.open();
	cd.write(html);
	cd.close();
}

function render() {
	if (!docname.value) return;
	// PDF is served straight into the iframe via src, and costs a Chromium render
	if (type.value === "PDF") return;
	preview_loaded.value = false;
	let seq = ++render_seq;
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
		})
		.catch(() => {
			if (seq !== render_seq) return;
			write_iframe(`<p style="padding:1rem">${__("Could not generate preview.")}</p>`);
			preview_loaded.value = true;
		});
}

function refresh() {
	if (type.value === "PDF") {
		preview_loaded.value = false;
		iframe.value?.contentWindow.location.reload();
	} else {
		render();
	}
}

// Editing beside the preview is the whole point of the dock, but every render is a
// server round trip — so coalesce bursts of edits, and never auto-fire a PDF render.
const auto_render = frappe.utils.debounce(() => {
	if (type.value === "HTML") render();
}, 1000);

watch(() => layout.value, auto_render, { deep: true });
watch([docname, type], render);

onMounted(render);
</script>

<style scoped>
.pfb-preview-dock {
	display: flex;
	flex-direction: column;
	width: 420px;
	flex-shrink: 0;
	border-left: 1px solid var(--border-color);
	background: var(--fg-color);
	overflow: hidden;
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

.pfb-preview-note,
.pfb-preview-empty {
	padding: 10px 12px;
	font-size: var(--text-sm);
	color: var(--text-muted);
}

.pfb-preview-note {
	border-bottom: 1px solid var(--border-color);
}

.pfb-preview-iframe {
	flex: 1;
	width: 100%;
	border: none;
	min-height: 0;
}
</style>
