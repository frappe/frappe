<template>
	<Teleport to="body">
		<div class="pfb-preview-backdrop" @click.self="$emit('close')">
			<div
				ref="modal"
				class="pfb-preview-modal"
				:class="{ 'pfb-preview-modal--compare': compare }"
				tabindex="-1"
				@click.self="$emit('close')"
			>
				<div v-if="!docname" class="pfb-preview-empty">
					{{ __("Pick a record in the toolbar above to preview it.") }}
				</div>
				<div v-else-if="unprintable_reason === 'cancelled'" class="pfb-preview-empty">
					{{ __("This document is cancelled and cannot be printed.") }}
				</div>
				<div v-else-if="unprintable_reason === 'draft'" class="pfb-preview-empty">
					{{ __("This document is a draft and cannot be printed.") }}
				</div>
				<template v-else-if="compare">
					<button
						class="es-button pfb-preview-close"
						data-variant="ghost"
						data-icon-button="true"
						:title="__('Close')"
						@click="$emit('close')"
						v-html="frappe.utils.icon('x', 'sm')"
					></button>
					<div class="pfb-preview-panes">
						<div class="pfb-preview-pane">
							<div class="pfb-preview-caption">
								{{ __("Saved version, what prints today") }}
							</div>
							<div v-if="before_note" class="pfb-preview-empty">
								{{ before_note }}
							</div>
							<div v-else-if="!before_url" class="pfb-preview-empty">
								<span class="pfb-preview-spinner" aria-hidden="true"></span>
								<span>{{ __("Rendering the saved version…") }}</span>
							</div>
							<iframe v-else :src="before_url" class="pfb-preview-iframe"></iframe>
						</div>
						<div class="pfb-preview-pane">
							<div class="pfb-preview-caption">
								{{ __("Your draft, not applied yet") }}
							</div>
							<div v-if="after_note" class="pfb-preview-empty">{{ after_note }}</div>
							<div v-else-if="!pdf_url" class="pfb-preview-empty">
								<span class="pfb-preview-spinner" aria-hidden="true"></span>
								<span>{{ __("Rendering your draft…") }}</span>
							</div>
							<iframe v-else :src="pdf_url" class="pfb-preview-iframe"></iframe>
						</div>
					</div>
				</template>
				<div v-else-if="after_note" class="pfb-preview-empty">{{ after_note }}</div>
				<div v-else-if="!pdf_url" class="pfb-preview-empty">
					<span class="pfb-preview-spinner" aria-hidden="true"></span>
					<span>{{ __("Generating preview…") }}</span>
				</div>
				<iframe v-else ref="iframe" :src="pdf_url" class="pfb-preview-iframe"></iframe>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { useStore } from "../stores";
import { ref, computed, onMounted, onUnmounted, watch } from "vue";
import { describe_draft_changes } from "../composables/useDraftDiff";

const props = defineProps({ compare: { type: Boolean, default: false } });
const emit = defineEmits(["close"]);

let { print_format, layout, store } = useStore();

let iframe = ref(null);
let modal = ref(null);
let pdf_url = ref(null);
let before_url = ref(null);
let before_note = ref("");
let after_note = ref("");
let render_seq = 0;
let render_abort = null;

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
async function render_pdf(format_doc) {
	const params = { print_format: format_doc, doctype: doctype.value, name: docname.value };
	const layout_lh = frappe.utils.parse_json(format_doc.format_data)?.letter_head;
	if (layout_lh || store.value.letterhead) {
		params.letterhead = layout_lh || store.value.letterhead.name;
	}
	const res = await fetch(
		"/api/method/frappe.utils.print_format_generator.download_builder_preview_pdf",
		{
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": frappe.csrf_token,
			},
			body: JSON.stringify(params),
			signal: render_abort.signal,
		}
	);
	if (!res.ok) {
		let message = "";
		try {
			const data = await res.json();
			message =
				JSON.parse(JSON.parse(data._server_messages || "[]")[0] || "{}").message || "";
		} catch {}
		throw new Error(strip_html(message));
	}
	return URL.createObjectURL(await res.blob()) + "#view=FitH";
}

async function render_saved_pdf() {
	const params = new URLSearchParams({
		doctype: doctype.value,
		name: docname.value,
		format: print_format.value.name,
	});
	const res = await fetch("/api/method/frappe.utils.print_format.download_pdf?" + params, {
		headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
		signal: render_abort.signal,
	});
	if (!res.ok) throw new Error(__("Could not render the saved version"));
	return URL.createObjectURL(await res.blob()) + "#view=FitH";
}

async function render() {
	let seq = ++render_seq;
	render_abort?.abort();
	render_abort = new AbortController();
	if (!docname.value) return;
	if (unprintable_reason.value) {
		set_pdf_url(null);
		set_before_url(null);
		return;
	}
	before_note.value = "";
	after_note.value = "";
	const attempt = (job) =>
		job.then(
			(url) => ({ url }),
			(e) => ({ error: e.message || __("Could not render the preview") })
		);
	set_pdf_url(null);
	set_before_url(null);
	let draft_doc = store.value.get_preview_format_doc();
	if (props.compare && store.value.saved_format_data) {
		const diff = describe_draft_changes(store.value.saved_format_data, draft_doc.format_data);
		const marks = [
			...diff.fields.map((f) => ({
				selector: `[data-fieldname="${f.fieldname}"]`,
				note: f.note,
			})),
			...diff.sections.map((sec) => ({
				selector: `[data-section="${sec.index}"]`,
				note: sec.note,
			})),
		];
		if (marks.length) {
			const css_text = (text) => text.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
			const rules = marks.map(
				(m) =>
					`${m.selector} { position: relative; outline: 2px solid #f59e0b; outline-offset: 2px; background: #fff7d6; }` +
					`${m.selector}::before { content: "${css_text(
						m.note
					)}"; position: absolute; right: 0; bottom: 100%; margin-bottom: 3px; padding: 1px 5px; font-size: 8px; line-height: 1.4; font-family: sans-serif; white-space: nowrap; color: #fff; background: #f59e0b; border-radius: 3px; }`
			);
			draft_doc = { ...draft_doc, css: `${draft_doc.css || ""}\n${rules.join("\n")}` };
		}
	}
	const after = await attempt(render_pdf(draft_doc));
	if (seq !== render_seq) return;
	set_pdf_url(after.url || null);
	after_note.value = after.error || "";
	if (!props.compare) return;
	const before = store.value.saved_format_data
		? await attempt(render_saved_pdf())
		: { error: __("Nothing has been saved yet, so everything here is new.") };
	if (seq !== render_seq) return;
	set_before_url(before.url || null);
	before_note.value = before.error || "";
}

function set_pdf_url(next) {
	if (pdf_url.value) URL.revokeObjectURL(pdf_url.value.split("#")[0]);
	pdf_url.value = next;
}

function set_before_url(next) {
	if (before_url.value) URL.revokeObjectURL(before_url.value.split("#")[0]);
	before_url.value = next;
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
	modal.value?.focus();
	render();
	window.addEventListener("keydown", on_keydown);
});
onUnmounted(() => {
	render_abort?.abort();
	set_pdf_url(null);
	set_before_url(null);
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

.pfb-preview-backdrop:has(.pfb-preview-modal--compare) {
	padding: 12px;
}

.pfb-preview-modal--compare {
	width: 100%;
	height: 100%;
}

.pfb-preview-close {
	position: absolute;
	top: 0;
	right: 0;
	z-index: 1;
	color: var(--white);
}

.pfb-preview-close:hover,
.pfb-preview-close:active {
	background: rgba(255, 255, 255, 0.18);
}

.pfb-preview-panes {
	flex: 1;
	min-height: 0;
	display: flex;
	gap: 12px;
}

.pfb-preview-modal--compare {
	position: relative;
}

.pfb-preview-pane {
	flex: 1;
	min-width: 0;
	min-height: 0;
	display: flex;
	flex-direction: column;
}

.pfb-preview-caption {
	margin-bottom: 6px;
	text-align: center;
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
	color: var(--white);
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
