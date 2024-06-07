<template>
	<div class="flex gap-2">
		<ListFilters
			v-if="options.showFilters"
			v-model="config.filters"
			:allFilterableFields="config.fields"
		/>
		<ListColumnSettings
			v-if="options.showColumnSettings && config.columns"
			v-model="config.columns"
			:allColumns="config.fields"
		/>
		<ListSortSelector
			v-if="options.showSortSelector"
			v-model="config.sort"
			:allSortableFields="config.columns"
		/>
	</div>
</template>

<script setup>
import { defineModel } from "vue"
import ListColumnSettings from "@/components/List/ListColumnSettings.vue"
import ListFilters from "@/components/List/ListFilters.vue"
import ListSortSelector from "@/components/List/ListSortSelector.vue"

const config = defineModel()

const emit = defineEmits(["update", "reload", "updateDefaultConfig"])

const props = defineProps({
	options: {
		type: Object,
		default: {},
	},
})
</script>
