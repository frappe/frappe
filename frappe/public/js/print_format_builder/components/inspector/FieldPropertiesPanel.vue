<template>
	<div class="pfb-insp-body">
		<InspectorSection :label="__('Field')">
			<template v-if="is_html_field">
				<div
					class="pfb-html-preview"
					v-if="selected_field.html"
					v-html="selected_field.html"
				></div>
				<div v-else class="pfb-insp-hint text-muted">
					{{ __("No HTML content yet.") }}
				</div>
				<button class="es-button" data-size="xs" @click="edit_html_field">
					<span v-html="frappe.utils.icon('pencil', 'xs')"></span>
					{{ __("Edit HTML") }}
				</button>
			</template>
			<template v-else-if="is_typst_field">
				<textarea
					class="form-control form-control-sm pfb-typst-input"
					:placeholder="'#text(weight: \'bold\')[Hello]'"
					spellcheck="false"
					rows="8"
					:value="selected_field.typst || ''"
					@input="(e) => (selected_field.typst = e.target.value)"
				></textarea>
				<div class="pfb-insp-hint text-muted">
					{{ typst_hint }}
				</div>
			</template>
			<template v-else-if="is_image_element">
				<ImageUploadControl
					:model-value="selected_field.image_url"
					:alt="selected_field.label"
					@update:model-value="set_image_url"
				/>
				<div v-if="selected_field.image_url" class="pfb-insp-row pfb-insp-row--col">
					<span class="pfb-insp-label">{{ __("Size") }}</span>
					<input
						class="pfb-size-slider"
						type="range"
						min="20"
						max="700"
						:value="image_size"
						@input="selected_field.width = $event.target.value + 'px'"
					/>
				</div>
				<SegmentedRow
					:label="__('Align')"
					:model-value="current_align"
					:options="align_opts"
					@update:model-value="(v) => (selected_field.align = v)"
				/>
			</template>
			<template v-else-if="is_barcode_element">
				<div class="pfb-insp-row" v-if="selected_field.custom">
					<span class="pfb-insp-label">{{ __("Value from") }}</span>
					<select
						class="pfb-insp-select"
						:value="selected_field.barcode_field || ''"
						@change="selected_field.barcode_field = $event.target.value"
					>
						<option value="">{{ __("Static value") }}</option>
						<option v-for="f in barcode_field_options" :key="f.value" :value="f.value">
							{{ f.label }}
						</option>
					</select>
				</div>
				<div
					class="pfb-insp-row"
					v-if="selected_field.custom && !selected_field.barcode_field"
				>
					<span class="pfb-insp-label">{{ __("Value") }}</span>
					<input
						type="text"
						class="pfb-insp-input"
						:placeholder="__('Static value')"
						:value="selected_field.barcode_value"
						@change="selected_field.barcode_value = $event.target.value"
					/>
				</div>
				<div class="pfb-insp-row" v-if="selected_field.custom">
					<span class="pfb-insp-label">{{ __("Format") }}</span>
					<select
						class="pfb-insp-select"
						:value="selected_field.barcode_format || 'CODE128'"
						@change="selected_field.barcode_format = $event.target.value"
					>
						<option v-for="fmt in barcode_formats" :key="fmt" :value="fmt">
							{{ fmt }}
						</option>
					</select>
				</div>
				<div class="pfb-insp-row pfb-insp-row--col">
					<span class="pfb-insp-label">{{ __("Size") }}</span>
					<input
						class="pfb-size-slider"
						type="range"
						min="40"
						max="500"
						:value="barcode_size"
						@input="selected_field.width = $event.target.value + 'px'"
					/>
				</div>
				<div
					class="pfb-insp-row"
					v-if="selected_field.custom && selected_field.barcode_format !== 'QR'"
				>
					<span class="pfb-insp-label">{{ __("Value text") }}</span>
					<label class="pfb-insp-check">
						<input
							type="checkbox"
							:checked="selected_field.show_text !== false"
							@change="selected_field.show_text = $event.target.checked"
						/>
						{{ __("Show") }}
					</label>
				</div>
				<SegmentedRow
					:label="__('Align')"
					:model-value="current_align"
					:options="align_opts"
					@update:model-value="(v) => (selected_field.align = v)"
				/>
			</template>
			<template v-else-if="is_spacer">
				<StepperRow
					:label="__('Height')"
					:model-value="selected_field.height"
					:base="16"
					:step="4"
					unit="px"
					:placeholder="__('auto')"
					allow-empty
					@update:model-value="(v) => (selected_field.height = v)"
				/>
			</template>
			<template v-else-if="is_divider"></template>
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
				<div class="pfb-insp-row" v-if="fieldIsInline && current_align === 'left'">
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
		</InspectorSection>

		<InspectorSection :label="__('Style')" :init-open="false" :padded="false">
			<div v-if="is_text_field" class="pfb-insp-section-body">
				<ColorField
					:label="__('Label')"
					:model-value="selected_field.label_color || ''"
					@update:model-value="(v) => set_field_prop('label_color', v)"
				/>
				<ColorField
					:label="__('Value')"
					:model-value="selected_field.value_color || ''"
					@update:model-value="(v) => set_field_prop('value_color', v)"
				/>
			</div>
			<StyleSection :label="__('Custom CSS')" v-model="selected_field.custom_style" />
		</InspectorSection>

		<InspectorSection :label="__('Visibility')" :init-open="false" :padded="false">
			<VisibilitySection v-model="selected_field.visible_if" :previewDoc="preview_doc" />
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import LabelField from "./LabelField.vue";
import SegmentedRow from "./SegmentedRow.vue";
import InspectorSection from "./InspectorSection.vue";
import StepperRow from "./StepperRow.vue";
import StyleSection from "./StyleSection.vue";
import ColorField from "./ColorField.vue";
import VisibilitySection from "./VisibilitySection.vue";
import ImageUploadControl from "./ImageUploadControl.vue";
import { get_image_dimensions } from "../../utils";
import { align_opts } from "./align_opts";
import { useSelectedField } from "./useSelectedField";

defineProps(["fieldIsInline"]);

const { selected_field, preview_doc, set_field_prop } = useSelectedField();

// Fieldtypes rendered as a label/value pair that a text colour can target
const NON_TEXT_FIELDTYPES = new Set([
	"HTML",
	"Image",
	"Barcode",
	"Spacer",
	"Divider",
	"Field Template",
]);
let is_text_field = computed(() => !NON_TEXT_FIELDTYPES.has(selected_field.value?.fieldtype));

let is_html_field = computed(() => selected_field.value?.fieldtype === "HTML");
let is_typst_field = computed(() => selected_field.value?.fieldtype === "Typst");
let typst_hint = __(
	"Write Typst here. Use {0} for values from the document. Check the PDF preview to see the result.",
	["{{ doc.field_name }}"]
);
// a spacer prints a gap and a divider a rule — neither carries a label to align
let is_spacer = computed(() => selected_field.value?.fieldtype === "Spacer");
let is_divider = computed(() => selected_field.value?.fieldtype === "Divider");
let is_image_element = computed(
	() => selected_field.value?.fieldtype === "Image" && selected_field.value?.custom
);
// dragged Barcode docfields get size/align only — value and format come from
// the field itself
let is_barcode_element = computed(() => selected_field.value?.fieldtype === "Barcode");

// QR comes from Barcode docfields with qrcode options, not the block; the
// option stays visible only on elements saved as QR before that change
const barcode_formats = computed(() =>
	selected_field.value?.barcode_format === "QR"
		? ["CODE128", "CODE39", "QR"]
		: ["CODE128", "CODE39"]
);

let store = inject("$store");

let barcode_field_options = computed(() => {
	const fields = store.meta.value?.fields || [];
	return [
		{ label: __("ID (name)"), value: "name" },
		...fields
			.filter((f) => !frappe.model.no_value_type.includes(f.fieldtype))
			.map((f) => ({ label: f.label || f.fieldname, value: f.fieldname })),
	];
});

let image_size = computed(() => parseFloat(selected_field.value?.width) || 200);
let barcode_size = computed(
	() =>
		parseFloat(selected_field.value?.width) ||
		(selected_field.value?.barcode_format === "QR" ? 130 : 200)
);

function set_image_url(url) {
	selected_field.value.image_url = url;
	if (!url) {
		selected_field.value.width = "";
		return;
	}
	get_image_dimensions(url)
		.then(({ width }) => {
			if (!parseFloat(selected_field.value.width)) {
				selected_field.value.width = Math.min(width, 300) + "px";
			}
		})
		.catch(() => {});
}

let current_align = computed(() => selected_field.value?.align ?? "left");
let current_label_justify = computed(() => selected_field.value?.label_justify ?? "");

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
