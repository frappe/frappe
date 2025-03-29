<template>
	<slot />
</template>

<script setup lang="ts">
import { provide, reactive } from "vue"

const props = defineProps<{
	item: any
	index: number
	dataKey: string
}>()

const context = reactive({
	item: props.item,
	index: props.index,
	dataKey: props.dataKey,
})

provide("repeaterContext", context)
</script>
