<template>
	<span :class="{ baseSpanTag: !field.is_static && field.is_labelled }">
		<span
			v-if="!field.is_static && field.is_labelled"
			class="label-text dynamicText labelSpanTag"
			:class="{
				'label-text-selected':
					MainStore.activeControl == 'text' && selectedDyanmicText.indexOf(field) != -1,
			}"
			v-html="
				field.label ||
				`{{ ${field.parentField ? field.parentField + '.' : ''}${field.fieldname} }}`
			"
		></span>
		<span
			class="dynamicText"
			:class="[
				'dynamic-span',
				{
					'dynamic-span-hover': MainStore.activeControl == 'text',
					'dynamic-span-selected':
						MainStore.activeControl == 'text' &&
						selectedDyanmicText.indexOf(field) != -1,
				},
				{ valueSpanTag: !field.is_static && field.is_labelled },
			]"
			@click="selectDyanmicText($event)"
			:style="[field?.style, 'cursor: default;']"
			v-html="
				field.value ||
				`{{ ${field.parentField ? field.parentField + '.' : ''}${field.fieldname} }}`
			"
		>
		</span>
		<br v-if="field.nextLine" />
	</span>
</template>

<script setup>
import { useMainStore } from "../../store/MainStore";

const selectDyanmicText = (event) => {
	if (MainStore.activeControl != "text") return;
	props.selectedDyanmicText.length = 0;
	props.selectedDyanmicText.push(props.field);
};

const MainStore = useMainStore();
const props = defineProps({
	field: {
		type: Object,
		required: true,
	},
	selectedDyanmicText: {
		type: Array,
		required: true,
	},
	index: {
		type: Number,
		required: true,
	},
});
</script>

<style lang="scss" scoped>
.dynamic-span {
	padding: 1px !important;
}
.dynamic-span-hover:hover:not(.dynamic-span-selected) {
	padding: 0px !important;
	border: 1px solid var(--gray-400) !important;
}
.dynamic-span-selected {
	padding: 0px !important;
	border: 1px solid black !important;
}
</style>
