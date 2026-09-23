<template>
	<div class="pfb-insp-body">
		<InspectorSection :label="__('Section')">
			<LabelField
				v-if="!is_zone"
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
				:model-value="selected_section.field_orientation || 'top'"
				:options="[
					{ value: 'top', label: __('Top') },
					{ value: 'left-right', label: __('Left') },
				]"
				@update:model-value="(v) => set('field_orientation', v, 'top')"
			/>

			<StepperRow
				:label="__('Gap')"
				:model-value="selected_section.gap ?? 20"
				:step="4"
				:base="20"
				unit="px"
				@update:model-value="(v) => (selected_section.gap = v)"
			/>
		</InspectorSection>

		<template v-if="!is_zone">
			<InspectorSection :label="__('Background')" :init-open="false">
				<ColorField
					:label="__('Color')"
					:placeholder="__('Transparent')"
					:model-value="selected_section.background || ''"
					@update:model-value="(v) => set('background', v)"
				/>
				<StepperRow
					v-if="selected_section.background || selected_section.field_borders"
					:label="__('Radius')"
					:model-value="selected_section.radius ?? null"
					unit="px"
					:placeholder="__('none')"
					allow-empty
					@update:model-value="(v) => set('radius', v)"
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

			<InspectorSection :label="__('Borders')" :init-open="false">
				<ToggleRow
					:label="__('Field borders')"
					:model-value="!!selected_section.field_borders"
					@update:model-value="toggle_field_borders"
				/>
				<template v-if="selected_section.field_borders">
					<DropdownRow
						:label="__('Grid lines')"
						stacked
						:model-value="selected_section.grid_borders || 'all'"
						:options="grid_opts"
						@update:model-value="(v) => set('grid_borders', v, 'all')"
					/>
					<StepperRow
						:label="__('Cell padding')"
						:model-value="selected_section.cell_padding ?? 8"
						:base="8"
						unit="px"
						@update:model-value="(v) => (selected_section.cell_padding = v)"
					/>
					<ColorField
						:label="__('Border color')"
						:model-value="selected_section.border_color || ''"
						@update:model-value="(v) => set('border_color', v)"
					/>
				</template>
			</InspectorSection>

			<InspectorSection :label="__('Print')" :init-open="false">
				<ToggleRow
					:label="__('Keep together')"
					:model-value="!!selected_section.keep_together"
					@update:model-value="(v) => set('keep_together', v, false)"
				/>
			</InspectorSection>

			<InspectorSection :label="__('Style')" :init-open="false" :padded="false">
				<StyleSection v-model="selected_section.custom_style" />
			</InspectorSection>

			<InspectorSection :label="__('Visibility')" :init-open="false" :padded="false">
				<VisibilitySection v-model="selected_section.visible_if" />
			</InspectorSection>
		</template>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import LabelField from "./LabelField.vue";
import SegmentedRow from "./SegmentedRow.vue";
import InspectorSection from "./InspectorSection.vue";
import StepperRow from "./StepperRow.vue";
import SpacingRow from "./SpacingRow.vue";
import StyleSection from "./StyleSection.vue";
import ToggleRow from "./ToggleRow.vue";
import ColorField from "./ColorField.vue";
import DropdownRow from "./DropdownRow.vue";
import VisibilitySection from "./VisibilitySection.vue";
import { set_prop } from "../../utils";
import { zone_of } from "../../layout";

const store = inject("$store");
const selected_section = computed(() => store.selected_section.value);
const is_zone = computed(() => !!zone_of(store.layout.value, selected_section.value));

const spacing_props = [
	{ key: "padding", label: __("Padding") },
	{ key: "margin", label: __("Margin") },
];
const grid_opts = [
	{ value: "all", label: __("Both") },
	{ value: "rows", label: __("Rows") },
	{ value: "columns", label: __("Columns") },
];

const set = (key, value, fallback) => set_prop(selected_section.value, key, value, fallback);

function set_columns(n) {
	const columns = selected_section.value.columns;
	if (n === columns.length) return;
	const kept = columns.slice(0, n);
	columns.slice(n).forEach((col) => kept[n - 1].fields.push(...col.fields));
	while (kept.length < n) kept.push({ label: "", fields: [] });
	kept.forEach((col) => delete col.width);
	selected_section.value.columns = kept;
}

function toggle_field_borders(on) {
	set("field_borders", on, false);
	if (!on) set("grid_borders", null);
}
</script>
