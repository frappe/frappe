<template>
	<div class="pfb-insp-body">
		<InspectorSection :label="__('{0} fields selected', [count])">
			<SegmentedRow
				:label="__('Align')"
				:model-value="common_align"
				:options="align_opts"
				@update:model-value="(v) => store.align_selected_fields(v)"
			/>
			<div class="pfb-insp-row">
				<button
					class="es-button pfb-bulk-delete"
					data-variant="ghost"
					data-theme="red"
					@click="store.remove_selected_fields()"
				>
					<span v-html="frappe.utils.icon('trash', 'sm')"></span>
					{{ __("Remove selected") }}
				</button>
			</div>
		</InspectorSection>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";
import InspectorSection from "./InspectorSection.vue";
import SegmentedRow from "./SegmentedRow.vue";
import { align_opts } from "./align_opts";

let store = inject("$store");

let count = computed(() => store.selected_fields.value.length);
let common_align = computed(() => {
	const aligns = store.selected_fields.value.map((df) => df.align || "left");
	const first = aligns[0];
	return aligns.every((a) => a === first) ? first : "";
});
</script>

<style scoped>
.pfb-bulk-delete {
	width: 100%;
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 6px;
}
</style>
