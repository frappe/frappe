<template>
	<Teleport to="body">
		<div class="pfb-preview-backdrop" @click.self="$emit('close')">
			<div class="pfb-preview-modal">
				<div v-if="!docname" class="pfb-preview-empty">
					{{ __("Pick a record in the toolbar above to preview it.") }}
				</div>
				<div v-else-if="unprintable_reason === 'cancelled'" class="pfb-preview-empty">
					{{ __("This document is cancelled and cannot be printed.") }}
				</div>
				<div v-else-if="unprintable_reason === 'draft'" class="pfb-preview-empty">
					{{ __("This document is a draft and cannot be printed.") }}
				</div>
				<div v-else-if="!preview_loaded" class="pfb-preview-empty">
					<span class="pfb-preview-spinner" aria-hidden="true"></span>
					<span>{{ __("Generating preview…") }}</span>
				</div>
				<iframe
					v-show="docname && preview_loaded && !unprintable_reason"
					ref="iframe"
					:src="pdf_url"
					class="pfb-preview-iframe"
				></iframe>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { useStore } from "../stores";
import { ref, computed, onMounted, onUnmounted, watch } from "vue";

const emit = defineEmits(["close"]);

let { print_format, layout, store } = useStore();

let preview_loaded = ref(false);
let iframe = ref(null);
let pdf_url = ref(null);
let render_seq = 0;

let docname = computed(() => store.value.preview_doc_name);
let doctype = computed(() => print_format.value.doc_type);

// draft/cancelled documents aren't printable unless Print Settings allows it (see
// printview.validate_print_for_docstatus) — asking the server for a preview would
// only bounce back a permission error, so skip the round trip and say so directly.
let preview_doc_docstatus = computed(() =>
	store.value.preview_doc?.name === docname.value ? store.value.preview_doc?.docstatus : null
);
let unprintable_reason = computed(() => {
	const docstatus = preview_doc_docstatus.value;
	if (docstatus == null || frappe.model.can_print_docstatus(doctype.value, docstatus))
		return null;
	return docstatus === 2 ? "cancelled" : "draft";
});

// Chromium decides where a page actually breaks — automatic breaks depend on
// laid-out heights, keep-together and table splitting — so the paged view asks
// the print renderer for a real PDF of the unsaved format.
async function render() {
	let seq = ++render_seq;
	if (!docname.value) return;
	if (unprintable_reason.value) {
		set_pdf_url(null);
		preview_loaded.value = true;
		return;
	}
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
		// keep the browser's own PDF toolbar — page nav, zoom and download come free
		set_pdf_url(URL.createObjectURL(blob) + "#view=FitH");
	} catch (e) {
		if (seq !== render_seq) return;
		set_pdf_url(null);
		frappe.show_alert({ message: __("Could not render the preview"), indicator: "red" });
	}
	preview_loaded.value = true;
}

function set_pdf_url(next) {
	if (pdf_url.value) URL.revokeObjectURL(pdf_url.value.split("#")[0]);
	pdf_url.value = next;
}

// docstatus arrives async and can resolve after docname already triggered a render
watch([docname, () => store.value.preview_doc?.docstatus], render, { flush: "post" });

function on_keydown(e) {
	if (e.key !== "Escape") return;
	// an open dialog owns Escape — one keypress dismisses one layer
	if (window.cur_dialog?.display) return;
	emit("close");
}

onMounted(() => {
	render();
	window.addEventListener("keydown", on_keydown);
});
onUnmounted(() => {
	set_pdf_url(null);
	window.removeEventListener("keydown", on_keydown);
});
</script>

<style scoped>
.pfb-preview-backdrop {
	position: fixed;
	inset: 0;
	z-index: 1035;
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 24px;
	background: rgba(0, 0, 0, 0.6);
}

.pfb-preview-modal {
	position: relative;
	display: flex;
	flex-direction: column;
	width: min(1000px, 94vw);
	height: 94vh;
	/* no chrome of its own — the PDF viewer fills the frame edge to edge */
	background: transparent;
	overflow: hidden;
}

/* opaque while there's no PDF yet — the modal itself is transparent, so without
   this the canvas behind shows through and the message looks like a glitch */
.pfb-preview-empty {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 8px;
	background: var(--fg-color);
	border-radius: var(--radius-lg, 8px);
	font-size: var(--text-sm);
	color: var(--text-color);
}

.pfb-preview-spinner {
	width: 20px;
	height: 20px;
	border: 2px solid var(--gray-300);
	border-top-color: var(--gray-600);
	border-radius: 50%;
	animation: pfb-preview-spin 0.7s linear infinite;
}

@keyframes pfb-preview-spin {
	to {
		transform: rotate(360deg);
	}
}

.pfb-preview-iframe {
	flex: 1;
	width: 100%;
	min-height: 0;
	border: none;
	border-radius: var(--radius-lg, 8px);
	display: block;
}
</style>
