<template>
	<slot />
</template>

<script setup lang="ts">
import { provide, reactive } from "vue"

const props = defineProps<{
	dataItem: any
	dataIndex: number
	dataKey: string
}>()

const context = reactive({
	dataItem: props.dataItem,
	dataIndex: props.dataIndex,
	dataKey: props.dataKey,
})

provide("repeaterContext", context)
</script>
