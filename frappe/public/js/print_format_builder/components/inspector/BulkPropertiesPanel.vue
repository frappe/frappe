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
import { align_opts } from "./align_opts";

let store = inject("$store");

let field_count = computed(() => store.selected_fields.value.length);
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
