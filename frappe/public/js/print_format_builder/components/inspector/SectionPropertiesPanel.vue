<template>
	<div class="pfb-insp-body">
		<InspectorSection :label="__('Section')">
			<LabelField
				v-model="selected_section.label"
				:label="__('Title')"
				:placeholder="__('Untitled section')"
				show-toggle
				:show-label="__('Show title')"
				:show="selected_section.show_label"
				@update:show="(v) => (selected_section.show_label = v)"
			/>

			<SegmentedRow
				:label="__('Columns')"
				:model-value="selected_section.columns.length"
				:options="[1, 2, 3, 4].map((n) => ({ value: n, label: n }))"
				@update:model-value="set_columns"
			/>

			<SegmentedRow
				:label="__('Label side')"
				:model-value="section_orientation === 'left-right' ? 'left-right' : 'top'"
				:options="[
					{ value: 'top', label: __('Top') },
					{ value: 'left-right', label: __('Left') },
				]"
				@update:model-value="
					(v) =>
						(selected_section.field_orientation =
							v === 'left-right' ? 'left-right' : '')
				"
			/>

			<StepperRow
				:label="__('Gap')"
				:model-value="section_gap"
				:step="4"
				:base="20"
				unit="px"
				@update:model-value="(v) => (selected_section.gap = v)"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Background')" :init-open="false">
			<div ref="bg_color_host"></div>
			<StepperRow
				v-if="section_has_box"
				:label="__('Radius')"
				:model-value="section_radius"
				unit="px"
				:placeholder="__('none')"
				allow-empty
				@update:model-value="set_section_radius"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Spacing')" :init-open="false">
			<SpacingRow
				v-for="prop in spacing_props"
				:key="prop.key"
				:label="prop.label"
				:model-value="selected_section[prop.key]"
				@update:model-value="(v) => (selected_section[prop.key] = v)"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Layout')" :init-open="false">
			<div class="pfb-insp-row">
				<span class="pfb-insp-label">{{ __("Justify") }}</span>
				<select
					class="pfb-insp-select"
					:value="section_justify"
					@change="set_justify($event.target.value)"
				>
					<option value="">{{ __("Normal") }}</option>
					<option v-for="mode in Object.keys(JUSTIFY_CLASSES)" :key="mode" :value="mode">
						{{ justify_labels[mode] }}
					</option>
				</select>
			</div>
			<SegmentedRow
				:label="__('Mode')"
				:model-value="section_field_borders"
				:options="[
					{ value: false, label: __('Normal') },
					{ value: true, label: __('Table') },
				]"
				@update:model-value="toggle_field_borders"
			/>
			<SegmentedRow
				v-if="section_field_borders"
				:label="__('Borders')"
				:model-value="selected_section.grid_borders || 'all'"
				:options="[
					{ value: 'all', label: __('All') },
					{ value: 'rows', label: __('Rows') },
					{ value: 'columns', label: __('Columns') },
				]"
				@update:model-value="set_grid_borders"
			/>
			<StepperRow
				:label="__('Cell padding')"
				:model-value="section_cell_padding"
				:base="8"
				unit="px"
				@update:model-value="(v) => (selected_section.cell_padding = v)"
			/>
			<ColorField
				v-if="section_field_borders"
				:label="__('Border color')"
				:model-value="selected_section.border_color || ''"
				@update:model-value="(v) => set_section_prop('border_color', v)"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Print')" :init-open="false">
			<ToggleRow
				:label="__('Keep together')"
				:model-value="!!selected_section.keep_together"
				@update:model-value="(v) => (selected_section.keep_together = v)"
			/>
		</InspectorSection>

		<InspectorSection :label="__('Style')" :init-open="false" :padded="false">
			<StyleSection v-model="selected_section.custom_style" />
		</InspectorSection>

		<InspectorSection :label="__('Visibility')" :init-open="false" :padded="false">
			<VisibilitySection v-model="selected_section.visible_if" :previewDoc="preview_doc" />
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, ref, watch } from "vue";
import LabelField from "./LabelField.vue";
import SegmentedRow from "./SegmentedRow.vue";
import InspectorSection from "./InspectorSection.vue";
import StepperRow from "./StepperRow.vue";
import SpacingRow from "./SpacingRow.vue";
import StyleSection from "./StyleSection.vue";
import ToggleRow from "./ToggleRow.vue";
import ColorField from "./ColorField.vue";
import VisibilitySection from "./VisibilitySection.vue";
import { mountColorControl } from "./useColorControl";
import { JUSTIFY_CLASSES } from "../../utils";

let store = inject("$store");

let selected_section = computed(() => store.selected_section.value);

const spacing_props = [
	{ key: "padding", label: __("Padding") },
	{ key: "margin", label: __("Margin") },
];
let preview_doc = computed(() => store.preview_doc.value);

const justify_labels = {
	"space-between": __("Space Between"),
	"space-evenly": __("Space Evenly"),
	center: __("Center"),
	"right-end": __("Right"),
};

let section_justify = computed(() => selected_section.value?.justify ?? "");

function set_justify(value) {
	if (value) {
		selected_section.value.justify = value;
	} else {
		delete selected_section.value.justify;
	}
}

let section_orientation = computed(() => selected_section.value?.field_orientation ?? "");
let section_gap = computed(() => selected_section.value?.gap ?? 20);
let section_field_borders = computed(() => !!selected_section.value?.field_borders);
let section_cell_padding = computed(() => selected_section.value?.cell_padding ?? 8);
let section_radius = computed(() => selected_section.value?.radius ?? null);
let section_has_box = computed(
	() => !!(selected_section.value?.background || selected_section.value?.field_borders)
);

function set_section_radius(v) {
	if (v === null) delete selected_section.value.radius;
	else selected_section.value.radius = v;
}

const bg_color_host = ref(null);

function mount_bg_color_control() {
	mountColorControl(bg_color_host.value, {
		value: selected_section.value?.background || "",
		placeholder: __("Transparent"),
		fieldname: "section_background",
		onChange(value) {
			if ((selected_section.value?.background ?? "") !== value) {
				selected_section.value.background = value;
			}
		},
	});
}

watch(selected_section, () => nextTick(mount_bg_color_control), { immediate: true });

function set_columns(n) {
	if (!selected_section.value) return;
	const current = selected_section.value.columns.length;
	if (n === current) return;
	const all_fields = selected_section.value.columns.flatMap((col) => col.fields);
	const new_columns = Array.from({ length: n }, () => ({ label: "", fields: [] }));
	all_fields.forEach((field, i) => new_columns[i % n].fields.push(field));
	selected_section.value.columns = new_columns;
}

function toggle_field_borders(on) {
	if (on) {
		selected_section.value.field_borders = true;
	} else {
		delete selected_section.value.field_borders;
		delete selected_section.value.grid_borders;
	}
}

function set_grid_borders(v) {
	if (v === "all") {
		delete selected_section.value.grid_borders;
	} else {
		selected_section.value.grid_borders = v;
	}
}

function set_section_prop(key, value) {
	if (value) {
		selected_section.value[key] = value;
	} else {
		delete selected_section.value[key];
	}
}
</script>
