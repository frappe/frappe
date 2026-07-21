<template>
	<div class="flex flex-row flex-wrap gap-5">
		<div
			v-if="!data?.length"
			class="pointer-events-none flex h-full w-full items-center justify-center p-5 text-base text-ink-gray-6"
		>
			{{ emptyStateMessage || "No data" }}
		</div>
		<template v-else v-for="(dataItem, dataIndex) in data" :key="dataItem?.[dataKey] || dataIndex">
			<SlotScopeProvider :scope="{ dataItem, dataIndex, dataKey }">
				<slot v-bind="{ dataItem, dataKey, dataIndex }"></slot>
			</SlotScopeProvider>
		</template>
	</div>
</template>

<script setup lang="ts">
import SlotScopeProvider from "@/components/SlotScopeProvider.vue"
import type { RepeaterProps } from "@/types/studio_components/Repeater"

defineProps<RepeaterProps>()
</script>
