<template>
	<div class="flex select-none flex-col pb-16">
		<div class="flex flex-col gap-3">
			<div v-if="componentProps" v-for="(config, propName) in componentProps" :key="propName">
				<InlineInput
					:label="propName"
					:type="config.inputType"
					:modelValue="config.modelValue"
					@update:modelValue="(val) => updateComponentProp(propName, val)"
				/>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue"
import Block from "@/utils/block"

import { getComponentProps } from "@/utils/components"
import InlineInput from "@/components/InlineInput.vue"

const props = defineProps({
	block: {
		type: Block,
		required: false,
	},
})

const componentProps = computed(() => {
	if (!props.block || props.block.isRoot()) return []
	const propConfig = getComponentProps(props.block.componentName) || []

	Object.entries(propConfig).forEach(([propName, config]) => {
		if (props.block.componentProps[propName] === undefined) {
			const defaultValue = typeof config.default === "function" ? config.default() : config.default
			config.modelValue = defaultValue
		} else {
			config.modelValue = props.block.componentProps[propName]
		}
	})

	return propConfig
})

const updateComponentProp = (propName, newValue) => {
	props.block.setProp(propName, newValue)
}
</script>
