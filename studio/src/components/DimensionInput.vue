<!-- Extracted from Builder -->
<template>
	<InlineInput
		type="autocomplete"
		:label="label"
		:enableSlider="true"
		:options="[
			{
				label: 'Auto',
				value: 'auto',
			},
			{
				label: 'Fit Content',
				value: 'fit-content',
			},
			{
				label: 'Stretch',
				value: '100%',
			},
		]"
		:modelValue="blockController.getStyle(props.property)"
		:unitOptions="['px', '%', 'vw', 'vh']"
		@update:modelValue="(val) => blockController.setStyle(property, val)"
	></InlineInput>
</template>

<script setup lang="ts">
import InlineInput from "@/components/InlineInput.vue"
import { styleProperty } from "@/utils/block"
import blockController from "@/utils/blockController"

const props = defineProps<{
	property: styleProperty
	label: string
}>()
</script>
