<template>
	<StudioComponent v-if="block" :block="block" />
</template>

<script setup lang="ts">
import { watch, ref } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import { useStudioComponents } from "@/utils/useStudioComponents"

const props = defineProps<{ studioComponentId: string }>()
const block = ref<Block | undefined>()

const { getComponent } = useStudioComponents()

watch(
	() => props.studioComponentId,
	async () => {
		block.value = await getComponent(props.studioComponentId)
		if (!block.value) {
			console.error(`Component with ID ${props.studioComponentId} not found`)
		}
	},
	{ immediate: true },
)
</script>
