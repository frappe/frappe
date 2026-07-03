<template>
	<div class="pfb-inspector" @click.stop>
		<!-- Header -->
		<div class="pfb-inspector-head">
			<div class="pfb-inspector-title">
				<span class="pfb-inspector-kind">{{ inspector_kind }}</span>
				<span
					class="pfb-inspector-name"
					v-if="
						selected_field ||
						selected_section ||
						selected_letterhead ||
						selected_lh_footer
					"
				>
					{{ inspector_subtitle }}
				</span>
				<span v-else class="pfb-inspector-eyebrow-inline">{{ __("Inspector") }}</span>
			</div>
		</div>

		<!-- Breadcrumb: navigate up to parent section when a field is selected -->
		<div v-if="selected_field && parent_section" class="pfb-breadcrumb">
			<button
				class="pfb-breadcrumb-btn"
				@click="select_parent_section"
				:title="__('Select parent section (Esc)')"
			>
				<span v-html="frappe.utils.icon('arrow-up', 'xs')"></span>
				<span class="pfb-breadcrumb-label">{{ __("Section:") }}</span>
				<span class="pfb-breadcrumb-name">{{
					parent_section.label || __("Untitled")
				}}</span>
			</button>
		</div>

		<!-- Letter Head notice — shown whenever the letterhead is selected -->
		<div v-if="selected_letterhead || selected_lh_footer" class="pfb-lh-notice">
			{{ __("Edits here update the Letter Head document directly.") }}
		</div>

		<!-- Empty state -->
		<div
			v-if="
				!selected_field && !selected_section && !selected_letterhead && !selected_lh_footer
			"
			class="pfb-inspector-empty"
		>
			<svg class="icon icon-md text-muted" style="margin-bottom: 8px">
				<use href="#icon-text-cursor"></use>
			</svg>
			<p class="text-muted">{{ __("Click a field to edit its properties") }}</p>
		</div>

		<!-- ── Letter Head Footer inspector ──────────────────────── -->
		<template v-else-if="selected_lh_footer">
			<LetterHeadZoneInspector zone="footer" />
		</template>

		<!-- ── Letter Head inspector ──────────────────────────────── -->
		<template v-else-if="selected_letterhead">
			<LetterHeadZoneInspector zone="header" />
		</template>

		<!-- ── Table field inspector ───────────────────────────────── -->
		<TableFieldInspector v-else-if="selected_field && is_table_field" />

		<!-- ── Repeater inspector ──────────────────────────────── -->
		<RepeaterFieldInspector v-else-if="selected_field && is_repeater_field" />

		<!-- ── Field inspector ─────────────────────────────────── -->
		<template v-else-if="selected_field">
			<div class="pfb-insp-body">
				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('f_field')">
						<span class="pfb-insp-section-label">{{ __("Field") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.f_field }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.f_field" class="pfb-insp-section-body">
						<div class="pfb-insp-row">
							<span class="pfb-insp-label">{{ __("Source") }}</span>
							<div class="pfb-source-display">
								<span class="pfb-source-name">{{
									selected_field.label || selected_field.fieldname
								}}</span>
								<span class="pfb-type-badge">{{ short_fieldtype }}</span>
							</div>
						</div>
						<template v-if="is_html_field">
							<div
								class="pfb-html-preview"
								v-if="selected_field.html"
								v-html="selected_field.html"
							></div>
							<div v-else class="pfb-insp-hint text-muted">
								{{ __("No HTML content yet.") }}
							</div>
							<button
								class="btn btn-xs btn-default pfb-lh-edit-btn"
								@click="edit_html_field"
							>
								<span v-html="frappe.utils.icon('pencil', 'xs')"></span>
								{{ __("Edit HTML") }}
							</button>
						</template>
						<template v-else>
							<LabelField
								v-model="selected_field.label"
								:label="__('Label')"
								:placeholder="__('Field label')"
								show-toggle
								:show="selected_field.show_label"
								@update:show="(v) => (selected_field.show_label = v)"
							/>
							<SegmentedRow
								:label="__('Align')"
								:model-value="current_align"
								:options="align_opts"
								@update:model-value="(v) => (selected_field.align = v)"
							/>
							<div class="pfb-insp-row" v-if="field_is_inline">
								<span class="pfb-insp-label">{{ __("Spacing") }}</span>
								<select
									class="pfb-insp-select"
									:value="current_label_justify"
									@change="selected_field.label_justify = $event.target.value"
								>
									<option value="">{{ __("Normal") }}</option>
									<option value="space-between">
										{{ __("Space Between") }}
									</option>
									<option value="space-evenly">{{ __("Space Evenly") }}</option>
								</select>
							</div>
							<StepperRow
								v-if="field_is_inline"
								:label="__('Label gap')"
								:model-value="selected_field.label_gap"
								:base="8"
								:step="2"
								unit="px"
								:placeholder="__('auto')"
								allow-empty
								@update:model-value="(v) => (selected_field.label_gap = v)"
							/>
						</template>
					</div>
				</div>

				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('f_style')">
						<span class="pfb-insp-section-label">{{ __("Style") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.f_style }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.f_style">
						<StyleSection v-model="selected_field.custom_style" />
					</div>
				</div>

				<div class="pfb-insp-section">
					<div class="pfb-insp-section-head" @click="toggle('f_visibility')">
						<span class="pfb-insp-section-label">{{ __("Visibility") }}</span>
						<span
							class="pfb-insp-chevron"
							:class="{ collapsed: !open.f_visibility }"
							v-html="frappe.utils.icon('chevron-down', 'xs')"
						></span>
					</div>
					<div v-show="open.f_visibility">
						<VisibilitySection
							v-model="selected_field.visible_if"
							:previewDoc="preview_doc"
						/>
					</div>
				</div>

				<div class="pfb-insp-actions">
					<button class="btn btn-xs btn-danger-subtle" @click="remove_field">
						<span v-html="frappe.utils.icon('x', 'xs')"></span>
						{{ __("Remove field") }}
					</button>
				</div>
			</div>
		</template>

		<!-- ── Section inspector ───────────────────────────────── -->
		<SectionPropertiesPanel v-else-if="selected_section" />
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import { useStore } from "../../stores";
import LetterHeadZoneInspector from "./LetterHeadZoneInspector.vue";
import VisibilitySection from "./VisibilitySection.vue";
import StyleSection from "./StyleSection.vue";
import LabelField from "./LabelField.vue";
import SegmentedRow from "./SegmentedRow.vue";
import StepperRow from "./StepperRow.vue";
import SectionPropertiesPanel from "./SectionPropertiesPanel.vue";
import RepeaterFieldInspector from "./RepeaterFieldInspector.vue";
import TableFieldInspector from "./TableFieldInspector.vue";
import { align_opts } from "./align_opts";

let store = inject("$store");
let { letterhead, layout, meta } = useStore();

let selected_field = computed(() => store.selected_field.value);
let selected_section = computed(() => store.selected_section.value);
let selected_letterhead = computed(() => store.selected_letterhead.value);
let selected_lh_footer = computed(() => store.selected_lh_footer.value);
let preview_doc = computed(() => store.preview_doc.value);

const open = ref({
	f_field: true,
	f_style: false,
	f_visibility: false,
	t_table: true,
	t_columns: true,
	t_style: false,
	t_visibility: true,
	r_repeater: true,
	r_columns: true,
	r_style: false,
});

function toggle(key) {
	open.value[key] = !open.value[key];
}

// ── Inspector header ───────────────────────────────────────
let is_table_field = computed(() => selected_field.value?.fieldtype === "Table");
let is_repeater_field = computed(() => selected_field.value?.fieldtype === "Repeater");
let is_html_field = computed(() => selected_field.value?.fieldtype === "HTML");

let inspector_kind = computed(() => {
	if (selected_lh_footer.value) return __("Letter Head");
	if (selected_letterhead.value) return __("Letter Head");
	if (selected_field.value) {
		if (selected_field.value.fieldtype === "Table") return __("Table");
		return __("Field");
	}
	if (selected_section.value) return __("Section");
	return __("Canvas");
});

let inspector_subtitle = computed(() => {
	if (selected_lh_footer.value) return __("Footer");
	if (selected_letterhead.value) return letterhead.value?.name || "";
	if (selected_field.value) return selected_field.value.label || selected_field.value.fieldname;
	if (selected_section.value) return selected_section.value.label || __("Untitled section");
	return "";
});

// ── Breadcrumb: parent section of the selected field ──────
let parent_section = computed(() => {
	if (!selected_field.value || !layout.value) return null;
	const all_sections = [
		layout.value.header,
		...(layout.value.sections || []),
		layout.value.footer,
	].filter(Boolean);
	for (const section of all_sections) {
		for (const column of section.columns || []) {
			if (column.fields?.includes(selected_field.value)) return section;
		}
	}
	return null;
});

function select_parent_section() {
	if (parent_section.value) {
		store.selected_section.value = parent_section.value;
		store.selected_field.value = null;
	}
}

// ── Field helpers ──────────────────────────────────────────
let short_fieldtype = computed(() => {
	if (!selected_field.value) return "";
	const map = {
		Data: "Data",
		Currency: "Currency",
		Int: "Int",
		Float: "Float",
		Date: "Date",
		Datetime: "DateTime",
		Check: "Check",
		Select: "Select",
		Table: "Table",
		"Long Text": "Text",
		Text: "Text",
		Link: "Link",
		HTML: "HTML",
		Spacer: "Spacer",
		Divider: "Divider",
		"Field Template": "Template",
	};
	return map[selected_field.value.fieldtype] || selected_field.value.fieldtype || "";
});

let current_align = computed(() => selected_field.value?.align ?? "left");
let current_label_justify = computed(() => selected_field.value?.label_justify ?? "");
// Spacing only applies when the field is inline (section "Label side: Left")
let field_is_inline = computed(() => parent_section.value?.field_orientation === "left-right");

function remove_field() {
	if (selected_field.value) {
		selected_field.value.remove = true;
		store.selected_field.value = null;
	}
}

function open_html_split_dialog({ title, initial_html, on_save }) {
	let d = new frappe.ui.Dialog({
		title,
		size: "extra-large",
		fields: [
			{
				fieldname: "split_layout",
				fieldtype: "HTML",
				options: `<div class="pfb-html-split">
					<div class="pfb-html-split-pane pfb-html-split-editor">
						<div class="pfb-html-split-label">${__("HTML")}</div>
						<div class="pfb-html-ctrl-host"></div>
					</div>
					<div class="pfb-html-split-divider"></div>
					<div class="pfb-html-split-pane pfb-html-split-preview">
						<div class="pfb-html-split-label">${__("Preview")}</div>
						<div class="pfb-html-preview-content"></div>
					</div>
				</div>`,
			},
		],
		primary_action_label: __("Save"),
		primary_action: () => {
			const val = d._html_ctrl?.get_value?.() ?? "";
			on_save(frappe.dom.remove_script_and_style(val));
			d.hide();
		},
	});
	d.show();

	setTimeout(() => {
		const host = d.$wrapper.find(".pfb-html-ctrl-host")[0];
		const preview = d.$wrapper.find(".pfb-html-preview-content")[0];
		if (!host) return;

		const ctrl = frappe.ui.form.make_control({
			parent: host,
			df: {
				fieldtype: "Code",
				fieldname: "html_code",
				options: "HTML",
				show_label: false,
			},
			render_input: true,
		});
		ctrl.set_value(initial_html || "");
		d._html_ctrl = ctrl;

		// initial preview
		if (preview) preview.innerHTML = initial_html || "";

		// real-time preview via CodeMirror change event
		setTimeout(() => {
			if (ctrl.editor) {
				ctrl.editor.on(
					"change",
					frappe.utils.debounce(() => {
						if (preview) preview.innerHTML = ctrl.editor.getValue();
					}, 150)
				);
				ctrl.editor.refresh();
			}
		}, 300);
	}, 200);
}

function edit_html_field() {
	open_html_split_dialog({
		title: __("Edit HTML"),
		initial_html: selected_field.value?.html || "",
		on_save: (html) => {
			selected_field.value.html = html;
		},
	});
}
</script>

<style scoped>
.pfb-inspector {
	width: 280px;
	flex-shrink: 0;
	height: calc(100vh - 95px);
	overflow-y: auto;
	border-left: 1px solid var(--border-color);
	background: var(--fg-color);
	display: flex;
	flex-direction: column;
}

/* ── Header ─────────────────────────────────────────────── */
.pfb-inspector-head {
	padding: 8px 12px;
	border-bottom: 1px solid var(--border-color);
	flex-shrink: 0;
	min-height: 0;
}

.pfb-inspector-title {
	display: flex;
	align-items: center;
	gap: 6px;
	min-width: 0;
}

.pfb-inspector-kind {
	font-size: var(--text-sm);
	font-weight: var(--weight-semibold);
	white-space: nowrap;
	flex-shrink: 0;
}

.pfb-inspector-name {
	font-size: var(--text-sm);
	color: var(--text-muted);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	flex: 1;
	min-width: 0;
}

.pfb-inspector-name::before {
	content: "·";
	margin-right: 6px;
	opacity: 0.4;
}

.pfb-inspector-eyebrow-inline {
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
	color: var(--text-muted);
}

/* ── Breadcrumb ──────────────────────────────────────────── */
.pfb-breadcrumb {
	padding: 4px 10px;
	border-bottom: 1px solid var(--border-color);
	background: var(--fg-color);
}

.pfb-breadcrumb-btn {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	padding: 2px 6px;
	border: none;
	background: transparent;
	cursor: pointer;
	border-radius: var(--radius);
	color: var(--text-muted);
	font-size: var(--text-xs);
	transition: background 0.1s, color 0.1s;
	max-width: 100%;
}

.pfb-breadcrumb-btn:hover {
	background: var(--gray-100);
}

.pfb-breadcrumb-label {
	font-weight: 500;
	flex-shrink: 0;
}

.pfb-breadcrumb-name {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

/* ── Empty state ─────────────────────────────────────────── */
.pfb-inspector-empty {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 24px;
	text-align: center;
	font-size: var(--text-sm);
}

/* ── Letter Head inspector ───────────────────────────────── */
.pfb-lh-edit-btn {
	display: inline-flex;
	align-items: center;
	gap: 4px;
}

.pfb-lh-notice {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: var(--text-tiny);
	color: var(--yellow-800);
	background: var(--yellow-50);
	border-bottom: 1px solid var(--yellow-200);
	padding: 7px 14px;
	flex-shrink: 0;
	line-height: 1.4;
}

/* ── HTML field inline preview (inspector sidebar) ───────── */
.pfb-html-preview {
	font-size: var(--text-sm);
	color: var(--text-muted);
	padding: 6px 8px;
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	background: var(--gray-50);
	max-height: 100px;
	overflow: hidden;
	margin-bottom: 2px;
}
</style>

<style>
/* ── HTML split editor dialog (global — renders in modal portal) ── */
.pfb-html-split {
	display: flex;
	height: 480px;
	gap: 0;
	overflow: hidden;
	margin: -15px;
}

.pfb-html-split-pane {
	display: flex;
	flex-direction: column;
	flex: 1;
	min-width: 0;
	overflow: hidden;
}

.pfb-html-split-divider {
	width: 1px;
	background: var(--border-color);
	flex-shrink: 0;
}

.pfb-html-split-label {
	font-size: var(--text-tiny);
	font-weight: var(--weight-bold);
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--text-muted);
	padding: 10px 12px 8px;
	border-bottom: 1px solid var(--border-color);
	background: var(--gray-50);
	flex-shrink: 0;
}

.pfb-html-ctrl-host {
	flex: 1;
	overflow: hidden;
	display: flex;
	flex-direction: column;
	padding: 0 12px 12px;
}

.pfb-html-ctrl-host .frappe-control {
	flex: 1;
	display: flex;
	flex-direction: column;
	height: 100%;
}

.pfb-html-ctrl-host .form-group {
	flex: 1;
	margin: 0;
	display: flex;
	flex-direction: column;
}

.pfb-html-ctrl-host .CodeMirror {
	flex: 1;
	height: 100%;
	font-size: 13px;
	font-family: var(--monospace-font-family, monospace);
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
}

.pfb-html-ctrl-host .CodeMirror-scroll {
	height: 100%;
}

.pfb-html-preview-content {
	flex: 1;
	overflow-y: auto;
	padding: 16px 20px;
	font-size: var(--text-sm);
}
</style>
