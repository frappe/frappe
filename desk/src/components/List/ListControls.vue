<template>
	<div class="flex gap-2">
		<ListFilters
			v-if="options.showFilters"
			v-model="listConfig.filters"
			:allFilterableFields="listConfig.fields"
		/>
		<ListColumnSettings
			v-if="options.showColumnSettings && listConfig.columns"
			v-model="listConfig.columns"
			:allColumns="listConfig.fields"
		/>
		<ListSortSelector
			v-if="options.showSortSelector"
			v-model="listConfig.sort"
			:allSortableFields="listConfig.columns"
		/>
	</div>
</template>

<script setup>
import ListColumnSettings from "@/components/List/ListColumnSettings.vue"
import ListFilters from "@/components/List/ListFilters.vue"
import ListSortSelector from "@/components/List/ListSortSelector.vue"

import { listConfig } from "@/stores/view"

const emit = defineEmits(["update", "reload", "fetch"])

const props = defineProps({
	options: {
		type: Object,
		default: {},
	},
})
</script>
