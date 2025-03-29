<template>
	<div class="flex flex-row flex-wrap gap-5">
		<template v-for="(item, index) in data" :key="item[dataKey]">
			<RepeaterContextProvider :item="item" :index="index" :dataKey="dataKey">
				<slot v-bind="{ item, dataKey, index }">
					<div class="rounded-sm border border-gray-200 p-5 text-xs text-gray-500">{{ item[dataKey] }}</div>
				</slot>
			</RepeaterContextProvider>
		</template>
	</div>
</template>

<script setup lang="ts">
import RepeaterContextProvider from "@/components/AppLayout/RepeaterContextProvider.vue"
defineProps<{
	data?: Array<any>
	dataKey: string
}>()
</script>
