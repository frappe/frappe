<template>
	<div class="flex flex-row flex-wrap gap-5">
		<div
			v-if="!data?.length"
			class="pointer-events-none flex h-full w-full items-center justify-center rounded-sm bg-gray-100 p-5 text-base text-gray-700"
		>
			{{ emptyStateMessage || "No data" }}
		</div>
		<template v-else v-for="(dataItem, dataIndex) in data" :key="dataItem[dataKey]">
			<RepeaterContextProvider :dataItem="dataItem" :dataIndex="dataIndex" :dataKey="dataKey">
				<slot v-bind="{ dataItem, dataKey, dataIndex }"></slot>
			</RepeaterContextProvider>
		</template>
	</div>
</template>

<script setup lang="ts">
import RepeaterContextProvider from "@/components/AppLayout/RepeaterContextProvider.vue"
import type { RepeaterProps } from "@/types/studio_components/Repeater"

defineProps<RepeaterProps>()
</script>
