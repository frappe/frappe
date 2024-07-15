<template>
	<div class="mx-5 my-4 flex h-[41rem] flex-col gap-4">
		<div class="overflow-x-none flex w-full justify-between gap-2">
			<ViewSwitcher :queryFilters="queryFilters" />
			<ListControls :options="listControlOptions" />
		</div>
		<ListView
			v-if="listConfig && listResource.data?.length"
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
					:titleField="listConfig?.title_field"
				/>
			</template>
		</ListView>

		<!-- Empty State -->
		<div v-else class="my-4 flex h-full flex-col items-center justify-center gap-4">
			<span class="text-xl font-semibold">No records found</span>
			<Button variant="solid" size="md" :label="`Create New ${doctype}`" />
		</div>
	</div>

	<ListFooter
		class="border-t px-5 py-2.5"
		v-model="pageLength"
		:options="{
			rowCount: listResource.data?.length,
			totalCount: totalCount,
		}"
		@loadMore="handleLoadMore"
	/>
</template>

<script setup lang="ts">
import { ref, computed, watch, provide } from "vue"
import { useRoute, useRouter } from "vue-router"
import { watchDebounced } from "@vueuse/core"

import { call, createResource, ListView, ListFooter } from "frappe-ui"

import ListControls from "@/components/List/ListControls.vue"
import ListFormatter from "@/components/List/ListFormatter.vue"
import ViewSwitcher from "@/components/ViewSwitcher.vue"

import { doctypesBySlug } from "@/data/permissions"
import { cloneObject } from "@/utils"
import { getFilterQuery } from "@/utils/list"

import {
	doctype,
	configName,
	configSettings,
	isDefaultConfig,
	listConfig,
	oldConfig,
	configUpdated,
} from "@/stores/view"

import { fetchListFnKey, renderListFnKey } from "@/types/injectionKeys"
import { useRouteParamsAsStrings } from "@/composables/router"
import { FieldTypes } from "@/types/controls"
import {
	RouteQuery,
	ListFilterOperator,
	ListFilter,
	ListQueryFilter,
	ListResource,
	isValidFilterOperator,
} from "@/types/list"

const route = useRoute()
const router = useRouter()
const routeParams = useRouteParamsAsStrings()

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
	configName.value = (route.query.view || "") as string
	await loadConfig()
	await addSavedFilters()
	await createConfigObj()
	await fetchList(true)
}

const loadConfig = async () => {
	isDefaultConfig.value = configName.value == ""
	await configSettings.fetch()
}

const addSavedFilters = async () => {
	if (isDefaultConfig.value) return
	let queryParams: RouteQuery = { view: configName.value }
	let savedFilters = configSettings.data.filters
	Object.assign(queryParams, getFilterQuery(savedFilters))
	await router.replace({ query: queryParams })
}

const createConfigObj = async () => {
	listConfig.value = {
		...configSettings.data,
		filters: currentFilters.value,
	}
	oldConfig.value = cloneObject(listConfig.value)
}

const fetchList = async (updateCount = false) => {
	updateCount && (await updateTotalCount())
	await listResource.fetch()
}

const listResource: ListResource = createResource({
	url: "frappe.desk.doctype.view_config.view_config.get_list",
	makeParams() {
		return {
			doctype: doctype.value,
			cols: listConfig.value?.columns,
			filters: queryFilters.value,
			limit: rowCount.value,
			order_by: querySort.value,
		}
	},
})

// Maintain current sort and filtering

const currentSort = computed(() =>
	listConfig.value ? [listConfig.value.sort[0], listConfig.value.sort[1]] : []
)

const querySort = computed(() => `${currentSort.value.join(" ")}`)

const getFieldType = (fieldname: string): FieldTypes | "" => {
	return configSettings.data?.fields.find((f) => f.key === fieldname)?.type || ""
}

const getSelectOptions = (fieldname: string): string[] => {
	return configSettings.data?.fields.find((f) => f.key === fieldname)?.options || []
}

const getParsedFilter = (key: string, filter: string): ListFilter | undefined => {
	let f: string | string[] = JSON.parse(filter)
	let fieldtype = getFieldType(key)
	if (!fieldtype) return
	if (Array.isArray(f) && !isValidFilterOperator(f[0])) return
	return {
		fieldname: key,
		fieldtype: fieldtype,
		operator: Array.isArray(f) ? (f[0] as ListFilterOperator) : "=",
		value: Array.isArray(f) ? f[1] : f,
		options: getSelectOptions(key),
	}
}

const currentFilters = computed(() => {
	let filters: ListFilter[] = []
	let query = route.query as RouteQuery
	if (query) {
		for (let key in query) {
			if (key == "view") continue
			let value = query[key]

			if (typeof value == "string") {
				let parsedFilter = getParsedFilter(key, value)
				if (parsedFilter) filters.push(parsedFilter)
			} else {
				value.forEach((v) => {
					let parsedFilter = getParsedFilter(key, v)
					if (parsedFilter) filters.push(parsedFilter)
				})
			}
		}
	}
	return filters
})

const queryFilters = computed<ListQueryFilter[]>(() => {
	if (!currentFilters.value) return []
	return currentFilters.value.map((f) => {
		let val = f.operator === "between" ? f.value.split(",") : f.value
		return [f.fieldname, f.operator, val]
	})
})

// Footer actions
const updateTotalCount = async () => {
	totalCount.value = await call("frappe.client.get_count", {
		doctype: doctype.value,
		filters: queryFilters.value,
	})
}

const handleLoadMore = async () => {
	rowCount.value += pageLength.value
	await fetchList(true)
}

watch(
	() => (routeParams.doctype, route.query.view),
	async () => {
		doctype.value = doctypesBySlug[routeParams.doctype]?.name
		await renderList()
	},
	{ immediate: true }
)

watch(
	() => pageLength.value,
	async () => {
		rowCount.value = pageLength.value
		await fetchList(true)
	}
)

watchDebounced(
	() => [JSON.stringify(listConfig.value?.columns), JSON.stringify(listConfig.value?.sort)],
	async () => {
		if (!listConfig.value || !oldConfig.value) return

		if (isDefaultConfig.value && configUpdated.value) {
			let res = await call("frappe.desk.doctype.view_config.view_config.update_config", {
				doctype: doctype.value,
				config: listConfig.value,
				config_name: configName.value,
			})
			configName.value = res.name
			oldConfig.value.columns = cloneObject(listConfig.value.columns)
			oldConfig.value.sort = cloneObject(listConfig.value.sort)
		}
	},
	{ debounce: 1000, maxWait: 1000 }
)

provide(fetchListFnKey, fetchList)
provide(renderListFnKey, renderList)
</script>
