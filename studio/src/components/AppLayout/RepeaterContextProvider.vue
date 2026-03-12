<template>
	<slot />
</template>

<script setup lang="ts">
import { computed, provide } from "vue"

const props = defineProps<{
	dataItem: any
	dataIndex: number
	dataKey: string
}>()

const context = computed(() => ({
	dataItem: props.dataItem,
	dataIndex: props.dataIndex,
	dataKey: props.dataKey,
}))

provide("repeaterContext", context)
</script>
