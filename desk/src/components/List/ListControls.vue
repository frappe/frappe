<template>
	<template v-if="options.showColumnSettings && config.columns">
		<ListColumnSettings v-model="config.columns" :allColumns="config.fields" />
	</template>
	<template v-if="options.showFilters">
		<ListFilters v-model="config.filters" :allFilterableFields="config.fields" />
	</template>
	<template v-if="options.showSortSelector">
		<ListSortSelector v-model="config.sort" :allSortableFields="config.columns" />
	</template>
</template>

<script setup>
import { defineModel } from "vue"
import ListColumnSettings from "@/components/List/ListColumnSettings.vue"
import ListFilters from "@/components/List/ListFilters.vue"
import ListSortSelector from "@/components/List/ListSortSelector.vue"

const config = defineModel()

const emit = defineEmits(["update"])

const props = defineProps({
	options: {
		type: Object,
		default: {},
	},
})
</script>
