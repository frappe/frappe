<template>
	<StudioComponent v-if="rootBlock" :block="rootBlock" :breakpoint="props.breakpoint" />
</template>

<script setup lang="ts">
import { provide, computed } from "vue"
import StudioComponent from "@/components/StudioComponent.vue"
import Block from "@/utils/block"
import useComponentEditorStore from "@/stores/componentEditorStore"

const props = defineProps<{
	rootBlock: Block
	breakpoint?: string
}>()

const componentEditorStore = useComponentEditorStore()
const componentBlock = computed(() => componentEditorStore.studioComponentBlock!)
const componentContext = computed(() => componentBlock.value.componentProps)
provide("componentContext", componentContext)
</script>
