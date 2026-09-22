<template>
	<div
		v-if="shouldRender"
		class="builder-root"
		:class="{ 'pfb-multi-select': $store.is_multi_select.value }"
	>
		<PrintFormatControls v-if="!$store.needs_setup.value" />
		<div class="canvas-area">
			<!-- Canvas toolbar: sample data picker, zoom, preview toggle -->
			<div class="canvas-toolbar" v-if="!$store.needs_setup.value">
				<div class="canvas-toolbar-center">
					<DeskControl
						v-if="doc_picker_df"
						class="canvas-doc-picker"
						:df="doc_picker_df"
						:model-value="$store.preview_doc_name.value || ''"
						@update:model-value="(name) => $store.load_preview_doc(name || null)"
					/>
					<span v-if="no_records" class="canvas-toolbar-hint">
						{{ __("No records to preview yet") }}
					</span>
				</div>
				<div class="canvas-toolbar-right">
					<button
						type="button"
						class="es-button"
						data-variant="ghost"
						data-size="sm"
						data-icon-button="true"
						:title="__('Undo')"
						:disabled="!$store.can_undo.value"
						@click="$store.undo()"
						v-html="frappe.utils.icon('undo-2', 'sm')"
					></button>
					<button
						type="button"
						class="es-button"
						data-variant="ghost"
						data-size="sm"
						data-icon-button="true"
						:title="__('Redo')"
						:disabled="!$store.can_redo.value"
						@click="$store.redo()"
						v-html="frappe.utils.icon('redo-2', 'sm')"
					></button>
					<button
						ref="zoom_ref"
						type="button"
						class="es-button canvas-zoom-trigger"
						data-variant="subtle"
						data-size="sm"
						:title="__('Zoom')"
					>
						<span class="es-button__label">{{ canvas_zoom }}%</span>
						<span v-html="frappe.utils.icon('chevron-down', 'xs')"></span>
					</button>
				</div>
			</div>
			<div v-if="$store.versions.viewing.value" class="pfb-viewing-banner">
				<span v-html="frappe.utils.icon('rotate-ccw-clock', 'sm')"></span>
				<span>
					{{
						__("Viewing {0} ({1}). Editing is off.", [
							$store.versions.viewing.value.label,
							$store.versions.viewing.value.when,
						])
					}}
				</span>
				<button
					class="es-button pfb-viewing-restore"
					data-variant="subtle"
					data-size="sm"
					@click="restore_viewed"
				>
					{{ __("Restore this version") }}
				</button>
			</div>
			<div
				class="print-format-container"
				:class="{
					'pfb-marquee-dragging': marquee_dragging,
					'pfb-viewing': $store.versions.viewing.value,
				}"
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
		<FieldInspector v-if="!$store.needs_setup.value" />
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
import DeskControl from "./components/DeskControl.vue";
import { getStore } from "./stores";
import { field_uid } from "./utils";
import { section_of } from "./layout";
import { computed, ref, onMounted, onUnmounted, provide, watch } from "vue";

const props = defineProps(["print_format_name"]);

const ZOOM_KEY = "pfb_canvas_zoom";
const ZOOM_LEVELS = [50, 60, 70, 80, 90, 100, 125, 150];

let show_preview = ref(false);
let no_records = ref(false);
let canvas_zoom = ref(nearest_zoom(parseInt(localStorage.getItem(ZOOM_KEY)) || 100));
let zoom_ref = ref(null);
let zoom_dropdown = null;

watch(zoom_ref, (el) => {
	zoom_dropdown?.destroy();
	zoom_dropdown = null;
	if (!el) return;
	frappe.ui.dropdown({
		trigger: el,
		align: "end",
		options: () =>
			ZOOM_LEVELS.map((z) => ({
				label: `${z}%`,
				selected: z === canvas_zoom.value,
				onclick: () => set_zoom(z),
			})),
	});
	zoom_dropdown = $(el).data("es-dropdown");
});

const $store = getStore(props.print_format_name);

let shouldRender = computed(() => {
	return Boolean($store.print_format.value && $store.meta.value && $store.layout.value);
});

provide("$store", $store);

function toggle_preview() {
	show_preview.value = !show_preview.value;
}

function toggle_history() {
	$store.versions.toggle();
}

watch(
	[() => $store.selected_field.value, () => $store.selected_section.value],
	([field, section]) => {
		if ((field || section) && $store.versions.open.value) $store.versions.close();
	}
);

function restore_viewed() {
	const v = $store.versions.viewing.value;
	if (v.published) $store.draft.discard();
	else $store.versions.restore(v.name);
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
	$store.selected_field.value = null;
	$store.selected_section.value = null;
	$store.selected_letterhead.value = false;
	$store.selected_lh_footer.value = false;
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
	" .section-toolbar, .drag-handle, .col-width-handle," +
	" .section-preview-actions, .empty-drop-zone, .canvas-toolbar";

function on_canvas_pointerdown(e) {
	if (e.button !== 0 || e.target.closest(MARQUEE_IGNORE)) return;
	marquee_start = { x: e.clientX, y: e.clientY };
	marquee_dragging.value = true; // suppresses text selection while dragging
	const additive = e.shiftKey || e.metaKey || e.ctrlKey;
	marquee_base = {
		fields: additive ? $store.selected_fields.value.slice() : [],
		sections: additive ? $store.selected_sections.value.slice() : [],
	};
	const el_of = (uid) =>
		document.querySelector(`[data-field-uid="${uid}"], [data-section-uid="${uid}"]`);
	const target = (key) => (obj) => {
		const el = el_of(field_uid(obj));
		return el ? { [key]: obj, el, r: el.getBoundingClientRect() } : null;
	};
	marquee_targets = {
		sections: ($store.layout.value?.sections || []).map(target("s")).filter(Boolean),
		fields: $store.ordered_body_fields().map(target("df")).filter(Boolean),
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
	$store.set_selection({ fields, sections });
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
	const src = $store.layout.value;
	// Drop empty columns, then sections that have no columns left
	const sections = (src.sections || [])
		.map((s) => ({ ...s, columns: s.columns.filter((c) => c.fields.length > 0) }))
		.filter((s) => s.columns.length > 0);
	const layout = { ...src, sections };
	$store.layout.value = layout;
	$store.print_format.value.format_data = JSON.stringify(layout);
	$store.dirty.value = true;
	$store.needs_setup.value = false;
}

function on_start_blank() {
	const blank = {
		sections: [],
		header: { columns: [{ label: "", fields: [] }] },
		footer: { columns: [{ label: "", fields: [] }] },
	};
	$store.layout.value = blank;
	$store.print_format.value.format_data = JSON.stringify(blank);
	$store.dirty.value = true;
	$store.needs_setup.value = false;
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
	if (show_preview.value || $store.versions.viewing.value) return;
	// Zoom shortcuts: Ctrl+= / Ctrl+- / Ctrl+0
	if (e.ctrlKey || e.metaKey) {
		if (e.key === "z" || e.key === "Z" || e.key === "y") {
			// rich text editors and dialogs keep their own undo
			if (is_typing_context()) return;
			e.preventDefault();
			if (e.key === "y" || e.shiftKey) $store.redo();
			else $store.undo();
			return;
		}
		if (e.key === "c" || e.key === "C" || e.key === "v" || e.key === "V") {
			if (is_typing_context()) return;
			const is_copy = e.key === "c" || e.key === "C";
			if (is_copy) {
				// Let native copy work when text is highlighted or nothing in the
				// canvas is selected
				if (String(window.getSelection() || "")) return;
				if (!$store.selected_field.value && !$store.selected_section.value) return;
				e.preventDefault();
				$store.copy_selection();
			} else {
				if (!$store.clipboard.value) return;
				e.preventDefault();
				$store.paste_clipboard();
			}
			return;
		}
		if (e.key === "d" || e.key === "D") {
			if (is_typing_context()) return;
			if (!$store.selected_field.value && !$store.selected_section.value) return;
			e.preventDefault();
			$store.duplicate_selection();
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
		if (!$store.selected_field.value && !$store.selected_section.value) return;
		e.preventDefault();
		$store.move_selection(e.key === "ArrowUp" ? -1 : 1);
		return;
	}

	if (e.key === "Delete" || e.key === "Backspace") {
		// Never hijack delete/backspace from text editing contexts
		if (is_typing_context()) return;
		const sf = $store.selected_field.value;
		const ss = $store.selected_section.value;
		if ($store.is_multi_select.value) {
			$store.remove_selection();
			e.preventDefault();
		} else if (sf) {
			sf.remove = true;
			$store.selected_field.value = null;
			e.preventDefault();
		} else if (ss) {
			// Header/footer zones aren't in layout.sections, so they can't be deleted
			const sections = $store.layout.value?.sections || [];
			const idx = sections.indexOf(ss);
			if (idx !== -1) {
				sections.splice(idx, 1);
				$store.selected_section.value = null;
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

	const sf = $store.selected_field.value;
	const ss = $store.selected_section.value;

	if (sf) {
		$store.selected_field.value = null;
		$store.selected_section.value = section_of($store.layout.value, sf);
		e.stopPropagation();
	} else if (ss) {
		// Navigate up: section → canvas (clear all)
		$store.selected_section.value = null;
		e.stopPropagation();
	} else if ($store.selected_letterhead.value || $store.selected_lh_footer.value) {
		// letter head zones have no parent — Escape just deselects them
		$store.selected_letterhead.value = false;
		$store.selected_lh_footer.value = false;
		e.stopPropagation();
	}
}

function nearest_zoom(value) {
	return ZOOM_LEVELS.reduce((best, z) =>
		Math.abs(z - value) < Math.abs(best - value) ? z : best
	);
}

function set_zoom(value) {
	canvas_zoom.value = value;
	localStorage.setItem(ZOOM_KEY, value);
}

function zoom_in() {
	const i = ZOOM_LEVELS.indexOf(canvas_zoom.value);
	set_zoom(ZOOM_LEVELS[Math.min(ZOOM_LEVELS.length - 1, i + 1)]);
}

function zoom_out() {
	const i = ZOOM_LEVELS.indexOf(canvas_zoom.value);
	set_zoom(ZOOM_LEVELS[Math.max(0, i - 1)]);
}

function reset_zoom() {
	set_zoom(100);
}

const is_printable_docstatus = (docstatus) =>
	frappe.model.can_print_docstatus($store.meta.value?.name, docstatus);
const printable_filters = computed(() => {
	const meta = $store.meta.value;
	return meta?.is_submittable
		? { docstatus: ["in", [0, 1, 2].filter(is_printable_docstatus)] }
		: {};
});
const doc_picker_df = computed(() => {
	const meta = $store.meta.value;
	if (!meta || $store.needs_setup.value) return null;
	return {
		fieldname: "preview_doc",
		fieldtype: "Link",
		options: meta.name,
		placeholder: __("Pick a {0} to preview...", [__(meta.name)]),
		with_link_btn: true,
		get_query: () => ({ filters: printable_filters.value }),
	};
});

function pick_initial_doc() {
	const st = $store;
	const meta = st.meta.value;
	const saved = st.persisted_preview_doc_name();
	const auto_select = () =>
		frappe.db
			.get_list(meta?.name, {
				filters: printable_filters.value,
				limit: 1,
				fields: ["name"],
				order_by: "creation desc",
			})
			.then((rows) =>
				rows?.length ? st.load_preview_doc(rows[0].name) : (no_records.value = true)
			);
	if (!saved) return auto_select();
	frappe.db
		.get_value(meta?.name, saved, ["name", "docstatus"])
		.then((r) =>
			r?.message?.name && is_printable_docstatus(r.message.docstatus)
				? st.load_preview_doc(saved)
				: auto_select()
		);
}

watch(doc_picker_df, (df, was) => df && !was && pick_initial_doc());

function warn_before_unload(e) {
	const st = $store;
	if (st.dirty.value || st.draft.saving_count.value > 0 || st.draft.save_failed.value)
		e.preventDefault();
}

onMounted(() => {
	document.addEventListener("keydown", handle_keydown);
	window.addEventListener("beforeunload", warn_before_unload);

	$store.fetch().then(() => {
		if ($store.print_format.value?.custom_format) {
			frappe.set_route("Form", "Print Format", props.print_format_name);
			return;
		}
		if (!$store.layout.value) {
			$store.layout.value = $store.get_default_layout();
			$store.draft.save();
		}
	});
});

onUnmounted(() => {
	document.removeEventListener("keydown", handle_keydown);
	zoom_dropdown?.destroy();
	window.removeEventListener("beforeunload", warn_before_unload);
	window.removeEventListener("pointermove", on_canvas_pointermove);
	window.removeEventListener("pointerup", on_canvas_pointerup);
});

defineExpose({ toggle_preview, toggle_history, open_print_settings, show_preview, $store });
</script>

<style scoped>
.builder-root {
	/* single source of truth for every selection/hover ring on the canvas —
	   change these two and fields, sections, and layer-hover all update */
	--pfb-accent: var(--blue-400);
	--pfb-ring: 2px solid var(--pfb-accent);
	display: flex;
	width: 100%;
	height: 100%;
}

/* In bulk mode the per-item action toolbars (remove) are
   just noise on top of every highlighted block — the bulk panel drives actions
   instead. Hide them everywhere at once from the one multi-select flag. */
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
	height: 100%;
}

/* ── Canvas toolbar ──────────────────────────────────────── */
.canvas-toolbar {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 0 8px;
	height: 44px;
	border-bottom: 1px solid var(--border-color);
	background: var(--fg-color);
}

.canvas-toolbar-center {
	flex: 1;
	min-width: 0;
	max-width: 250px;
}

.canvas-doc-picker :deep(.form-control) {
	font-size: var(--text-sm);
	height: 28px;
	padding: 2px 8px;
	border-radius: var(--radius);
}

.canvas-toolbar-hint {
	font-size: var(--text-sm);
	color: var(--text-muted);
	white-space: nowrap;
}

.canvas-toolbar-right {
	flex-shrink: 0;
	margin-left: auto;
	display: flex;
	align-items: center;
	gap: 6px;
}

.canvas-zoom-trigger {
	font-variant-numeric: tabular-nums;
}

/* ── Canvas scroll area ──────────────────────────────────── */
.pfb-viewing-banner {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 6px 12px;
	font-size: var(--text-sm);
	background: var(--surface-amber-2);
	color: var(--ink-amber-8);
}

.pfb-viewing-restore {
	margin-left: auto;
}

.print-format-container.pfb-viewing {
	pointer-events: none;
}

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
	background: color-mix(in srgb, var(--blue-400) 12%, transparent);
	border-radius: 2px;
	pointer-events: none;
}
</style>
