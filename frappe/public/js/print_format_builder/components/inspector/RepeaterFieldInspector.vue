<template>
	<div class="pfb-insp-body">
		<InspectorSection :label="__('Custom Table')">
			<SelectRow
				:label="__('Source')"
				:model-value="selected_field.source"
				:options="repeater_source_opts"
				:placeholder="__('Select table…')"
				@update:model-value="(v) => (selected_field.source = v)"
			/>
			<template v-if="selected_field.source">
				<LabelField
					v-model="selected_field.label"
					:label="__('Title')"
					:placeholder="__('Optional heading')"
					show-toggle
					:show-label="__('Show title')"
					:show="selected_field.show_label"
					@update:show="(v) => (selected_field.show_label = v)"
				/>
			</template>
		</InspectorSection>

		<InspectorSection v-if="selected_field.source" :label="__('Columns')" :padded="false">
			<draggable
				:list="selected_field.repeater_columns"
				handle=".pfb-col-drag"
				:animation="150"
				:item-key="(col) => selected_field.repeater_columns.indexOf(col)"
				class="pfb-col-list"
			>
				<template #item="{ element: col, index: ci }">
					<div class="pfb-col-item">
						<div class="pfb-col-row">
							<span
								class="pfb-col-drag"
								v-html="frappe.utils.icon('grip', 'xs')"
							></span>
							<TemplateInput v-model="col.template" :fields="repeater_field_opts" />
							<button
								class="es-button"
								data-size="xs"
								data-icon-button="true"
								:data-variant="expanded_col === ci ? 'subtle' : 'ghost'"
								:title="__('Column settings')"
								@click="expanded_col = expanded_col === ci ? null : ci"
								v-html="frappe.utils.icon('settings-2', 'xs')"
							></button>
							<button
								class="es-button"
								data-size="xs"
								data-variant="ghost"
								data-theme="red"
								data-icon-button="true"
								:title="__('Remove column')"
								@click="remove_repeater_column(ci)"
								v-html="frappe.utils.icon('x', 'xs')"
							></button>
						</div>
						<div
							v-if="expanded_col === ci"
							class="pfb-col-editor pfb-insp-section-body"
						>
							<StepperRow
								:label="__('Width')"
								:model-value="col.width ?? null"
								:min="5"
								:step="5"
								unit="%"
								:placeholder="__('auto')"
								allow-empty
								@update:model-value="(v) => set_width(col, v)"
							/>
							<SegmentedRow
								:label="__('Align')"
								v-model="col.align"
								:options="align_opts"
							/>
							<ColorField :label="__('Colour')" v-model="col.color" />
						</div>
					</div>
				</template>
			</draggable>
			<div class="pfb-col-add-row">
				<button class="pfb-add-btn" @click="add_repeater_column">
					<span v-html="frappe.utils.icon('plus', 'xs')"></span>
					{{ __("Add column") }}
				</button>
			</div>
		</InspectorSection>

		<InspectorSection :label="__('Style')" :init-open="false" :padded="false">
			<StyleSection v-model="selected_field.custom_style" />
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import draggable from "vuedraggable";
import SelectRow from "./SelectRow.vue";
import LabelField from "./LabelField.vue";
import TemplateInput from "./TemplateInput.vue";
import SegmentedRow from "./SegmentedRow.vue";
import StepperRow from "./StepperRow.vue";
import ColorField from "./ColorField.vue";
import InspectorSection from "./InspectorSection.vue";
import StyleSection from "./StyleSection.vue";
import { align_opts } from "./align_opts";
import { useSelectedField } from "./useSelectedField";
import { table_field_opts, value_field_opts } from "../../utils";

let { meta } = inject("$store");
const { selected_field } = useSelectedField();

let repeater_source_opts = computed(() => table_field_opts(meta.value?.fields));

let repeater_field_opts = computed(() => {
	const src = (meta.value?.fields || []).find(
		(f) => f.fieldname === selected_field.value?.source
	);
	const child_meta = src?.options ? frappe.get_meta(src.options) : null;
	return value_field_opts(child_meta?.fields).filter((o) => o.value !== "name");
});

function add_repeater_column() {
	if (!selected_field.value.repeater_columns) selected_field.value.repeater_columns = [];
	selected_field.value.repeater_columns.push({ template: [], align: "left" });
}

function remove_repeater_column(i) {
	selected_field.value.repeater_columns.splice(i, 1);
}

const expanded_col = ref(null);

function set_width(col, value) {
	if (value == null) {
		delete col.width;
		return;
	}
	col.width = Math.max(5, Math.min(100, parseInt(value) || 10));
}
</script>
