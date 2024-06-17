<template>
	<div class="mx-5 my-4 flex h-[41rem] max-w-[1340px] flex-col gap-4">
		<div v-if="configSettings.data" class="overflow-x-none flex w-full justify-between gap-2">
			<ViewSwitcher :queryFilters="queryFilters" />
			<ListControls
				v-if="listConfig.fields"
				:options="listControlOptions"
				@fetch="(updateCount) => fetchList(updateCount)"
				@reload="renderList"
			/>
		</div>
		<ListView
			v-if="listResource.data?.length"
			:rows="listResource.data"
			rowKey="name"
			:columns="listConfig.columns"
			:options="listOptions"
		>
			<template #cell="{ item, row, column }">
				<ListFormatter
					:item="item"
					:row="row"
					:column="column"
					:titleField="listConfig.titleField"
				/>
			</template>
		</ListView>
		<div v-else class="my-4 flex h-full flex-col items-center justify-center gap-4">
			<span class="text-xl font-semibold">No records found</span>
			<Button variant="solid" size="md" :label="'Create New ' + doctype" />
		</div>
	</div>

	<ListFooter
		class="border-t px-5 py-2"
		v-model="pageLength"
		:options="{
			rowCount: listResource.data?.length,
			totalCount: totalCount,
		}"
		@loadMore="handleLoadMore"
	/>
</template>

<script setup>
import { ref, computed, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { watchDebounced } from "@vueuse/core"

import { call, createResource, ListView, ListFooter } from "frappe-ui"

import ListControls from "@/components/List/ListControls.vue"
import ListFormatter from "@/components/List/ListFormatter.vue"
import ViewSwitcher from "@/components/ViewSwitcher.vue"

import { doctypesBySlug } from "@/data/permissions"

import {
	doctype,
	configName,
	configSettings,
	isDefaultConfig,
	listConfig,
	oldConfig,
	configUpdated,
} from "@/stores/view"

const route = useRoute()
const router = useRouter()
const pageLength = ref(20)
const rowCount = ref(20)
const totalCount = ref(0)

const listControlOptions = {
	showColumnSettings: true,
	showFilters: true,
	showSortSelector: true,
}

const listOptions = {
	showTooltip: false,
	selectable: true,
	resizeColumn: true,
	rowHeight: 47,
}

// Display list based on default or saved view

const renderList = async () => {
	configName.value = route.query.view
	await loadConfig()
	await addSavedFilters()
	await createConfigObj()
	await fetchList()
}

const loadConfig = async () => {
	isDefaultConfig.value = configName.value == null
	await configSettings.fetch()
}

const addSavedFilters = async () => {
	if (isDefaultConfig.value) return
	let query_params = { view: configName.value }
	configSettings.data.filters?.map((f) => {
		let fieldname = f[0]
		if (query_params[fieldname]) query_params[fieldname].push(JSON.stringify([f[1], f[2] + ""]))
		else query_params[fieldname] = [JSON.stringify([f[1], f[2] + ""])]
	})
	await router.push({ query: query_params })
}

const createConfigObj = async () => {
	listConfig.value = {
		...configSettings.data,
		filters: currentFilters.value,
		sort: [configSettings.data.sort_field, configSettings.data.sort_order],
	}
	oldConfig.value = JSON.parse(JSON.stringify(listConfig.value))
}

const fetchList = async (updateCount) => {
	if (updateCount) await updateTotalCount()
	await listResource.fetch()
}

const listResource = createResource({
	url: `frappe.desk.doctype.view_config.view_config.get_list`,
	makeParams() {
		return {
			doctype: doctype.value,
			cols: listConfig.value.columns,
			filters: queryFilters.value,
			limit: rowCount.value,
			start: 0,
			order_by: querySort.value,
		}
	},
})

// Maintain current sort and filtering

const currentSort = computed(() => [listConfig.value.sort[0], listConfig.value.sort[1]])

const querySort = computed(() => `${currentSort.value.join(" ")}`)

const getFieldType = (fieldname) => {
	return configSettings.data?.fields.find((f) => f.value === fieldname).type || ""
}

const getSelectOptions = (fieldname) => {
	return configSettings.data?.fields.find((f) => f.value === fieldname).options?.split("\n") || []
}

const getParsedFilter = (key, filter) => {
	let f = JSON.parse(filter)
	return {
		fieldname: key,
		fieldtype: getFieldType(key),
		operator: f[0],
		value: f[1],
		options: getSelectOptions(key),
	}
}

const currentFilters = computed(() => {
	let filters = []
	if (route.query) {
		for (let key in route.query) {
			if (key == "view") continue

			if (typeof route.query[key] == "string") filters.push(getParsedFilter(key, route.query[key]))
			else {
				route.query[key].forEach((v) => {
					filters.push(getParsedFilter(key, v))
				})
			}
		}
	}
	return filters
})

const queryFilters = computed(
	() => currentFilters.value.map((f) => [f.fieldname, f.operator, f.value]) || []
)

// Footer actions
const updateTotalCount = async () => {
	totalCount.value = await call("frappe.client.get_count", {
		doctype: doctype.value,
		filters: queryFilters.value,
	})
}

const handleLoadMore = async () => {
	rowCount.value += pageLength.value
	await fetchList()
}

watch(
	() => (route.params.doctype, route.query.view),
	async () => {
		doctype.value = doctypesBySlug[route.params.doctype]?.name
		await renderList(doctype.value, route.query.view)
	},
	{ immediate: true }
)

watch(
	() => pageLength.value,
	async () => {
		rowCount.value = pageLength.value
		await fetchList()
	}
)

watchDebounced(
	() => [JSON.stringify(listConfig.value.columns), JSON.stringify(listConfig.value.sort)],
	async () => {
		if (!listConfig.value.columns || !listConfig.value.sort) return

		if (isDefaultConfig.value && configUpdated.value) {
			let res = await call("frappe.desk.doctype.view_config.view_config.update_config", {
				doctype: doctype.value,
				config: listConfig.value,
				config_name: configName.value,
			})
			configName.value = res.name
			oldConfig.value = JSON.parse(JSON.stringify(listConfig.value))
		}
	},
	{ debounce: 1000, maxWait: 1000 }
)
</script>
