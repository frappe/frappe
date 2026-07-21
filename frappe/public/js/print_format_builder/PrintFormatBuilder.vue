<template>
	<div
		v-if="shouldRender"
		class="builder-root"
		:class="{
			'builder-root--preview': show_preview,
		}"
	>
		<PrintFormatControls v-if="!show_preview" />
		<div class="canvas-area">
			<!-- Sidebar-open hint -->
			<div v-if="sidebar_open && !hint_dismissed" class="pfb-sidebar-hint">
				<span v-html="frappe.utils.icon('info', 'sm', 'pfb-hint-icon')"></span>
				<span class="pfb-hint-text">{{
					__("Tip: Close the left sidebar for more editing space.")
				}}</span>
				<button class="pfb-hint-dismiss" @click="dismiss_hint" :aria-label="__('Dismiss')">
					<span v-html="frappe.utils.icon('x', 'xs')"></span>
				</button>
			</div>

			<!-- Canvas toolbar: sample data picker (hidden in preview mode).
			     v-show (not v-if) so the picker control survives a preview round-trip. -->
			<div v-show="!show_preview" class="canvas-toolbar">
				<div class="canvas-toolbar-left">
					<span class="canvas-toolbar-eyebrow">{{ __("Data") }}</span>
				</div>
				<div class="canvas-toolbar-center">
					<div ref="doc_picker_ref" class="canvas-doc-picker"></div>
				</div>
				<div class="canvas-toolbar-right">
					<span v-if="!$store.preview_doc.value" class="canvas-no-data-hint">
						← {{ __("Pick a record to see real values") }}
					</span>
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
				:style="{ '--pfb-zoom': canvas_zoom / 100 }"
				@click="clear_selection"
			>
				<PrintFormatSetup
					v-if="$store.needs_setup.value"
					@start-default="on_start_default"
					@start-blank="on_start_blank"
				/>
				<KeepAlive v-else>
					<component :is="Preview" v-if="show_preview" />
					<component :is="PrintFormat" v-else />
				</KeepAlive>
			</div>
		</div>
		<FieldInspector v-if="!show_preview" />
	</div>
</template>

<script setup>
import PrintFormat from "./components/editor/PrintFormat.vue";
import PrintFormatSetup from "./components/editor/PrintFormatSetup.vue";
import Preview from "./components/Preview.vue";
import PrintFormatControls from "./components/PrintFormatControls.vue";
import FieldInspector from "./components/inspector/FieldInspector.vue";
import { getStore } from "./stores";
import { computed, ref, onMounted, onUnmounted, provide, nextTick, watch } from "vue";

// props
const props = defineProps(["print_format_name"]);

const HINT_KEY = "pfb_sidebar_hint_dismissed";
const ZOOM_KEY = "pfb_canvas_zoom";
const ZOOM_STEP = 10;
const ZOOM_MIN = 50;
const ZOOM_MAX = 150;

// variables
let show_preview = ref(false);
let doc_picker_ref = ref(null);
let doc_picker_ctrl = ref(null);
let sidebar_open = ref(false);
let hint_dismissed = ref(localStorage.getItem(HINT_KEY) === "1");
let canvas_zoom = ref(parseInt(localStorage.getItem(ZOOM_KEY)) || 100);
let sidebar_observer_ref = null;

// computed
let $store = computed(() => {
	return getStore(props.print_format_name);
});

let shouldRender = computed(() => {
	return Boolean(
		$store.value.print_format.value && $store.value.meta.value && $store.value.layout.value
	);
});

// provide
provide("$store", $store.value);

// methods
function toggle_preview() {
	show_preview.value = !show_preview.value;
}

watch(show_preview, (on) => {
	if (on) {
		history.pushState({ ...history.state, pfb_preview: true }, "");
	} else {
		// Reflect a document changed in preview mode back in the edit-mode picker
		const name = $store.value.preview_doc_name.value;
		if (name && doc_picker_ctrl.value?.get_value() !== name) {
			doc_picker_ctrl.value?.set_value(name);
		}
		if (history.state?.pfb_preview) {
			history.back();
		}
	}
});

function handle_popstate() {
	if (show_preview.value) {
		show_preview.value = false;
	}
}

function clear_selection() {
	$store.value.selected_field.value = null;
	$store.value.selected_section.value = null;
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
		if ($store.value.selected_fields.value.length > 1) {
			$store.value.remove_selected_fields();
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

function check_sidebar() {
	sidebar_open.value = frappe.app?.sidebar?.wrapper?.is(":visible") ?? false;
}

function dismiss_hint() {
	hint_dismissed.value = true;
	localStorage.setItem(HINT_KEY, "1");
}

function init_doc_picker() {
	if (!doc_picker_ref.value) return;
	const meta = $store.value.meta.value;
	doc_picker_ctrl.value = frappe.ui.form.make_control({
		parent: doc_picker_ref.value,
		df: {
			fieldname: "preview_doc",
			fieldtype: "Link",
			options: meta?.name,
			placeholder: __("Pick a {0} to preview...", [__(meta?.name || "document")]),
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
	// auto-select the most recent record so the preview is ready immediately.
	const saved = $store.value.persisted_preview_doc_name();
	const auto_select = () =>
		frappe.db
			.get_list(meta?.name, { limit: 1, fields: ["name"], order_by: "creation desc" })
			.then((rows) => rows?.length && select(rows[0].name));
	if (saved) {
		frappe.db
			.get_value(meta?.name, saved, "name")
			.then((r) => (r?.message?.name ? select(saved) : auto_select()));
	} else {
		auto_select();
	}
}

// mounted
onMounted(() => {
	document.addEventListener("keydown", handle_keydown);
	window.addEventListener("popstate", handle_popstate);

	// Detect desk sidebar open/close via MutationObserver on the wrapper's style attribute
	check_sidebar();
	const sidebar_el = frappe.app?.sidebar?.wrapper?.[0];
	if (sidebar_el) {
		sidebar_observer_ref = new MutationObserver(check_sidebar);
		sidebar_observer_ref.observe(sidebar_el, { attributes: true, attributeFilter: ["style"] });
	}
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
	window.removeEventListener("popstate", handle_popstate);
	sidebar_observer_ref?.disconnect();
});

defineExpose({ toggle_preview, show_preview, $store });
</script>

<style scoped>
.builder-root {
	/* navbar + page head height */
	--pfb-chrome-offset: 95px;
	display: flex;
	width: 100%;
}

.canvas-area {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	height: calc(100vh - var(--pfb-chrome-offset));
}

.builder-root--preview .canvas-area {
	padding-left: 1.5rem;
	padding-right: 1.5rem;
}

/* ── Sidebar hint ────────────────────────────────────────── */
.pfb-sidebar-hint {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 4px 12px;
	background: var(--gray-50);
	border-bottom: 1px solid var(--gray-200);
	font-size: var(--text-xs);
	color: var(--gray-700);
}

.pfb-hint-icon {
	flex-shrink: 0;
	opacity: 0.7;
}

.pfb-hint-text {
	flex: 1;
}

.pfb-hint-dismiss {
	flex-shrink: 0;
	display: flex;
	align-items: center;
	padding: 2px;
	border: none;
	background: transparent;
	cursor: pointer;
	color: var(--gray-500);
	border-radius: var(--radius);
	line-height: 1;
	opacity: 0.7;
}

.pfb-hint-dismiss:hover {
	opacity: 1;
	background: var(--gray-200);
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

.canvas-no-data-hint {
	display: flex;
	align-items: center;
	gap: 4px;
	font-size: 11px;
	color: var(--text-muted);
	white-space: nowrap;
	background: var(--yellow-50);
	border: 1px solid var(--yellow-200);
	border-radius: var(--radius);
	padding: 3px 8px;
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
</style>
