<template>
	<div class="pfb-insp-body">
		<InspectorSection :label="__('Repeater')">
			<div class="pfb-insp-row">
				<span class="pfb-insp-label">{{ __("Source") }}</span>
				<Autocomplete
					:options="repeater_source_opts"
					:model-value="selected_field.source || ''"
					:placeholder="__('Select table…')"
					@select="(o) => (selected_field.source = o.value)"
				/>
			</div>
			<LabelField
				v-model="selected_field.label"
				:label="__('Title')"
				:placeholder="__('Optional heading')"
				show-toggle
				:show-label="__('Show title')"
				:show="selected_field.show_label"
				@update:show="(v) => (selected_field.show_label = v)"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Columns')">
			<div
				v-for="(col, ci) in selected_field.repeater_columns"
				:key="ci"
				class="pfb-rep-col"
			>
				<div class="pfb-rep-col-head">
					<span class="pfb-insp-label">{{ __("Column {0}", [ci + 1]) }}</span>
					<div class="pfb-rep-col-head-actions">
						<input
							class="pfb-col-width-input"
							type="number"
							min="5"
							max="100"
							v-model.number="col.width"
							@blur="clamp_repeater_width(col)"
							:placeholder="__('auto')"
							:title="__('Width %')"
						/>
						<span class="pfb-col-width-unit">%</span>
						<button
							class="es-button"
							data-size="xs"
							data-variant="ghost"
							data-icon-button="true"
							:title="__('Remove column')"
							@click="remove_repeater_column(ci)"
							v-html="frappe.utils.icon('x', 'xs')"
						></button>
					</div>
				</div>
				<TemplateInput v-model="col.template" :fields="repeater_field_opts" />
				<SegmentedRow
					:label="__('Align')"
					v-model="col.align"
					:options="align_opts"
					style="margin-top: 8px"
				/>
				<div class="pfb-insp-row" style="margin-top: 8px">
					<span class="pfb-insp-label">{{ __("Color") }}</span>
					<div class="pfb-rep-col-color" :ref="(el) => (rep_color_hosts[ci] = el)"></div>
				</div>
			</div>
			<button class="pfb-add-btn" @click="add_repeater_column">
				<span v-html="frappe.utils.icon('plus', 'xs')"></span>
				{{ __("Add column") }}
			</button>
		</InspectorSection>

		<InspectorSection :label="__('Style')" :init-open="false" :padded="false">
			<StyleSection v-model="selected_field.custom_style" />
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from "vue";
import { useStore } from "../../stores";
import Autocomplete from "../../../vue-components/Autocomplete.vue";
import LabelField from "./LabelField.vue";
import TemplateInput from "./TemplateInput.vue";
import SegmentedRow from "./SegmentedRow.vue";
import InspectorSection from "./InspectorSection.vue";
import StyleSection from "./StyleSection.vue";
import { mountColorControl } from "./useColorControl";
import { align_opts } from "./align_opts";
import { useSelectedField } from "./useSelectedField";

let { meta } = useStore();
const { selected_field } = useSelectedField();

let repeater_source_opts = computed(() =>
	(meta.value?.fields || [])
		.filter((f) => f.fieldtype === "Table")
		.map((f) => ({ value: f.fieldname, label: f.label || f.fieldname }))
);

let repeater_field_opts = computed(() => {
	const src = (meta.value?.fields || []).find(
		(f) => f.fieldname === selected_field.value?.source
	);
	const child_meta = src?.options ? frappe.get_meta(src.options) : null;
	if (!child_meta) return [];
	return child_meta.fields
		.filter((f) => !frappe.model.no_value_type.includes(f.fieldtype) && f.fieldname !== "name")
		.map((f) => ({ value: f.fieldname, label: f.label || f.fieldname }));
});

function add_repeater_column() {
	if (!selected_field.value.repeater_columns) selected_field.value.repeater_columns = [];
	selected_field.value.repeater_columns.push({ template: [], align: "left" });
}

function remove_repeater_column(i) {
	selected_field.value.repeater_columns.splice(i, 1);
}

function clamp_width(col) {
	col.width = Math.max(5, Math.min(100, parseInt(col.width) || 10));
}

function clamp_repeater_width(col) {
	if (isNaN(parseInt(col.width))) {
		delete col.width;
		return;
	}
	clamp_width(col);
}

const rep_color_hosts = ref({});

function mount_repeater_color_controls() {
	(selected_field.value?.repeater_columns || []).forEach((col, ci) => {
		mountColorControl(rep_color_hosts.value[ci], {
			value: col.color || "",
			placeholder: __("Default"),
			fieldname: `repeater_col_color_${ci}`,
			onChange(value) {
				if ((col.color ?? "") !== value) {
					col.color = value;
				}
			},
		});
	});
}

watch(
	() => [selected_field.value, selected_field.value?.repeater_columns?.length],
	() => nextTick(mount_repeater_color_controls),
	{ immediate: true }
);
</script>

<style scoped>
.pfb-rep-col {
	border: 1px solid var(--border-color);
	border-radius: var(--radius);
	padding: 8px;
	margin-bottom: 8px;
}
.pfb-rep-col-head {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin-bottom: 6px;
}
.pfb-rep-col-head-actions {
	display: flex;
	align-items: center;
	gap: 4px;
}
</style>
