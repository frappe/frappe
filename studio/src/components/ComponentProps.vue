<template>
	<div class="flex select-none flex-col pb-16">
		<div class="flex flex-col gap-3">
			<div v-if="!isObjectEmpty(componentProps)" v-for="(config, propName) in componentProps" :key="propName">
				<InlineInput
					:label="propName"
					:type="config.inputType"
					:modelValue="config.modelValue"
					:options="config.options"
					@update:modelValue="(val) => updateComponentProp(propName, val)"
				/>
			</div>

			<EmptyState v-else message="Select a block to edit properties" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import Block from "@/utils/block"

import { getComponentProps } from "@/utils/components"
import { isObjectEmpty } from "@/utils/helpers"
import InlineInput from "@/components/InlineInput.vue"
import EmptyState from "@/components/EmptyState.vue"

const props = defineProps<{
	block?: Block
}>()

const componentProps = computed(() => {
	if (!props.block || props.block.isRoot()) return []
	const propConfig = getComponentProps(props.block.componentName) || []
	if (!propConfig) return []

	Object.entries(propConfig).forEach(([propName, config]) => {
		if (props.block?.componentProps[propName] === undefined) {
			const defaultValue = typeof config.default === "function" ? config.default() : config.default
			config.modelValue = defaultValue
		} else {
			config.modelValue = props.block.componentProps[propName]
		}
	})

	return propConfig
})

const updateComponentProp = (propName: string, newValue: any) => {
	props.block?.setProp(propName, newValue)
}
</script>
