<template>
	<div class="flex flex-row flex-wrap gap-5">
		<div
			v-if="!data?.length"
			class="pointer-events-none flex h-full w-full items-center justify-center p-5 font-semibold text-gray-500"
		>
			Connect data to the repeater
		</div>
		<template v-else v-for="(item, index) in data" :key="item[dataKey]">
			<RepeaterContextProvider :item="item" :index="index" :dataKey="dataKey">
				<slot v-bind="{ item, dataKey, index }"></slot>
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
