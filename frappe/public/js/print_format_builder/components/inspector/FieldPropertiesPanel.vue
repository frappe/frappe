<template>
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
					<div
						class="pfb-source-display d-flex align-items-center justify-content-between"
					>
						<span class="ellipsis" style="min-width: 0">{{
							selected_field.label || selected_field.fieldname
						}}</span>
						<span class="badge badge-light flex-shrink-0">{{ short_fieldtype }}</span>
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
						class="btn btn-xs btn-default d-inline-flex align-items-center"
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
					<div class="pfb-insp-row" v-if="fieldIsInline">
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
						v-if="fieldIsInline"
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
				<VisibilitySection v-model="selected_field.visible_if" :previewDoc="preview_doc" />
			</div>
		</div>

		<div class="pfb-insp-actions">
			<button class="btn btn-xs text-danger" @click="remove_field">
				<span v-html="frappe.utils.icon('x', 'xs')"></span>
				{{ __("Remove field") }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import LabelField from "./LabelField.vue";
import SegmentedRow from "./SegmentedRow.vue";
import StepperRow from "./StepperRow.vue";
import StyleSection from "./StyleSection.vue";
import VisibilitySection from "./VisibilitySection.vue";
import { align_opts } from "./align_opts";

defineProps(["fieldIsInline"]);

let store = inject("$store");

let selected_field = computed(() => store.selected_field.value);
let preview_doc = computed(() => store.preview_doc.value);

const open = ref({
	f_field: true,
	f_style: false,
	f_visibility: false,
});

function toggle(key) {
	open.value[key] = !open.value[key];
}

let is_html_field = computed(() => selected_field.value?.fieldtype === "HTML");

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

		if (preview) preview.innerHTML = initial_html || "";

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
