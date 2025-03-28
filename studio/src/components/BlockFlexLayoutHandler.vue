<!-- Extracted from Builder -->
<template>
	<OptionToggle
		label="Direction"
		v-if="blockController.isFlex()"
		:options="[
			{ label: 'Horizontal', value: 'row', icon: 'arrow-right', hideLabel: true },
			{ label: 'Vertical', value: 'column', icon: 'arrow-down', hideLabel: true },
		]"
		:modelValue="blockController.getStyle('flexDirection')"
		@update:modelValue="(val: string | number) => blockController.setStyle('flexDirection', val)"
	></OptionToggle>
	<PlacementControl v-if="blockController.isFlex()"></PlacementControl>
	<InlineInput
		v-if="blockController.isFlex()"
		:modelValue="blockController.getStyle('justifyContent') ?? ''"
		type="select"
		label="Distribution"
		:options="[
			{ label: '', value: '' },
			{ label: 'Space Between', value: 'space-between' },
			{ label: 'Space Around', value: 'space-around' },
			{ label: 'Space Evenly', value: 'space-evenly' },
		]"
		@update:modelValue="(val: string | number) => blockController.setStyle('justifyContent', val)"
	/>

	<InlineInput
		label="Gap"
		v-if="blockController.isFlex()"
		type="text"
		:enableSlider="true"
		:unitOptions="['px', 'em', 'rem']"
		:modelValue="blockController.getStyle('gap') ?? '0px'"
		@update:modelValue="(val: string | number) => blockController.setStyle('gap', val)"
	/>
	<OptionToggle
		label="Wrap"
		v-if="blockController.isFlex()"
		:options="[
			{ label: 'No Wrap', value: 'nowrap' },
			{ label: 'Wrap', value: 'wrap' },
		]"
		:modelValue="blockController.getStyle('flexWrap') || 'nowrap'"
		@update:modelValue="(val: string | number) => blockController.setStyle('flexWrap', val)"
	></OptionToggle>
	<div class="flex flex-col gap-3" v-if="blockController.getParentBlock()?.isFlex()">
		<OptionToggle
			label="Grow"
			:options="[
				{ label: 'Yes', value: 1 },
				{ label: 'No', value: 0 },
			]"
			:modelValue="blockController.getStyle('flexGrow') || 0"
			@update:modelValue="(val: string | number) => blockController.setStyle('flexGrow', val)"
		></OptionToggle>
		<OptionToggle
			label="Shrink"
			:options="[
				{ label: 'Yes', value: 1 },
				{ label: 'No', value: 0 },
			]"
			:modelValue="blockController.getStyle('flexShrink') ?? 0"
			@update:modelValue="(val: string | number) => blockController.setStyle('flexShrink', val)"
		></OptionToggle>
	</div>
</template>
<script lang="ts" setup>
import InlineInput from "@/components/InlineInput.vue"
import OptionToggle from "@/components/OptionToggle.vue"
import blockController from "@/utils/blockController"
import PlacementControl from "@/components/PlacementControl.vue"
</script>
