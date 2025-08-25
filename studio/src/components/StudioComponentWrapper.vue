<template>
	<StudioComponent v-if="block" :block="block" :breakpoint="props.breakpoint" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import { useStudioComponents } from "@/utils/useStudioComponents"

const props = defineProps<{
	componentBlock: Block
	breakpoint?: string
}>()
const block = ref<Block | undefined>()

const { getComponent } = useStudioComponents()
watch(
	() => props.componentBlock.componentId,
	async () => {
		const { componentId, componentName } = props.componentBlock
		block.value = await getComponent(componentName)
		if (!block.value) {
			console.error(`Component with ID ${componentName} not found`)
			return
		}
		block.value.initializeStudioComponent(componentName, componentId)
	},
	{ immediate: true },
)
</script>
