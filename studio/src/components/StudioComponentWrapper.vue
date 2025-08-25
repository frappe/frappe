<template>
	<StudioComponent v-if="block" :block="block" :breakpoint="props.breakpoint" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import { useStudioComponents } from "@/utils/useStudioComponents"

const props = defineProps<{
	studioComponentId: string
	studioComponentName: string
	breakpoint?: string
}>()
const block = ref<Block | undefined>()

const { getComponent } = useStudioComponents()

watch(
	() => props.studioComponentName,
	async () => {
		block.value = await getComponent(props.studioComponentName)
		if (!block.value) {
			console.error(`Component with ID ${props.studioComponentName} not found`)
			return
		}
		block.value.componentId = props.studioComponentId
	},
	{ immediate: true },
)
</script>
