<template>
	<div
		v-if="shouldRender"
		class="builder-root"
		:class="{ 'pfb-multi-select': $store.is_multi_select.value }"
	>
		<PrintFormatControls />
		<div class="canvas-area">
			<!-- Canvas toolbar: sample data picker, zoom, preview toggle -->
			<div class="canvas-toolbar">
				<div class="canvas-toolbar-left">
					<span class="canvas-toolbar-eyebrow">{{ __("Data") }}</span>
				</div>
				<div class="canvas-toolbar-center">
					<div ref="doc_picker_ref" class="canvas-doc-picker"></div>
				</div>
				<div class="canvas-toolbar-right">
					<div class="canvas-zoom-control" role="group" :aria-label="__('Zoom')">
						<button
							class="canvas-zoom-btn"
							:title="__('Zoom out')"
							:disabled="canvas_zoom <= ZOOM_MIN"
							@click="zoom_out"
							v-html="frappe.utils.icon('minus', 'xs')"
						></button>
						<button
							class="canvas-zoom-label"
							:title="__('Reset zoom')"
							@click="reset_zoom"
						>
							{{ canvas_zoom }}%
						</button>
						<button
							class="canvas-zoom-btn"
							:title="__('Zoom in')"
							:disabled="canvas_zoom >= ZOOM_MAX"
							@click="zoom_in"
							v-html="frappe.utils.icon('plus', 'xs')"
						></button>
					</div>
				</div>
			</div>
			<div
				class="print-format-container"
				:class="{ 'pfb-marquee-dragging': marquee_dragging }"
				:style="{ '--pfb-zoom': canvas_zoom / 100 }"
				@click="clear_selection"
				@pointerdown="on_canvas_pointerdown"
			>
				<PrintFormatSetup
					v-if="$store.needs_setup.value"
					@start-default="on_start_default"
					@start-blank="on_start_blank"
				/>
				<component :is="PrintFormat" v-else />
			</div>
		</div>
		<FieldInspector />
		<Preview v-if="show_preview" @close="show_preview = false" />
		<ContextMenu />
		<Teleport to="body">
			<div
				v-if="marquee"
				class="pfb-marquee"
				:style="{
					left: marquee.x + 'px',
					top: marquee.y + 'px',
					width: marquee.w + 'px',
					height: marquee.h + 'px',
				}"
			></div>
		</Teleport>
	</div>
</template>

<script setup>
import PrintFormat from "./components/editor/PrintFormat.vue";
import PrintFormatSetup from "./components/editor/PrintFormatSetup.vue";
import Preview from "./components/Preview.vue";
import PrintFormatControls from "./components/PrintFormatControls.vue";
import FieldInspector from "./components/inspector/FieldInspector.vue";
import ContextMenu from "./components/editor/ContextMenu.vue";
import { getStore } from "./stores";
import { field_uid } from "./utils";
import { computed, ref, onMounted, onUnmounted, provide, nextTick } from "vue";

const props = defineProps(["print_format_name"]);

const ZOOM_KEY = "pfb_canvas_zoom";
const ZOOM_STEP = 10;
const ZOOM_MIN = 50;
const ZOOM_MAX = 150;

let show_preview = ref(false);
let doc_picker_ref = ref(null);
let doc_picker_ctrl = ref(null);
let canvas_zoom = ref(parseInt(localStorage.getItem(ZOOM_KEY)) || 100);

let $store = computed(() => {
	return getStore(props.print_format_name);
});

let shouldRender = computed(() => {
	return Boolean(
		$store.value.print_format.value && $store.value.meta.value && $store.value.layout.value
	);
});

provide("$store", $store.value);

function toggle_preview() {
	show_preview.value = !show_preview.value;
}

const SETTINGS_DOCTYPE = "Print Settings";

// Editing the Single in a dialog rather than routing to its form: the builder
// holds unsaved layout in memory, and navigating away would drop it.
async function open_print_settings() {
	if (!frappe.perm.has_perm(SETTINGS_DOCTYPE, 0, "write")) {
		frappe.msgprint(__("You are not permitted to change Print Settings"));
		return;
	}
	await frappe.model.with_doctype(SETTINGS_DOCTYPE);
	const doc = await frappe.model.with_doc(SETTINGS_DOCTYPE, SETTINGS_DOCTYPE);
	// built from the doctype's own meta, so a new field shows up here for free
	const fields = frappe.get_meta(SETTINGS_DOCTYPE).fields.filter((df) => !df.hidden);

	const dialog = new frappe.ui.Dialog({
		title: __("Print Settings"),
		size: "large",
		fields: fields.map((df) => ({ ...df, default: doc[df.fieldname] })),
		primary_action_label: __("Save"),
		primary_action: (values) => {
			frappe
				.call("frappe.client.set_value", {
					doctype: SETTINGS_DOCTYPE,
					name: SETTINGS_DOCTYPE,
					fieldname: values,
				})
				.then(() => {
					dialog.hide();
					frappe.show_alert({
						message: __("Print Settings updated"),
						indicator: "green",
					});
				});
		},
	});
	dialog.show();
}

function clear_selection() {
	// a marquee drag ends with a click on the canvas — don't let it wipe the result
	if (suppress_next_click) {
		suppress_next_click = false;
		return;
	}
	$store.value.selected_field.value = null;
	$store.value.selected_section.value = null;
}

// ── Marquee (rubber-band) selection ──────────────────────────
const marquee = ref(null);
const marquee_dragging = ref(false);
let marquee_start = null;
let marquee_base = { fields: [], sections: [] };
// element + rect for every hit-testable target, captured once per drag (no reflow
// happens mid-marquee, so re-reading rects on every pointermove would only thrash)
let marquee_targets = { sections: [], fields: [] };
let suppress_next_click = false;
const MARQUEE_THRESHOLD = 4;

// controls that should start their own interaction, never a marquee
const MARQUEE_IGNORE =
	".field--preview, .field--chip, button, input, textarea, select, a, [contenteditable]," +
	" .section-toolbar, .drag-handle, .col-width-handle, .field-preview-actions," +
	" .section-preview-actions, .empty-drop-zone, .canvas-toolbar";

function on_canvas_pointerdown(e) {
	if (e.button !== 0 || e.target.closest(MARQUEE_IGNORE)) return;
	marquee_start = { x: e.clientX, y: e.clientY };
	marquee_dragging.value = true; // suppresses text selection while dragging
	const additive = e.shiftKey || e.metaKey || e.ctrlKey;
	marquee_base = {
		fields: additive ? $store.value.selected_fields.value.slice() : [],
		sections: additive ? $store.value.selected_sections.value.slice() : [],
	};
	const el_of = (uid) =>
		document.querySelector(`[data-field-uid="${uid}"], [data-section-uid="${uid}"]`);
	const target = (key) => (obj) => {
		const el = el_of(field_uid(obj));
		return el ? { [key]: obj, el, r: el.getBoundingClientRect() } : null;
	};
	marquee_targets = {
		sections: ($store.value.layout.value?.sections || []).map(target("s")).filter(Boolean),
		fields: $store.value.ordered_body_fields().map(target("df")).filter(Boolean),
	};
	window.addEventListener("pointermove", on_canvas_pointermove);
	window.addEventListener("pointerup", on_canvas_pointerup);
}

function on_canvas_pointermove(e) {
	if (!marquee_start) return;
	const x = Math.min(marquee_start.x, e.clientX);
	const y = Math.min(marquee_start.y, e.clientY);
	const w = Math.abs(e.clientX - marquee_start.x);
	const h = Math.abs(e.clientY - marquee_start.y);
	// only engage once it's a real drag, so plain clicks still clear selection
	if (!marquee.value && w < MARQUEE_THRESHOLD && h < MARQUEE_THRESHOLD) return;
	marquee.value = { x, y, w, h };
	update_marquee_selection();
}

const dedupe = (arr) => [...new Set(arr)];

function update_marquee_selection() {
	const box = marquee.value;
	if (!box) return;
	const encloses = (r) =>
		r.left >= box.x && r.top >= box.y && r.right <= box.x + box.w && r.bottom <= box.y + box.h;
	const overlaps = (r) =>
		r.left < box.x + box.w && r.right > box.x && r.top < box.y + box.h && r.bottom > box.y;

	// Builder rule: select the outermost fully-enclosed element. A section the box
	// fully wraps is selected as a section; its fields are then dropped. Fields that
	// don't belong to any enclosed section are selected on their own.
	const enclosed = marquee_targets.sections.filter((x) => encloses(x.r));
	const looseFields = marquee_targets.fields
		.filter((x) => overlaps(x.r) && !enclosed.some((sec) => sec.el.contains(x.el)))
		.map((x) => x.df);

	const fields = dedupe([...marquee_base.fields, ...looseFields]);
	const sections = dedupe([...marquee_base.sections, ...enclosed.map((x) => x.s)]);
	$store.value.set_selection({ fields, sections });
}

function on_canvas_pointerup() {
	window.removeEventListener("pointermove", on_canvas_pointermove);
	window.removeEventListener("pointerup", on_canvas_pointerup);
	suppress_next_click = !!marquee.value;
	marquee.value = null;
	marquee_start = null;
	marquee_dragging.value = false;
}

function on_start_default() {
	const src = $store.value.layout.value;
	// Drop empty columns, then sections that have no columns left
	const sections = (src.sections || [])
		.map((s) => ({ ...s, columns: s.columns.filter((c) => c.fields.length > 0) }))
		.filter((s) => s.columns.length > 0);
	const layout = { ...src, sections };
	$store.value.layout.value = layout;
	$store.value.print_format.value.format_data = JSON.stringify(layout);
	$store.value.dirty.value = true;
	$store.value.needs_setup.value = false;
}

function on_start_blank() {
	const blank = {
		sections: [],
		header: { columns: [{ label: "", fields: [] }] },
		footer: { columns: [{ label: "", fields: [] }] },
	};
	$store.value.layout.value = blank;
	$store.value.print_format.value.format_data = JSON.stringify(blank);
	$store.value.dirty.value = true;
	$store.value.needs_setup.value = false;
}

function is_typing_context() {
	const el = document.activeElement;
	return !!(
		el?.tagName === "INPUT" ||
		el?.tagName === "TEXTAREA" ||
		el?.isContentEditable ||
		el?.closest(".modal")
	);
}

function handle_keydown(e) {
	// Zoom shortcuts: Ctrl+= / Ctrl+- / Ctrl+0
	if (e.ctrlKey || e.metaKey) {
		if (e.key === "z" || e.key === "Z" || e.key === "y") {
			// rich text editors and dialogs keep their own undo
			if (is_typing_context()) return;
			e.preventDefault();
			if (e.key === "y" || e.shiftKey) $store.value.redo();
			else $store.value.undo();
			return;
		}
		if (e.key === "c" || e.key === "C" || e.key === "v" || e.key === "V") {
			if (is_typing_context()) return;
			const is_copy = e.key === "c" || e.key === "C";
			if (is_copy) {
				// Let native copy work when text is highlighted or nothing in the
				// canvas is selected
				if (String(window.getSelection() || "")) return;
				if (!$store.value.selected_field.value && !$store.value.selected_section.value)
					return;
				e.preventDefault();
				$store.value.copy_selection();
			} else {
				if (!$store.value.clipboard.value) return;
				e.preventDefault();
				$store.value.paste_clipboard();
			}
			return;
		}
		if (e.key === "d" || e.key === "D") {
			if (is_typing_context()) return;
			if (!$store.value.selected_field.value && !$store.value.selected_section.value) return;
			e.preventDefault();
			$store.value.duplicate_selection();
			return;
		}
		if (e.key === "=" || e.key === "+") {
			e.preventDefault();
			zoom_in();
			return;
		}
		if (e.key === "-") {
			e.preventDefault();
			zoom_out();
			return;
		}
		if (e.key === "0") {
			e.preventDefault();
			reset_zoom();
			return;
		}
	}

	if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
		if (is_typing_context()) return;
		if (!$store.value.selected_field.value && !$store.value.selected_section.value) return;
		e.preventDefault();
		$store.value.move_selection(e.key === "ArrowUp" ? -1 : 1);
		return;
	}

	if (e.key === "Delete" || e.key === "Backspace") {
		// Never hijack delete/backspace from text editing contexts
		if (is_typing_context()) return;
		const sf = $store.value.selected_field.value;
		const ss = $store.value.selected_section.value;
		if ($store.value.is_multi_select.value) {
			$store.value.remove_selection();
			e.preventDefault();
		} else if (sf) {
			sf.remove = true;
			$store.value.selected_field.value = null;
			e.preventDefault();
		} else if (ss) {
			// Header/footer zones aren't in layout.sections, so they can't be deleted
			const sections = $store.value.layout.value?.sections || [];
			const idx = sections.indexOf(ss);
			if (idx !== -1) {
				sections.splice(idx, 1);
				$store.value.selected_section.value = null;
				e.preventDefault();
			}
		}
		return;
	}

	if (e.key !== "Escape") return;
	// Don't intercept if a modal/dialog is open
	if (document.querySelector(".modal.show")) return;
	const dialog_open = Array.from(document.querySelectorAll(".frappe-dialog")).some(
		(el) => el.offsetParent !== null
	);
	if (dialog_open) return;

	const sf = $store.value.selected_field.value;
	const ss = $store.value.selected_section.value;

	if (sf) {
		// Navigate up: field → parent section
		const lv = $store.value.layout.value;
		const all_sections = [lv?.header, ...(lv?.sections || []), lv?.footer].filter(Boolean);
		let parent = null;
		for (const sec of all_sections) {
			for (const col of sec.columns || []) {
				if (col.fields?.includes(sf)) {
					parent = sec;
					break;
				}
			}
			if (parent) break;
		}
		$store.value.selected_field.value = null;
		$store.value.selected_section.value = parent || null;
		e.stopPropagation();
	} else if (ss) {
		// Navigate up: section → canvas (clear all)
		$store.value.selected_section.value = null;
		e.stopPropagation();
	}
}

function zoom_in() {
	canvas_zoom.value = Math.min(ZOOM_MAX, canvas_zoom.value + ZOOM_STEP);
	localStorage.setItem(ZOOM_KEY, canvas_zoom.value);
}

function zoom_out() {
	canvas_zoom.value = Math.max(ZOOM_MIN, canvas_zoom.value - ZOOM_STEP);
	localStorage.setItem(ZOOM_KEY, canvas_zoom.value);
}

function reset_zoom() {
	canvas_zoom.value = 100;
	localStorage.setItem(ZOOM_KEY, 100);
}

function init_doc_picker() {
	if (!doc_picker_ref.value) return;
	const meta = $store.value.meta.value;
	// draft/cancelled documents can't be printed unless Print Settings allows it, so
	// keep them out of the picker unless that's turned on
	const is_printable_docstatus = (docstatus) =>
		frappe.model.can_print_docstatus(meta?.name, docstatus);
	const printable_filters = meta?.is_submittable
		? { docstatus: ["in", [0, 1, 2].filter(is_printable_docstatus)] }
		: {};
	doc_picker_ctrl.value = frappe.ui.form.make_control({
		parent: doc_picker_ref.value,
		df: {
			fieldname: "preview_doc",
			fieldtype: "Link",
			options: meta?.name,
			placeholder: __("Pick a {0} to preview...", [__(meta?.name || "document")]),
			get_query: () => ({ filters: printable_filters }),
			change: () => {
				const name = doc_picker_ctrl.value.get_value();
				$store.value.load_preview_doc(name || null);
			},
		},
		render_input: true,
	});
	doc_picker_ref.value.querySelector(".control-label")?.remove();
	doc_picker_ref.value.querySelector(".form-group")?.style.setProperty("margin", "0");

	const select = (name) => {
		doc_picker_ctrl.value?.set_value(name);
		$store.value.load_preview_doc(name);
	};
	// Prefer the record chosen last time (persisted across refresh); otherwise
	// auto-select the most recent printable record so the preview is ready immediately.
	const saved = $store.value.persisted_preview_doc_name();
	const auto_select = () =>
		frappe.db
			.get_list(meta?.name, {
				filters: printable_filters,
				limit: 1,
				fields: ["name"],
				order_by: "creation desc",
			})
			.then((rows) => rows?.length && select(rows[0].name));
	if (saved) {
		frappe.db
			.get_value(meta?.name, saved, ["name", "docstatus"])
			.then((r) =>
				r?.message?.name && is_printable_docstatus(r.message.docstatus)
					? select(saved)
					: auto_select()
			);
	} else {
		auto_select();
	}
}

onMounted(() => {
	document.addEventListener("keydown", handle_keydown);

	$store.value.fetch().then(() => {
		if (!$store.value.layout.value) {
			$store.value.layout.value = $store.value.get_default_layout();
			$store.value.save_changes();
		}
		nextTick(init_doc_picker);
	});
});

onUnmounted(() => {
	document.removeEventListener("keydown", handle_keydown);
	window.removeEventListener("pointermove", on_canvas_pointermove);
	window.removeEventListener("pointerup", on_canvas_pointerup);
});

defineExpose({ toggle_preview, open_print_settings, show_preview, $store });
</script>

<style scoped>
.builder-root {
	/* navbar + page head height */
	--pfb-chrome-offset: 95px;
	/* single source of truth for every selection/hover ring on the canvas —
	   change these two and fields, sections, and layer-hover all update */
	--pfb-accent: var(--blue-400);
	--pfb-ring: 2px solid var(--pfb-accent);
	display: flex;
	width: 100%;
}

/* In bulk mode the per-item action toolbars (copy/duplicate/snippet/remove) are
   just noise on top of every highlighted block — the bulk panel drives actions
   instead. Hide them everywhere at once from the one multi-select flag. */
.builder-root.pfb-multi-select :deep(.field-preview-actions),
.builder-root.pfb-multi-select :deep(.field-actions),
.builder-root.pfb-multi-select :deep(.section-preview-actions),
.builder-root.pfb-multi-select :deep(.section-toolbar-right) {
	display: none;
}

.canvas-area {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	height: calc(100vh - var(--pfb-chrome-offset));
}

/* ── Canvas toolbar ──────────────────────────────────────── */
.canvas-toolbar {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 0 16px;
	height: 40px;
	border-bottom: 1px solid var(--border-color);
	background: var(--fg-color);
}

.canvas-toolbar-left {
	flex-shrink: 0;
}

.canvas-toolbar-eyebrow {
	font-size: 9px;
	font-weight: 700;
	letter-spacing: 0.1em;
	color: var(--text-muted);
	white-space: nowrap;
}

.canvas-toolbar-center {
	flex: 1;
	min-width: 0;
	max-width: 320px;
}

.canvas-doc-picker :deep(.form-group) {
	margin: 0;
}

.canvas-doc-picker :deep(.form-control) {
	font-size: var(--text-sm);
	height: 28px;
	padding: 2px 8px;
	border-radius: var(--radius);
}

.canvas-toolbar-right {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	gap: 6px;
}

/* ── Zoom control ────────────────────────────────────────── */
.canvas-zoom-control {
	display: flex;
	align-items: center;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	overflow: hidden;
}

.canvas-zoom-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 24px;
	height: 24px;
	border: none;
	background: transparent;
	cursor: pointer;
	color: var(--text-muted);
	padding: 0;
	flex-shrink: 0;
}

.canvas-zoom-btn:hover:not(:disabled) {
	background: var(--gray-100);
	color: var(--text-color);
}

.canvas-zoom-btn:disabled {
	opacity: 0.35;
	cursor: not-allowed;
}

.canvas-zoom-label {
	font-size: 11px;
	font-weight: 500;
	font-variant-numeric: tabular-nums;
	color: var(--text-color);
	background: transparent;
	border: none;
	border-left: 1px solid var(--border-color);
	border-right: 1px solid var(--border-color);
	padding: 0 6px;
	height: 24px;
	min-width: 40px;
	cursor: pointer;
	white-space: nowrap;
}

.canvas-zoom-label:hover {
	background: var(--gray-100);
}

/* ── Canvas scroll area ──────────────────────────────────── */
.print-format-container {
	flex: 1;
	overflow-y: auto;
	padding-top: 0.5rem;
	padding-bottom: 4rem;
}

.print-format-container :deep(.print-format-main) {
	zoom: var(--pfb-zoom, 1);
}

/* while rubber-band dragging, don't let the drag select page text */
.print-format-container.pfb-marquee-dragging,
.print-format-container.pfb-marquee-dragging :deep(*) {
	user-select: none;
}

/* teleported to <body>, so --pfb-accent (scoped to .builder-root) isn't in scope */
.pfb-marquee {
	position: fixed;
	z-index: 1040;
	border: 1px solid var(--blue-400);
	background: rgba(97, 175, 239, 0.12);
	border-radius: 2px;
	pointer-events: none;
}
</style>
