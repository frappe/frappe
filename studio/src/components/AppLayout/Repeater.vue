<template>
	<div class="flex flex-row flex-wrap gap-5">
		<template v-for="item in data" :key="item[dataKey]">
			<slot v-bind="{ item, dataKey }">
				<div class="rounded-sm border border-gray-200 p-5 text-xs text-gray-500">{{ item[dataKey] }}</div>
			</slot>
		</template>
	</div>
</template>

<script setup lang="ts">
const props = defineProps<{
	data: Array<any>
	dataKey: string
}>()
</script>
