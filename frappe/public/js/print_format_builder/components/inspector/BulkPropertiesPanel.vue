<template>
	<div class="pfb-insp-body">
		<InspectorSection :label="__('{0} selected', [label])">
			<SegmentedRow
				v-if="field_count"
				:label="__('Align')"
				:model-value="common_align"
				:options="align_opts"
				@update:model-value="(v) => store.align_selected_fields(v)"
			/>
			<template v-if="field_count">
				<ToggleRow
					:label="__('Show label')"
					:model-value="all_have('show_label', (v) => v !== 'hide')"
					@update:model-value="(v) => apply('show_label', v ? 'show' : 'hide')"
				/>
				<ToggleRow
					:label="__('Bold')"
					:model-value="all_have('bold', (v) => !!v)"
					@update:model-value="(v) => apply('bold', v ? 1 : 0)"
				/>
				<StepperRow
					:label="__('Font size')"
					:model-value="first_value('font_size')"
					:base="13"
					:step="1"
					unit="px"
					:placeholder="__('auto')"
					allow-empty
					@update:model-value="(v) => apply('font_size', v)"
				/>
				<ColorField
					:label="__('Label colour')"
					:model-value="first_value('label_color') || ''"
					@update:model-value="(v) => apply('label_color', v)"
				/>
				<ColorField
					:label="__('Value colour')"
					:model-value="first_value('value_color') || ''"
					@update:model-value="(v) => apply('value_color', v)"
				/>
			</template>
			<button
				class="es-button pfb-bulk-remove"
				data-variant="subtle"
				data-theme="red"
				@click="store.remove_selection()"
			>
				{{ __("Remove selected") }}
			</button>
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import InspectorSection from "./InspectorSection.vue";
import SegmentedRow from "./SegmentedRow.vue";
import ToggleRow from "./ToggleRow.vue";
import StepperRow from "./StepperRow.vue";
import ColorField from "./ColorField.vue";
import { align_opts } from "./align_opts";

let store = inject("$store");

let field_count = computed(() => store.selected_fields.value.length);
function apply(key, value) {
	store.selected_fields.value.forEach((df) => (df[key] = value));
}
function all_have(key, test) {
	return store.selected_fields.value.every((df) => test(df[key]));
}
function first_value(key) {
	return store.selected_fields.value[0]?.[key];
}
let section_count = computed(() => store.selected_sections.value.length);
let label = computed(() =>
	section_count.value
		? __("{0} items", [field_count.value + section_count.value])
		: __("{0} fields", [field_count.value])
);
let common_align = computed(() => {
	const aligns = store.selected_fields.value.map((df) => df.align || "left");
	const first = aligns[0];
	return aligns.every((a) => a === first) ? first : "";
});
</script>

<style scoped>
.pfb-bulk-remove {
	align-self: flex-start;
}
</style>
