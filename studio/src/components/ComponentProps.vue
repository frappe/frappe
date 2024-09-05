<template>
	<div class="flex select-none flex-col pb-16">
		<div class="flex flex-col gap-3">
			<div v-if="componentProps" v-for="(config, propName) in componentProps" :key="propName">
				<InlineInput :label="propName" :type="config.inputType" :modelValue="config.default" />
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
	return getComponentProps(props.block.componentName)
})
</script>
